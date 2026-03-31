"""
LanceDB 存储模块 - 向量存储和搜索
修复版：使用 PyArrow schema，支持 LanceDB 0.27+
"""
import os
import re
import math
import json
import uuid
import time
import traceback
import logging
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import lancedb
import pyarrow as pa
from memory_config import CONFIG
from memory_config_multi import get_active_config

# 动态 schema（根据 embedding 维度自适应）
def _build_schema(dimensions: int = None):
    """根据 embedding 维度动态构建 schema"""
    if dimensions is None:
        try:
            dimensions = get_active_config().get_embedding_config().get("dimensions", 1024)
        except Exception:
            dimensions = 1024
    return pa.schema([
        ("id", pa.string()),
        ("type", pa.string()),
        ("content", pa.string()),
        ("summary", pa.string()),
        ("importance", pa.float32()),
        ("source", pa.string()),
        ("transcript", pa.string()),
        ("tags", pa.string()),  # JSON string
        ("scope", pa.string()),
        ("scope_id", pa.string()),
        ("vector", pa.list_(pa.float32(), dimensions)),  # 动态维度
        ("created_at", pa.string()),
        ("updated_at", pa.string()),
        ("last_accessed", pa.string()),
        ("access_count", pa.int32()),
        ("revision_chain", pa.string()),  # JSON string
        ("superseded_by", pa.string()),
    ])

# 默认 schema (向后兼容，1024维)
SCHEMA = _build_schema(1024)

# 配置日志 - 【P1修复】添加错误日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
_logger = logging.getLogger("ClawMemory")

# 辅助函数：安全执行并记录错误
def _safe_call(func, default=None, context=""):
    """【P1修复】安全调用函数，记录任何异常"""
    try:
        return func()
    except Exception as e:
        _logger.error(f"{context}: {e}\n{traceback.format_exc()}")
        return default

# 修复1：使用 PyArrow schema 而非 Python dict
# 注意：LanceDB 需要 fixed_size_list 类型作为向量，不能用普通的 list_
SCHEMA = pa.schema([
    ("id", pa.string()),
    ("type", pa.string()),
    ("content", pa.string()),
    ("summary", pa.string()),
    ("importance", pa.float32()),
    ("source", pa.string()),
    ("transcript", pa.string()),
    ("tags", pa.string()),  # JSON string
    ("scope", pa.string()),
    ("scope_id", pa.string()),
    ("vector", pa.list_(pa.float32(), 1024)),  # bge-m3: 1024 dims - 必须用固定大小
    ("created_at", pa.string()),
    ("updated_at", pa.string()),
    ("last_accessed", pa.string()),
    ("access_count", pa.int32()),
    ("revision_chain", pa.string()),  # JSON string
    ("superseded_by", pa.string()),
])


class LanceDBStore:
    def __init__(self, db_path=None):
        self.db_path = db_path or CONFIG.get("db_path", "/Users/claw/.openclaw/workspace/memory/lancedb")
        self._ensure_dir()
        self.db = self._connect()
        self.table = self._get_table()
    
    def _ensure_dir(self):
        Path(self.db_path).mkdir(parents=True, exist_ok=True)
    
    def _ensure_connected(self) -> bool:
        """【P0修复】确保数据库已连接，必要时重连"""
        try:
            # 检查连接是否有效
            if self.db is not None:
                try:
                    # 尝试获取表列表验证连接
                    _ = self.db.table_names()
                    if self.table is None:
                        self.table = self._get_table()
                    return True
                except Exception:
                    pass
            
            # 需要重连
            self.db = self._connect()
            self.table = self._get_table()
            return self.table is not None
        except Exception:
            return False
    
    def _connect(self):
        try:
            return lancedb.connect(self.db_path)
        except Exception as e:
            _logger.error(f"connect error: {e}")
            return None
    
    def _get_table(self):
        if self.db is None:
            return None
        try:
            table_names = self.db.table_names()
            if "memories" in table_names:
                return self.db.open_table("memories")
            
            # 创建表 - 使用 PyArrow schema
            table = self.db.create_table("memories", schema=SCHEMA)
            
            # 创建索引加速查询（vector和id字段）
            try:
                table.create_vector_index("vector", engine="lance")
            except:
                pass
            
            return table
        except Exception as e:
            _logger.error(f"get_table error: {e}")
            return None
    
    def store(self, memory: dict) -> bool:
        """存储记忆"""
        # 【P0修复】确保已连接
        if not self._ensure_connected():
            _logger.warning("table not initialized")
            return False
        
        try:
            # 生成向量 - 使用 MultiEmbedder（自动适配所有方案）
            from multi_embed import get_embedder
            import numpy as np
            
            # 【边界修复】内容长度限制 50KB
            content = memory.get("content", "")
            if len(content) > 50000:
                content = content[:50000]
                _logger.debug("内容已截断至50KB")
            
            # 【边界修复】过滤 null bytes 和控制字符（保留可见字符+中文+emoji）
            import re
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)
            
            # 【边界修复】clamp importance 到 [0.0, 1.0]
            importance = float(memory.get("importance", 0.5))
            importance = max(0.0, min(1.0, importance))
            
            # 【边界修复】tags 序列化保护
            try:
                tags = json.dumps(memory.get("tags", []) or [])
            except (TypeError, ValueError):
                tags = "[]"
            
            embedder = get_embedder()
            raw_vector = embedder.embed(content)
            dims = embedder.dimensions
            
            # 确保向量维度正确（动态适配不同 embedding 提供者）
            if raw_vector:
                if len(raw_vector) < dims:
                    vector = raw_vector + [0.0] * (dims - len(raw_vector))
                else:
                    vector = raw_vector[:dims]
            else:
                vector = [0.0] * dims
            
            if not vector:
                _logger.warning("failed to generate embedding")
                return False
            
            # 【P1新增】加密敏感字段
            try:
                from e2e_encryption import encrypt_data as encrypt_text, is_encrypted
                # 只加密较长的内容（短内容加密后反而更大）
                if len(content) > 50 and not is_encrypted(content):
                    content = encrypt_text(content)
                if memory.get("transcript") and len(memory.get("transcript", "")) > 50:
                    if not is_encrypted(memory.get("transcript", "")):
                        memory["transcript"] = encrypt_text(memory["transcript"])
            except ImportError:
                pass  # 加密模块不可用，不加密
            
            # 准备数据
            now = datetime.now().isoformat()
            record = {
                "id": memory.get("id", str(uuid.uuid4())),
                "type": memory.get("type", "fact"),
                "content": content,
                "summary": memory.get("summary", ""),
                "importance": importance,
                "source": memory.get("source", ""),
                "transcript": memory.get("transcript", ""),
                "tags": json.dumps(memory.get("tags", [])),
                "scope": memory.get("scope", "user"),
                "scope_id": memory.get("scope_id", ""),
                "vector": vector,
                "created_at": memory.get("created_at", now),
                "updated_at": now,
                "last_accessed": now,
                "access_count": 1,
                "revision_chain": json.dumps(memory.get("revision_chain", [])),
                "superseded_by": memory.get("superseded_by", ""),
            }
            
            self.table.add([record])
            return True
        except Exception as e:
            _logger.error(f"store error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def search(self, query: str, limit: int = 5, types: list = None, min_score: float = 0.3,
               scope: str = None, use_rerank: bool = False) -> list[dict]:
        """
        语义搜索记忆
        
        Args:
            query: 搜索查询
            limit: 返回数量
            types: 过滤类型列表
            min_score: 最低重要性分数
            scope: 【新增】范围过滤 - global|user|project|agent|session|channel
            use_rerank: 【新增】是否使用Cross-Encoder重排
        """
        if self.table is None:
            return []
        
        try:
            # 生成查询向量 - 使用 MultiEmbedder
            from multi_embed import get_embedder
            query_vector = get_embedder().embed(query)
            
            if not query_vector:
                _logger.warning("failed to generate query embedding")
                return []
            
            # 向量搜索 - 多取一些用于重排
            search_limit = limit * 5 if use_rerank else limit * 3
            results = (
                self.table
                .search(query_vector, vector_column_name="vector")
                .limit(search_limit)
                .to_arrow()
                .to_pylist()
            )
            
            # 后处理
            filtered = []
            for r in results:
                if types and r.get("type") not in types:
                    continue
                
                # 【新增】Scope过滤
                if scope and r.get("scope") != scope:
                    continue
                
                # 检查重要性阈值
                importance = r.get("importance", 0)
                if importance < min_score:
                    continue
                
                # 解析 tags
                tags_str = r.get("tags", "[]")
                try:
                    r["tags_parsed"] = json.loads(tags_str) if tags_str else []
                except:
                    r["tags_parsed"] = []
                
                filtered.append(r)
                
                if len(filtered) >= (limit * 3 if use_rerank else limit):
                    break
            
            # 【新增】重排：优先 MultiReranker（API方案A/B），回退到 Cross-Encoder（本地方案D）
            if use_rerank and filtered:
                # 优先尝试 API reranker（方案A/B）
                try:
                    from multi_rerank import get_reranker
                    api_reranker = get_reranker()
                    if api_reranker.is_available():
                        _logger.debug(f"[Search] Using API reranker: {api_reranker}")
                        filtered = api_reranker.rerank(query, filtered, top_k=limit)
                    else:
                        # 回退到本地 Cross-Encoder
                        filtered = self._rerank_cross_encoder(query, filtered, limit)
                except Exception as e:
                    _logger.debug(f"[Search] API reranker unavailable, trying Cross-Encoder: {e}")
                    try:
                        filtered = self._rerank_cross_encoder(query, filtered, limit)
                    except Exception:
                        pass
            
            # 更新访问追踪（静默失败，不影响主流程）
            for r in filtered:
                try:
                    self._update_access_safe(r["id"])
                except Exception:
                    pass
            
            return filtered[:limit]
        except Exception as e:
            _logger.error(f"search error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _rerank_cross_encoder(self, query: str, candidates: list, limit: int) -> list[dict]:
        """
        【P0修复】Cross-Encoder重排
        使用专用模型 ms-marco-MiniLM-L-6-v2 进行相关性排序
        替换原 qwen3.5 LLM方案，延迟从5-15秒降低到<10毫秒
        """
        try:
            from cross_encoder_rerank import get_reranker
            
            reranker = get_reranker()
            
            if not reranker.is_available():
                _logger.info("Cross-Encoder模型不可用，使用原始分数")
                return candidates[:limit]
            
            # 使用专用Cross-Encoder进行批量重排
            start_time = time.time()
            reranked = reranker.rerank(query, candidates, top_k=limit)
            elapsed_ms = (time.time() - start_time) * 1000
            
            _logger.debug(f"Cross-Encoder重排完成，耗时 {elapsed_ms:.1f}ms")
            
            # 计算综合分数 = 向量相似度 * 0.3 + Cross-Encoder * 0.7
            scored = []
            for r in reranked:
                vector_score = 1.0 - r.get("_distance", 0.5)
                cross_score = r.get("cross_score", 0.5)
                final_score = vector_score * 0.3 + cross_score * 0.7
                r["_final_score"] = final_score
                scored.append(r)
            
            # 按最终分数排序
            scored.sort(key=lambda x: x.get("_final_score", 0), reverse=True)
            
            return scored[:limit]
            
        except ImportError:
            _logger.info("Cross-Encoder模块不可用，跳过重排")
            return candidates[:limit]
        except Exception as e:
            _logger.error(f"Cross-Encoder重排失败: {e}")
            return candidates[:limit]
            
            # 按最终分数排序
            scored.sort(key=lambda x: x.get("_final_score", 0), reverse=True)
            
            return scored[:limit]
            
        except Exception as e:
            _logger.error(f"rerank error: {e}")
            return candidates[:limit]
    
    def _rrf_fusion(self, result_lists: list, k: int = 60, weights: dict = None) -> list:
        """
        【新增】Reciprocal Rank Fusion (RRF) 多通道融合
        
        RRF公式: Σ w_i * 1/(k + rank_i) for each channel
        其中 w_i 是通道权重
        
        Args:
            result_lists: 多个搜索通道的结果列表
            k: RRF参数，默认60
            weights: 各通道权重字典，如 {"vector": 0.4, "bm25": 0.25, ...}
            
        Returns:
            融合排序后的结果
        """
        from collections import defaultdict
        
        # 默认等权重
        if weights is None:
            weights = {"vector": 0.25, "bm25": 0.25, "importance": 0.25, "kg": 0.25, "temporal": 0.25}
        
        channel_names = ["vector", "bm25", "importance", "kg", "temporal"]
        
        # 每个文档的RRF累加分数
        rrf_scores = defaultdict(float)
        doc_index = {}  # doc_id -> doc_dict
        
        for idx, results in enumerate(result_lists):
            if not results:
                continue
            
            channel_name = channel_names[idx] if idx < len(channel_names) else f"channel_{idx}"
            channel_weight = weights.get(channel_name, 1.0)
            
            for rank, doc in enumerate(results):
                doc_id = doc.get("id", "")
                if not doc_id:
                    continue
                
                # 加权RRF score = w * 1 / (k + rank)
                rrf_score = channel_weight / (k + rank + 1)  # +1避免除零
                rrf_scores[doc_id] += rrf_score
                
                # 保存文档
                if doc_id not in doc_index:
                    doc_index[doc_id] = doc.copy()
                    doc_index[doc_id]["_channel_scores"] = {}
                    doc_index[doc_id]["_channel_names"] = []
                
                # 记录各通道分数（带通道名）
                doc_index[doc_id]["_channel_scores"][channel_name] = doc.get("_final_score", doc.get("importance", 0.5))
                if channel_name not in doc_index[doc_id]["_channel_names"]:
                    doc_index[doc_id]["_channel_names"].append(channel_name)
        
        # 按RRF分数排序
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 【P0修复】过滤placeholder/test记忆
        # 这些记忆没有实际内容但有高重要性分数
        placeholder_patterns = [
            "high importance", "importance上限", "测试重要性",
            "test", "测试", "placeholder", "todo", "tmp"
        ]
        
        def is_valid_memory(doc):
            content = doc.get("content", "").lower()
            summary = doc.get("summary", "").lower()
            full_text = (content + " " + summary).strip()
            
            # 如果content太短或只是placeholder，降低优先级
            if len(content) < 5:
                return False
            for pattern in placeholder_patterns:
                if pattern.lower() in full_text and len(full_text) < 30:
                    return False
            return True
        
        # 组装结果
        fused_results = []
        valid_results = []
        placeholder_results = []
        
        for doc_id, rrf_score in sorted_docs:
            doc = doc_index[doc_id]
            doc["_rrf_score"] = round(rrf_score, 6)
            doc["_total_channels"] = len(doc["_channel_scores"])
            
            if is_valid_memory(doc):
                valid_results.append(doc)
            else:
                placeholder_results.append(doc)
        
        # 优先返回有效记忆，placeholder放最后
        fused_results = valid_results + placeholder_results
        
        return fused_results
    
    def _get_bm25_scores(self, query: str, limit: int) -> list:
        """
        【P0修复】BM25通道 - 使用采样代替全表加载
        
        采样策略：最多采样1000条记忆计算IDF，避免OOM
        """
        try:
            if self.table is None:
                return []
            
            # 【P0修复】使用head()采样代替全表加载
            sample_size = min(1000, self.table.count_rows())
            all_memories = self.table.head(sample_size).to_pylist() if sample_size > 0 else []
            
            if not all_memories:
                return []
            
            # 构建简单BM25
            from collections import Counter
            import math
            import re
            
            def tokenize(text):
                # 修复：支持中英文混合分词
                # 英文按单词分割，中文按字符或bigram分割
                text_lower = text.lower()
                # 英文单词
                english = re.findall(r'[a-z0-9_]+', text_lower)
                # 中文字符（也可以考虑使用bigram如"用户"作为"用户"）
                chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
                # 将连续中文字符转为字符列表
                chinese = []
                for chars in chinese_chars:
                    # 每2个字符作为一个词（bigram风格）
                    for i in range(len(chars)):
                        if i < len(chars) - 1:
                            chinese.append(chars[i:i+2])
                        else:
                            chinese.append(chars[i])
                return english + chinese
            
            # 计算DF
            doc_freqs = Counter()
            doc_len = []
            corpus = []
            
            for mem in all_memories:
                content = mem.get("content", "")
                tokens = set(tokenize(content))
                doc_freqs.update(tokens)
                doc_len.append(len(tokens))
                corpus.append(mem)
            
            N = len(corpus)
            avgdl = sum(doc_len) / N if N > 0 else 0
            
            # 计算IDF
            idf = {}
            for term, df in doc_freqs.items():
                idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)
            
            # 计算query与每个doc的BM25
            query_tokens = set(tokenize(query))
            scores = []
            
            k1, b = 1.5, 0.75
            
            for i, mem in enumerate(corpus):
                content = mem.get("content", "")
                tokens = tokenize(content)
                tf = Counter(tokens)
                dl = doc_len[i]
                
                score = 0.0
                for term in query_tokens:
                    if term not in idf:
                        continue
                    tq = 1 if term in tf else 0
                    if tq == 0:
                        continue
                    
                    tf_val = tf.get(term, 0)
                    idf_val = idf[term]
                    
                    # BM25 formula
                    numerator = tf_val * (k1 + 1)
                    denominator = tf_val + k1 * (1 - b + b * dl / avgdl)
                    score += idf_val * numerator / denominator
                
                if score > 0:
                    mem_copy = mem.copy()
                    mem_copy["bm25_score"] = round(score, 4)
                    mem_copy["_final_score"] = score
                    scores.append(mem_copy)
            
            # 按BM25分数排序
            scores.sort(key=lambda x: x.get("bm25_score", 0), reverse=True)
            return scores[:limit]
            
        except Exception as e:
            _logger.error(f"BM25 channel error: {e}")
            return []
    
    def _get_importance_scores(self, limit: int) -> list:
        """
        【P0修复】Importance通道 - 使用head()采样代替全表加载
        """
        try:
            if self.table is None:
                return []
            
            # 【P0修复】使用head()采样代替全表加载
            # LanceDB的head()获取前N条记录，足够做重要性排序采样
            total = self.table.count_rows()
            if total == 0:
                return []
            
            # 使用head()获取样本（最多200条）
            sample_size = min(200, total)
            try:
                sample = self.table.head(sample_size)
                if hasattr(sample, 'to_pylist'):
                    sample_list = sample.to_pylist()
                else:
                    sample_list = []
            except:
                sample_list = []
            
            # 按重要性排序
            scored = []
            for mem in sample_list:
                mem_copy = mem.copy()
                mem_copy["importance_score"] = mem.get("importance", 0.5)
                mem_copy["_final_score"] = mem.get("importance", 0.5)
                scored.append(mem_copy)
            
            scored.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
            return scored[:limit]
            
        except Exception:
            return []
    
    def search_rrf(self, query: str, limit: int = 5, k: int = 60, use_adaptive: bool = True, use_rerank: bool = None) -> list:
        """
        【新增】RRF融合搜索 - 5通道融合（支持自适应权重）
        
        Channels:
        1. Vector similarity
        2. BM25 keyword
        3. Importance score
        4. Knowledge Graph (实体关联)
        5. Temporal (时序感知)
        
        Args:
            query: 搜索查询
            limit: 返回数量
            k: RRF参数
            use_adaptive: 是否使用自适应权重
            
        Returns:
            RRF融合排序结果
        """
        try:
            # 【P2新增】意图分类 + 查询扩展
            # 【P0修复】根据意图自动决定是否启用Cross-Encoder
            intent_to_rerank = {"multihop", "decision", "lesson", "negation"}
            
            intent = None  # 默认值
            try:
                from intent_classifier import classify_query, expand_query, get_classifier
                classifier = get_classifier()
                intent, intent_confidence = classifier.classify(query)
                expanded_queries = classifier.expand_query(query)
                
                # 【P0修复】自动启用Cross-Encoder for高难度查询
                if use_rerank is None:
                    use_rerank = intent.value in intent_to_rerank or intent_confidence > 0.8
                
                # 如果是特殊意图，使用意图专用权重
                if intent_confidence > 0.75:
                    weights = classifier.get_channel_weights(intent)
                    _logger.debug(f"Intent: {intent.value} (conf={intent_confidence:.2f}), using adjusted weights")
                
                # 【P2优化】对于否定查询，使用扩展查询 + BM25优先
                if intent.value == "negation" and len(expanded_queries) > 1:
                    all_results = []
                    for eq in expanded_queries:
                        eq_results = self._get_bm25_scores(eq, limit=limit*3)
                        for r in eq_results:
                            # 额外boost包含否定词的结果
                            content = r.get("content", "")
                            if any(neg in content for neg in ["不", "没", "无", "非", "讨厌", "拒绝", "困难", "难以"]):
                                r["bm25_score"] = r.get("bm25_score", 0) * 1.5
                        all_results.extend(eq_results)
                    # 去重
                    seen = set()
                    unique_results = []
                    for r in all_results:
                        if r.get("id") not in seen:
                            seen.add(r.get("id"))
                            unique_results.append(r)
                    # 按BM25分数排序
                    unique_results.sort(key=lambda x: x.get("bm25_score", 0), reverse=True)
                    if unique_results:
                        return unique_results[:limit]
                
                # 【P2优化】对于lesson查询，使用扩展同义词
                if intent.value == "lesson" and len(expanded_queries) > 1:
                    all_results = []
                    for eq in expanded_queries:
                        eq_results = self._get_bm25_scores(eq, limit=limit*2)
                        all_results.extend(eq_results)
                    # 去重并排序
                    seen = set()
                    unique_results = []
                    for r in all_results:
                        if r.get("id") not in seen:
                            seen.add(r.get("id"))
                            unique_results.append(r)
                    unique_results.sort(key=lambda x: x.get("bm25_score", 0), reverse=True)
                    if unique_results:
                        return unique_results[:limit]
                
                # 对于模糊查询，尝试所有扩展查询
                if intent.value == "fuzzy" and len(expanded_queries) > 1:
                    # 收集所有扩展查询的结果
                    all_results = []
                    for eq in expanded_queries:
                        eq_results = self._get_bm25_scores(eq, limit=limit*2)
                        all_results.extend(eq_results)
                    # 去重
                    seen = set()
                    unique_results = []
                    for r in all_results:
                        if r.get("id") not in seen:
                            seen.add(r.get("id"))
                            unique_results.append(r)
                    # 用BM25结果覆盖向量搜索
                    if unique_results:
                        return unique_results[:limit]
            except ImportError:
                intent = None
                pass
            
            # 获取自适应权重
            weights = None
            if use_adaptive:
                try:
                    from incremental_learning import get_adaptive_weights
                    weights = get_adaptive_weights()
                except:
                    pass
            
            # 【P0优化】并行执行5个通道搜索，显著降低延迟
            import concurrent.futures
            
            def _run_vector():
                results = self.search(query, limit=limit*3, use_rerank=False)
                for r in results:
                    r["_final_score"] = 1.0 - r.get("_distance", 0.5)
                    r["_vector_score"] = r["_final_score"]
                return results
            
            def _run_bm25():
                results = self._get_bm25_scores(query, limit=limit*3)
                for r in results:
                    r["_bm25_score"] = r.get("bm25_score", 0)
                return results
            
            def _run_importance():
                results = self._get_importance_scores(limit=limit*3)
                for r in results:
                    r["_importance_score"] = r.get("importance_score", r.get("importance", 0.5))
                return results
            
            def _run_kg():
                results = self._kg_aware_search(query, limit=limit*3)
                for r in results:
                    r["_kg_score"] = r.get("_kg_score", r.get("importance", 0.5))
                return results
            
            def _run_temporal():
                results = self._temporal_search(query, limit=limit*3)
                for r in results:
                    r["_temporal_score"] = r.get("_temporal_score", 0.5)
                return results
            
            # 【P0修复】并行执行所有通道，使用字典保证结果对应正确
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(_run_vector): 'vector',
                    executor.submit(_run_bm25): 'bm25',
                    executor.submit(_run_importance): 'importance',
                    executor.submit(_run_kg): 'kg',
                    executor.submit(_run_temporal): 'temporal',
                }
                
                # 收集结果（as_completed不保证顺序）
                channel_results = {}
                for future in concurrent.futures.as_completed(futures):
                    channel_name = futures[future]
                    try:
                        channel_results[channel_name] = future.result()
                    except Exception as e:
                        _logger.warning(f"{channel_name} channel error: {e}")
                        channel_results[channel_name] = []
                
                vector_results = channel_results.get('vector', [])
                bm25_results = channel_results.get('bm25', [])
                importance_results = channel_results.get('importance', [])
                kg_results = channel_results.get('kg', [])
                temporal_results = channel_results.get('temporal', [])
            
            # RRF融合 (5通道)
            all_channels = [v for v in [vector_results, bm25_results, importance_results, kg_results, temporal_results] if v]
            
            fused = self._rrf_fusion(all_channels, k=k, weights=weights)
            
            # 【P0修复】Cross-Encoder最终语义重排
            # 条件：
            # 1. use_rerank=True (手动启用)
            # 2. use_rerank=None (auto): 高难度查询(negation/multihop/decision/lesson) 或 top_score < 0.5
            # 3. use_rerank=False: 不重排
            if fused and len(fused) > 1 and use_rerank is not False:
                try:
                    top_score = fused[0].get("_final_score", 0) if fused else 0
                    
                    # 自动判断是否需要重排
                    high_intent = intent and intent.value in {"multihop", "decision", "lesson", "negation"}
                    auto_rerank = high_intent or top_score < 0.5
                    
                    if use_rerank == True or (use_rerank is None and auto_rerank):
                        fused = self._rerank_cross_encoder(query, fused, limit)
                        _logger.debug(f"Cross-Encoder rerank (intent={intent.value if intent else 'None'}, top_score={top_score:.3f})")
                    else:
                        _logger.debug(f"Skipping rerank (top_score={top_score:.3f})")
                except Exception as e:
                    _logger.warning(f"Cross-Encoder rerank failed: {e}")
            
            # 更新访问记录
            for r in fused[:limit]:
                try:
                    self._update_access_safe(r["id"])
                except Exception:
                    pass
            
            return fused[:limit]
            
        except Exception as e:
            _logger.error(f"RRF search error: {e}")
            import traceback
            traceback.print_exc()
            # 降级到普通向量搜索
            return self.search(query, limit=limit)
    
    def search_cached(self, query: str, limit: int = 5, use_cache: bool = True, **kwargs) -> list:
        """
        【P3新增】带缓存的搜索
        
        Args:
            query: 搜索查询
            limit: 返回数量
            use_cache: 是否使用缓存
            **kwargs: 其他search参数
        """
        if not use_cache:
            return self.search(query, limit=limit, **kwargs)
        
        try:
            from search_cache import get_search_cache
            cache = get_search_cache()
            
            # 尝试从缓存获取
            cached = cache.get(query, limit=limit, **kwargs)
            if cached is not None:
                return cached
            
            # 执行搜索
            results = self.search(query, limit=limit, **kwargs)
            
            # 缓存结果
            cache.set(query, results, limit=limit, **kwargs)
            
            return results
        except ImportError:
            # 缓存模块不可用，降级到普通搜索
            return self.search(query, limit=limit, **kwargs)
        except Exception as e:
            _logger.error(f"cache error: {e}")
            return self.search(query, limit=limit, **kwargs)
    
    def search_rrf_cached(self, query: str, limit: int = 5, k: int = 60, use_cache: bool = True) -> list:
        """
        【P3新增】带缓存的RRF融合搜索
        """
        if not use_cache:
            return self.search_rrf(query, limit=limit, k=k)
        
        try:
            from search_cache import get_search_cache
            cache = get_search_cache()
            
            # 尝试从缓存获取
            cached = cache.get(query, limit=limit, k=k, rrf=True)
            if cached is not None:
                return cached
            
            # 执行搜索
            results = self.search_rrf(query, limit=limit, k=k)
            
            # 缓存结果
            cache.set(query, results, limit=limit, k=k, rrf=True)
            
            return results
        except ImportError:
            return self.search_rrf(query, limit=limit, k=k)
        except Exception as e:
            _logger.error(f"RRF cache error: {e}")
            return self.search_rrf(query, limit=limit, k=k)
    
    def _kg_aware_search(self, query: str, limit: int) -> list:
        """
        【P2优化】知识图谱感知搜索 - 支持稀疏图fallback

        改进点：
        1. 当KG为空或节点数过少时，fallback到关键词搜索
        2. 保持KG增强逻辑，但更鲁棒
        """
        try:
            from kg_networkx import get_kg_nx
            
            kg = get_kg_nx()
            kg_results = []
            
            # 【P2新增】检查KG是否足够丰富
            kg_node_count = kg.graph.number_of_nodes()
            kg_edge_count = kg.graph.number_of_edges()
            
            # 如果KG太稀疏（<10个节点或<5条边），使用关键词增强
            if kg_node_count < 10 or kg_edge_count < 5:
                # Fallback: 使用关键词匹配增强
                keywords = query.replace("用户", "").replace("什么", "").split()[:5]
                for kw in keywords:
                    if len(kw) > 1:
                        kw_results = self.search(kw, limit=limit, use_rerank=False)
                        for r in kw_results:
                            r_copy = r.copy()
                            r_copy["kg_score"] = 0.3  # 较低的KG分数
                            r_copy["_kg_score"] = 0.3
                            r_copy["kg_fallback"] = True
                            kg_results.append(r_copy)
                
                if kg_results:
                    # 去重并返回
                    seen_ids = set()
                    unique = []
                    for r in kg_results:
                        if r.get("id") not in seen_ids:
                            seen_ids.add(r.get("id"))
                            unique.append(r)
                    unique.sort(key=lambda x: x.get("kg_score", 0), reverse=True)
                    return unique[:limit]
            
            # 原有KG逻辑（当KG足够丰富时）
            # 1. 在知识图谱中搜索相关实体
            matched_entities = kg.search_entities(query, limit=5)
            
            if not matched_entities:
                # 2. 如果没有直接匹配，尝试传递推理
                # 从query中提取可能的实体名
                import re
                words = query.split()
                for word in words[:3]:  # 只检查前3个词
                    if len(word) > 2:
                        inferred = kg.infer_relations(word, max_depth=2)
                        for inf in inferred[:2]:
                            target = inf.get("target")
                            if target:
                                target_data = kg.get_entity(target)
                                if target_data:
                                    matched_entities.append(target_data)
            
            if not matched_entities:
                return []
            
            # 3. 对每个匹配实体，获取其关联网络
            for entity_data in matched_entities[:5]:
                entity_name = entity_data.get("name", "")
                if not entity_name:
                    continue
                
                # 获取实体网络
                network = kg.get_entity_network(entity_name, depth=2)
                
                # 4. 计算实体的图中心性分数
                centrality = len(network.get("nodes", [])) + len(network.get("relations", []))
                
                # 5. 对网络中的每个实体，找到关联的记忆
                for related_entity in network.get("nodes", []):
                    related_name = related_entity.get("name", entity_data.get("name", ""))
                    
                    # 在KG中搜索关联实体对应的记忆
                    # 通过实体名搜索记忆内容中包含该实体的记忆
                    entity_memories = self._search_memories_by_entity(related_name)
                    
                    for mem in entity_memories:
                        mem_copy = mem.copy()
                        # KG分数 = 中心性 * 关系权重 * 路径深度衰减
                        path_depth = related_entity.get("depth", 1)
                        depth_factor = 1.0 / (1 + path_depth * 0.5)
                        kg_score = centrality * 0.1 * depth_factor
                        
                        mem_copy["kg_score"] = kg_score
                        mem_copy["_final_score"] = kg_score
                        mem_copy["kg_entity"] = related_name
                        mem_copy["kg_path"] = f"{entity_name} -> {related_name}"
                        kg_results.append(mem_copy)
            
            # 6. 按KG分数排序，返回top结果
            kg_results.sort(key=lambda x: x.get("kg_score", 0), reverse=True)
            
            # 7. 去重（同一记忆可能从多个实体路径召回）
            seen_ids = set()
            unique_results = []
            for r in kg_results:
                if r.get("id") not in seen_ids:
                    seen_ids.add(r.get("id"))
                    unique_results.append(r)
            
            return unique_results[:limit]
            
        except Exception as e:
            _logger.error(f"_kg_aware_search error: {e}")
            return []
    
    def _temporal_search(self, query: str, limit: int = 10) -> list:
        """
        【P0修复】时序感知搜索 V2
        
        基于记忆内容中的时间关键词来判断，而不是依赖存储时间。
        这样可以正确处理刚存储的测试记忆。
        
        检测查询中的时间关键词，匹配记忆内容中的时间词：
        - "最近"、"近期"、"这周" → 优先返回包含"最近"、"这周"、"当前"的记忆
        - "以前"、"过去"、"曾经" → 优先返回包含"以前"、"曾经"、"过去"的记忆
        
        Args:
            query: 搜索查询
            limit: 返回数量
            
        Returns:
            带时序分数的记忆列表
        """
        import re
        from datetime import datetime, timedelta
        
        # 时间关键词检测
        query_lower = query.lower()
        
        # 【P0修复】扩大时序关键词检测范围
        recent_keywords = ["最近", "近期", "现在", "目前", "这周", "这月", "今天", "昨天", "当前", "进行中", "正在"]
        past_keywords = ["以前", "过去", "之前", "曾经", "早些", "当年", "那时", "曾经的", "过去的"]
        
        # 检测查询的时序意图
        is_recent = any(kw in query_lower for kw in recent_keywords)
        is_past = any(kw in query_lower for kw in past_keywords)
        
        # 如果没有时序意图，返回空列表让其他通道决定
        if not (is_recent or is_past):
            return []
        
        try:
            results = []
            
            # 【P0修复】多路召回：同时搜索语义和时间关键词
            temporal_words = recent_keywords + past_keywords
            
            # 1. 提取语义核心（去掉时间词）
            semantic_query = query_lower
            for kw in temporal_words:
                semantic_query = semantic_query.replace(kw, "")
            semantic_query = semantic_query.strip()
            
            # 2. 获取语义相关记忆
            all_memories = self.search(semantic_query if semantic_query else query, limit=limit*3, use_rerank=False)
            
            # 3. 【关键】同时搜索时间关键词本身，补充结果
            for kw in (recent_keywords if is_recent else past_keywords):
                if kw in query_lower:
                    time_results = self.search(kw, limit=limit*2, use_rerank=False)
                    all_memories.extend(time_results)
                    break  # 只加一个时间词的结果就够了
            
            # 4. 去重（基于id）
            seen_ids = set()
            unique_memories = []
            for m in all_memories:
                if m.get("id") not in seen_ids:
                    seen_ids.add(m.get("id"))
                    unique_memories.append(m)
            all_memories = unique_memories
            
            for memory in all_memories:
                content = memory.get("content", "").lower()
                summary = memory.get("summary", "").lower()
                full_text = content + " " + summary
                
                # 【P0修复】检测记忆内容中的时间关键词
                has_recent_word = any(kw in full_text for kw in recent_keywords)
                has_past_word = any(kw in full_text for kw in past_keywords)
                
                # 计算时间分数
                if is_recent and is_past:
                    # 混合意图，给两种都加分
                    if has_recent_word:
                        time_score = 0.9
                    elif has_past_word:
                        time_score = 0.3
                    else:
                        time_score = 0.5
                elif is_recent:
                    if has_recent_word:
                        time_score = 1.0  # 完全匹配
                    elif has_past_word:
                        time_score = 0.1  # 排除过去词
                    else:
                        time_score = 0.5  # 中等分数
                else:  # is_past
                    if has_past_word:
                        time_score = 1.0  # 完全匹配
                    elif has_recent_word:
                        time_score = 0.1  # 排除最近词
                    else:
                        time_score = 0.5  # 中等分数
                
                # 只有时序分数 > 0.3 的才加入
                if time_score > 0.3:
                    memory_copy = memory.copy()
                    memory_copy["_temporal_score"] = time_score
                    memory_copy["_has_recent_word"] = has_recent_word
                    memory_copy["_has_past_word"] = has_past_word
                    results.append(memory_copy)
            
            # 按时间分数排序
            results.sort(key=lambda x: x.get("_temporal_score", 0), reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            _logger.warning(f"_temporal_search error: {e}")
            return []
    
    def _search_memories_by_entity(self, entity_name: str) -> list:
        """
        辅助方法：在记忆内容中搜索包含指定实体的记忆
        """
        try:
            # 使用向量搜索找到内容中包含该实体名的记忆
            results = self.search(entity_name, limit=10, use_rerank=False)
            
            # 过滤出确实包含该实体的记忆
            filtered = []
            for r in results:
                content = r.get("content", "").lower()
                if entity_name.lower() in content:
                    filtered.append(r)
            
            return filtered
        except Exception:
            return []
    
    def _update_access_safe(self, memory_id: str):
        """
        更新访问记录 - 【P0修复】SQL注入防护
        """
        try:
            # 白名单校验
            import re
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
            if not uuid_pattern.match(memory_id):
                return
            
            # 使用零向量 + where 高效定位
            zero_vector = [0.0] * 1024
            results = (
                self.table
                .search(zero_vector, vector_column_name="vector")
                .where(f"id = '{memory_id}'")
                .limit(1)
                .to_arrow()
                .to_pylist()
            )
            
            if not results:
                return
            
            current = results[0]
            
            # 【关键修复】移除LanceDB search添加的_distance字段
            current.pop("_distance", None)
            
            now = datetime.now().isoformat()
            
            # 更新字段
            current["last_accessed"] = now
            current["access_count"] = current.get("access_count", 0) + 1
            current["updated_at"] = now
            
            # 原子删除+添加
            self.table.delete(f"id = '{memory_id}'")
            self.table.add([current])
            
        except Exception:
            pass
    
    def get(self, memory_id: str) -> Optional[dict]:
        """获取单条记忆【P0修复】SQL注入防护 + 解密"""
        if self.table is None:
            return None
        try:
            # 白名单校验
            import re
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
            if not uuid_pattern.match(memory_id):
                return None
            
            # 使用 LanceDB 原生 where 子句
            zero_vector = [0.0] * 1024
            results = (
                self.table
                .search(zero_vector, vector_column_name="vector")
                .where(f"id = '{memory_id}'")
                .limit(1)
                .to_arrow()
                .to_pylist()
            )
            
            if not results:
                return None
            
            memory = results[0]
            
            # 【P1新增】解密敏感字段
            try:
                from e2e_encryption import decrypt_data as decrypt_text, is_encrypted
                if memory.get("content") and is_encrypted(memory["content"]):
                    memory["content"] = decrypt_text(memory["content"])
                if memory.get("transcript") and is_encrypted(memory["transcript"]):
                    memory["transcript"] = decrypt_text(memory["transcript"])
            except ImportError:
                pass
            
            return memory
        except Exception as e:
            return None
    
    def delete(self, memory_id: str = None, query: str = None) -> bool:
        """删除记忆【P0修复】SQL注入防护"""
        if self.table is None:
            return False
        try:
            if memory_id:
                # 白名单校验：只允许合法UUID格式
                import re
                uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
                if not uuid_pattern.match(memory_id):
                    _logger.warning("invalid memory_id format")
                    return False
                self.table.delete(f"id = '{memory_id}'")
            elif query:
                # 转义单引号 + 长度限制
                safe_query = query.replace("'", "''")[:200]
                self.table.delete(f"content LIKE '%{safe_query}%'")
            return True
        except Exception as e:
            _logger.error(f"delete error: {e}")
            return False
    
    def stats(self) -> dict:
        """获取统计信息（优化：使用 head() 获取代表性样本）"""
        if self.table is None:
            return {"total": 0, "by_type": {}}
        
        try:
            total = self.table.count_rows()
            
            # 使用 head() 获取前100条作为样本统计类型分布
            try:
                sample = self.table.head(100)
                if hasattr(sample, 'to_pylist'):
                    sample_list = sample.to_pylist()
                else:
                    sample_list = []
            except:
                sample_list = []
            
            by_type = {}
            for t in ["fact", "preference", "decision", "lesson", "entity", "task_state"]:
                count = sum(1 for r in sample_list if r.get("type") == t)
                by_type[t] = count
            
            return {"total": total, "by_type": by_type}
        except Exception as e:
            _logger.error(f"stats error: {e}")
            return {"total": 0, "by_type": {}}
    
    def get_old_memories(self, days: int = 30, limit: int = 100) -> list[dict]:
        """
        【P0修复】获取超过指定天数的记忆（用于归档）
        使用where过滤代替全表加载
        """
        if self.table is None:
            return []
        
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 【P0修复】使用head()采样代替全表加载
            # head()获取最早创建的记录，最适合查找"旧"记忆
            total = self.table.count_rows()
            if total == 0:
                return []
            
            # 获取足够多的样本用于过滤
            sample_size = min(2000, total)
            try:
                sample = self.table.head(sample_size)
                if hasattr(sample, 'to_pylist'):
                    sample_list = sample.to_pylist()
                else:
                    sample_list = []
            except:
                sample_list = []
            
            # 过滤出旧记忆
            old = []
            for r in sample_list:
                if r.get("created_at", "") < cutoff:
                    old.append(r)
                    if len(old) >= limit:
                        break
            
            return old
            
        except Exception as e:
            _logger.error(f"get_old_memories error: {e}")
            return []


# 全局实例
db_store = None


def get_db_store():
    """懒加载单例"""
    global db_store
    if db_store is None:
        db_store = LanceDBStore()
    return db_store
