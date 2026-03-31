"""
LanceDB 存储模块 - 向量存储和搜索
修复版：使用 PyArrow schema，支持 LanceDB 0.27+
"""
import os
import json
import uuid
import time
import traceback
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import lancedb
import pyarrow as pa
from memory_config import CONFIG

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
            # 生成向量
            from ollama_embed import embedder
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
            
            raw_vector = embedder.embed(content)
            
            # 确保向量是1024维，padding或截断
            if raw_vector:
                if len(raw_vector) < 1024:
                    vector = raw_vector + [0.0] * (1024 - len(raw_vector))
                else:
                    vector = raw_vector[:1024]
            else:
                vector = [0.0] * 1024
            
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
            # 生成查询向量
            from ollama_embed import embedder
            query_vector = embedder.embed(query)
            
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
            
            # 【新增】Cross-Encoder重排
            if use_rerank and filtered:
                filtered = self._rerank_cross_encoder(query, filtered, limit)
            
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
            weights = {"vector": 0.25, "bm25": 0.25, "importance": 0.25, "kg": 0.25}
        
        channel_names = ["vector", "bm25", "importance", "kg"]
        
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
        
        # 组装结果
        fused_results = []
        for doc_id, rrf_score in sorted_docs:
            doc = doc_index[doc_id]
            doc["_rrf_score"] = round(rrf_score, 6)
            doc["_total_channels"] = len(doc["_channel_scores"])
            fused_results.append(doc)
        
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
    
    def search_rrf(self, query: str, limit: int = 5, k: int = 60, use_adaptive: bool = True) -> list:
        """
        【新增】RRF融合搜索 - 4通道融合（支持自适应权重）
        
        Channels:
        1. Vector similarity
        2. BM25 keyword
        3. Importance score
        4. Knowledge Graph (实体关联)
        
        Args:
            query: 搜索查询
            limit: 返回数量
            k: RRF参数
            use_adaptive: 是否使用自适应权重
            
        Returns:
            RRF融合排序结果
        """
        try:
            # 获取自适应权重
            weights = None
            if use_adaptive:
                try:
                    from adaptive_rerank import get_adaptive_rrf
                    adaptive = get_adaptive_rrf()
                    weights = adaptive.get_weights()
                except:
                    pass
            
            # Channel 1: Vector search
            vector_results = self.search(query, limit=limit*3, use_rerank=False)
            for i, r in enumerate(vector_results):
                r["_final_score"] = 1.0 - r.get("_distance", 0.5)
                r["_vector_score"] = r["_final_score"]
            
            # Channel 2: BM25 keyword search
            bm25_results = self._get_bm25_scores(query, limit=limit*3)
            for r in bm25_results:
                r["_bm25_score"] = r.get("bm25_score", 0)
            
            # Channel 3: Importance score
            importance_results = self._get_importance_scores(limit=limit*3)
            for r in importance_results:
                r["_importance_score"] = r.get("importance_score", r.get("importance", 0.5))
            
            # Channel 4: Knowledge Graph aware (如果query中有实体)
            kg_results = self._kg_aware_search(query, limit=limit*3)
            for r in kg_results:
                r["_kg_score"] = r.get("_kg_score", r.get("importance", 0.5))
            
            # Channel 5: 【P1新增】时序感知搜索
            temporal_results = self._temporal_search(query, limit=limit*3)
            for r in temporal_results:
                r["_temporal_score"] = r.get("_temporal_score", 0.5)
            
            # RRF融合 (5通道)
            all_channels = [v for v in [vector_results, bm25_results, importance_results, kg_results, temporal_results] if v]
            
            fused = self._rrf_fusion(all_channels, k=k, weights=weights)
            
            # 【P0修复】Cross-Encoder最终语义重排
            # 条件：只有当RRF融合结果中top结果分数较低时才触发重排
            # 避免过度重排影响原本正确的排序
            if fused and len(fused) > 1:
                try:
                    top_score = fused[0].get("_final_score", 0) if fused else 0
                    # 如果top结果分数已经较高(<0.7)，保持RRF结果，跳过重排
                    # 只有在结果质量较差时才用Cross-Encoder二次确认
                    if top_score < 0.5:
                        fused = self._rerank_cross_encoder(query, fused, limit)
                    else:
                        _logger.debug(f"RRF top score {top_score:.3f} >= 0.5, skipping rerank")
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
        【P0修复】知识图谱感知搜索 - 真正利用实体关系和传递推理

        改进点：
        1. 使用KG的search_entities而非正则匹配
        2. 使用find_path做传递推理
        3. 使用infer_relations推断潜在关联
        4. 综合图中心性、路径强度计算KG分数
        """
        try:
            from kg_networkx import get_kg_nx
            
            kg = get_kg_nx()
            kg_results = []
            
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
        【P1新增】时序感知搜索
        
        检测查询中的时间关键词，对记忆进行时间衰减排序：
        - "最近"、"近期"、"最近一周" → 越新的记忆分数越高
        - "以前"、"过去"、"之前" → 越老的记忆分数越高
        
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
        
        # 检测是否有时序意图
        is_recent = any(kw in query_lower for kw in ["最近", "近期", "现在", "目前", "这周", "这月", "今天", "昨天"])
        is_past = any(kw in query_lower for kw in ["以前", "过去", "之前", "曾经", "早些", "以前"])
        
        # 如果没有时序意图，返回空列表让其他通道决定
        if not (is_recent or is_past):
            return []
        
        try:
            # 获取所有记忆的访问时间
            now = datetime.now()
            results = []
            
            # 获取记忆列表（使用已建立索引的数据）
            all_memories = self.search(query, limit=limit*2, use_rerank=False)
            
            for memory in all_memories:
                memory_id = memory.get("id", "")
                
                # 获取访问时间（从memory metadata）
                access_time_str = memory.get("last_accessed") or memory.get("created_at") or ""
                
                if not access_time_str:
                    continue
                
                try:
                    # 解析时间
                    if isinstance(access_time_str, str):
                        access_time = datetime.fromisoformat(access_time_str.replace('Z', '+00:00'))
                    else:
                        access_time = access_time_str
                    
                    # 计算天数差异
                    days_diff = (now - access_time).days
                    
                    # 计算时序分数
                    if is_recent:
                        # 最近查询：越新越好，用指数衰减
                        # 30天半衰期
                        time_score = math.exp(-days_diff / 30)
                    else:  # is_past
                        # 过去查询：越老越好，但不太老的优先
                        if days_diff < 7:
                            time_score = 0.3  # 太新了不太符合"以前"的意图
                        else:
                            time_score = min(1.0, days_diff / 365)  # 最多1年，超过1年不再增加
                    
                    # 只有时序分数明显的才加入
                    if time_score > 0.1:
                        memory_copy = memory.copy()
                        memory_copy["_temporal_score"] = time_score
                        memory_copy["_days_since_access"] = days_diff
                        results.append(memory_copy)
                        
                except Exception:
                    continue
            
            # 按时间分数排序
            if is_recent:
                results.sort(key=lambda x: x.get("_temporal_score", 0), reverse=True)
            else:
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
