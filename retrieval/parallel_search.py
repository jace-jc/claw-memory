"""
并行通道搜索 - Parallel Channel Search
5个RRF通道并行召回，减少总延迟

原理：
- 原有架构：5个通道串行执行，延迟累加
- 优化架构：5个通道并行执行，取并集后RRF融合
- 预计节省 60% 时间

通道：
1. Vector（向量相似度）
2. BM25（关键词匹配）
3. Importance（重要性分数）
4. KG（知识图谱关联）
5. Temporal（时序）

两阶段检索：
- Stage 1: 并行召回TOP-N候选
- Stage 2: Cross-Encoder重排TOP-M
"""
import time
import asyncio
import json
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# 默认配置
DEFAULT_TOP_N = 20        # 每个通道召回TOP-N
DEFAULT_TOP_M = 10        # 最终返回TOP-M
DEFAULT_PARALLEL = True   # 默认开启并行
DEFAULT_TIMEOUT = 3.0     # 单通道超时（秒）


class ParallelChannelSearch:
    """
    并行通道搜索引擎
    
    核心优化：
    1. 多通道并行召回（ThreadPoolExecutor）
    2. 超时控制（防止单通道拖慢整体）
    3. 结果合并与去重
    4. 两阶段检索（召回→重排）
    """
    
    def __init__(
        self,
        top_n: int = DEFAULT_TOP_N,
        top_m: int = DEFAULT_TOP_M,
        parallel: bool = DEFAULT_PARALLEL,
        timeout: float = DEFAULT_TIMEOUT
    ):
        self.top_n = top_n
        self.top_m = top_m
        self.parallel = parallel
        self.timeout = timeout
        
        # 通道权重（RRF融合用）
        self.channel_weights = {
            "vector": 0.35,
            "bm25": 0.25,
            "importance": 0.20,
            "kg": 0.12,
            "temporal": 0.08
        }
    
    def _search_vector(self, query: str, top_k: int) -> List[Dict]:
        """通道1: 向量相似度搜索"""
        try:
            from lancedb_store import get_db_store
            db = get_db_store()
            results = db.search(query, limit=top_k * 2)  # 多召回一些，后面会合并
            
            for r in results:
                r["_vector_score"] = r.get("score", 0)
                r["_channel"] = "vector"
            
            return results
        except Exception as e:
            print(f"[ParallelSearch] Vector搜索失败: {e}")
            return []
    
    def _search_bm25(self, query: str, top_k: int) -> List[Dict]:
        """通道2: BM25关键词搜索"""
        try:
            from retrieval.bm25_search import get_bm25_search
            from lancedb_store import get_db_store
            
            # 获取记忆数据
            db = get_db_store()
            if db.table is None:
                return []
            
            total = db.table.count_rows()
            sample_size = min(1000, total)
            sample = db.table.head(sample_size)
            memories = sample.to_pylist() if hasattr(sample, 'to_pylist') else []
            
            # 使用BM25搜索
            bm25 = get_bm25_search(memories)
            results = bm25.search(query, top_k=top_k * 2)
            
            for r in results:
                r["_bm25_score"] = r.get("score", 0)
                r["_channel"] = "bm25"
            
            return results
        except Exception as e:
            print(f"[ParallelSearch] BM25搜索失败: {e}")
            return []
    
    def _search_importance(self, query: str, top_k: int) -> List[Dict]:
        """通道3: 重要性分数搜索"""
        try:
            from lancedb_store import get_db_store
            db = get_db_store()
            
            if db.table is None:
                return []
            
            # 获取样本并按重要性排序
            total = db.table.count_rows()
            sample_size = min(1000, total)
            sample = db.table.head(sample_size)
            results = sample.to_pylist() if hasattr(sample, 'to_pylist') else []
            
            # 按重要性排序取TOP-K
            results.sort(key=lambda x: x.get("importance", 0), reverse=True)
            results = results[:top_k * 2]
            
            for r in results:
                r["_importance_score"] = r.get("importance", 0)
                r["_channel"] = "importance"
            
            return results
        except Exception as e:
            print(f"[ParallelSearch] Importance搜索失败: {e}")
            return []
    
    def _search_kg(self, query: str, top_k: int) -> List[Dict]:
        """通道4: 知识图谱关联搜索"""
        try:
            from memory.kg_networkx import KnowledgeGraphNX
            kg = KnowledgeGraphNX()
            
            # 提取查询中的实体
            entities = kg.extract_entities(query)
            
            # 查询相关记忆
            results = []
            for entity in entities[:5]:  # 最多5个实体
                related = kg.get_related_memories(entity, depth=2, limit=top_k // 2)
                results.extend(related)
            
            # 去重
            seen = set()
            unique_results = []
            for r in results:
                rid = r.get("id", "")
                if rid and rid not in seen:
                    seen.add(rid)
                    unique_results.append(r)
            
            for r in unique_results[:top_k * 2]:
                r["_kg_score"] = r.get("kg_score", 0.5)
                r["_channel"] = "kg"
            
            return unique_results[:top_k * 2]
        except Exception as e:
            print(f"[ParallelSearch] KG搜索失败: {e}")
            return []
    
    def _search_temporal(self, query: str, top_k: int) -> List[Dict]:
        """通道5: 时序搜索"""
        try:
            from lancedb_store import get_db_store
            db = get_db_store()
            
            if db.table is None:
                return []
            
            # 获取记忆并按创建时间排序
            total = db.table.count_rows()
            sample_size = min(1000, total)
            sample = db.table.head(sample_size)
            results = sample.to_pylist() if hasattr(sample, 'to_pylist') else []
            
            # 按created_at降序排序
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            results = results[:top_k * 2]
            
            for r in results:
                r["_temporal_score"] = r.get("recency_score", 0)
                r["_channel"] = "temporal"
            
            return results
        except Exception as e:
            print(f"[ParallelSearch] Temporal搜索失败: {e}")
            return []
    
    def _merge_results(self, channel_results: Dict[str, List[Dict]]) -> List[Dict]:
        """
        合并多通道结果
        
        策略：
        1. 取所有通道结果的并集
        2. 同一记忆保留得分最高的通道分数
        3. 计算RRF融合分数
        """
        # 合并去重
        memory_map = {}
        
        for channel, results in channel_results.items():
            for r in results:
                memory_id = r.get("id", r.get("memory_id", ""))
                if not memory_id:
                    continue
                
                if memory_id not in memory_map:
                    memory_map[memory_id] = {
                        "id": memory_id,
                        "content": r.get("content", ""),
                        "type": r.get("type", "fact"),
                        "importance": r.get("importance", 0.5),
                        "created_at": r.get("created_at", ""),
                        "_channels": []
                    }
                
                # 保留各通道分数
                score_field = f"_channel_score"
                if channel == "vector":
                    memory_map[memory_id]["_vector_score"] = r.get("_vector_score", 0)
                    memory_map[memory_id]["_channel"] = "vector"
                elif channel == "bm25":
                    memory_map[memory_id]["_bm25_score"] = r.get("_bm25_score", 0)
                elif channel == "importance":
                    memory_map[memory_id]["_importance_score"] = r.get("_importance_score", 0)
                elif channel == "kg":
                    memory_map[memory_id]["_kg_score"] = r.get("_kg_score", 0)
                elif channel == "temporal":
                    memory_map[memory_id]["_temporal_score"] = r.get("_temporal_score", 0)
                
                memory_map[memory_id]["_channels"].append(channel)
        
        # 计算RRF融合分数
        merged_results = []
        for memory_id, mem in memory_map.items():
            rrf_score = self._compute_rrf_score(mem)
            mem["_rrf_score"] = rrf_score
            merged_results.append(mem)
        
        # 按RRF分数排序
        merged_results.sort(key=lambda x: x.get("_rrf_score", 0), reverse=True)
        
        return merged_results[:self.top_n * 2]  # 返回2倍，后续重排
    
    def _compute_rrf_score(self, memory: Dict) -> float:
        """
        计算RRF融合分数
        
        RRF(k) = Σ 1/(k + rank_i)
        
        使用自适应权重替代固定k
        """
        k = 60  # RRF默认参数
        
        total_score = 0.0
        
        # Vector通道
        if "_vector_score" in memory:
            rank = 1  # 简化处理
            weight = self.channel_weights.get("vector", 0.3)
            total_score += weight * (1.0 / (k + rank)) * memory["_vector_score"]
        
        # BM25通道
        if "_bm25_score" in memory:
            rank = 1
            weight = self.channel_weights.get("bm25", 0.25)
            total_score += weight * (1.0 / (k + rank)) * memory["_bm25_score"]
        
        # Importance通道
        if "_importance_score" in memory:
            rank = 1
            weight = self.channel_weights.get("importance", 0.2)
            total_score += weight * (1.0 / (k + rank)) * memory["_importance_score"]
        
        # KG通道
        if "_kg_score" in memory:
            rank = 1
            weight = self.channel_weights.get("kg", 0.15)
            total_score += weight * (1.0 / (k + rank)) * memory["_kg_score"]
        
        # Temporal通道
        if "_temporal_score" in memory:
            rank = 1
            weight = self.channel_weights.get("temporal", 0.1)
            total_score += weight * (1.0 / (k + rank)) * memory["_temporal_score"]
        
        # 归一化
        total_weight = sum(self.channel_weights.values())
        if total_weight > 0:
            total_score /= total_weight
        
        return total_score
    
    def search_parallel(self, query: str) -> Tuple[List[Dict], Dict]:
        """
        并行搜索主入口
        
        Args:
            query: 查询字符串
            
        Returns:
            (results, stats)
        """
        start_time = time.time()
        channel_times = {}
        
        if self.parallel:
            # 并行执行5个通道
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(self._search_vector, query, self.top_n): "vector",
                    executor.submit(self._search_bm25, query, self.top_n): "bm25",
                    executor.submit(self._search_importance, query, self.top_n): "importance",
                    executor.submit(self._search_kg, query, self.top_n): "kg",
                    executor.submit(self._search_temporal, query, self.top_n): "temporal",
                }
                
                channel_results = {}
                for future in as_completed(futures, timeout=self.timeout * 5):
                    channel = futures[future]
                    try:
                        results = future.result()
                        channel_results[channel] = results
                        channel_times[channel] = time.time() - start_time
                    except Exception as e:
                        print(f"[ParallelSearch] {channel} 通道异常: {e}")
                        channel_results[channel] = []
        else:
            # 串行执行（备用）
            channel_results = {}
            for channel, search_fn in [
                ("vector", lambda: self._search_vector(query, self.top_n)),
                ("bm25", lambda: self._search_bm25(query, self.top_n)),
                ("importance", lambda: self._search_importance(query, self.top_n)),
                ("kg", lambda: self._search_kg(query, self.top_n)),
                ("temporal", lambda: self._search_temporal(query, self.top_n)),
            ]:
                t0 = time.time()
                channel_results[channel] = search_fn()
                channel_times[channel] = time.time() - t0
        
        # 合并结果
        merge_start = time.time()
        merged = self._merge_results(channel_results)
        merge_time = time.time() - merge_start
        
        # 两阶段检索：Cross-Encoder重排
        rerank_start = time.time()
        final_results = self._apply_reranking(query, merged[:self.top_n])
        rerank_time = time.time() - rerank_start
        
        total_time = time.time() - start_time
        
        # 应用Weibull衰减
        try:
            from memory.weibull_decay import apply_decay_to_search_results
            final_results = apply_decay_to_search_results(final_results)
        except ImportError:
            pass
        
        stats = {
            "total_time_ms": round(total_time * 1000, 1),
            "channel_times": {k: round(v * 1000, 1) for k, v in channel_times.items()},
            "merge_time_ms": round(merge_time * 1000, 1),
            "rerank_time_ms": round(rerank_time * 1000, 1),
            "channels_used": list(channel_results.keys()),
            "candidates_before_rerank": len(merged),
            "results_returned": len(final_results),
            "parallel_enabled": self.parallel
        }
        
        return final_results[:self.top_m], stats
    
    def _apply_reranking(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """应用Cross-Encoder重排"""
        if not candidates:
            return []
        
        try:
            from retrieval.cross_encoder_rerank import get_reranker
            reranker = get_reranker()
            
            if reranker.is_available():
                return reranker.rerank(query, candidates, top_k=len(candidates))
        except ImportError:
            pass
        
        return candidates
    
    def search_with_cache(self, query: str, cache_ttl: int = 300) -> Tuple[List[Dict], Dict, bool]:
        """
        带缓存的搜索
        
        Args:
            query: 查询字符串
            cache_ttl: 缓存有效期（秒），默认5分钟
            
        Returns:
            (results, stats, cache_hit)
        """
        try:
            from retrieval.search_cache import get_cache
            cache = get_cache()
            
            # 尝试从缓存获取
            cached = cache.get(query)
            if cached:
                stats = cached.get("stats", {})
                stats["cache_hit"] = True
                return cached["results"], stats, True
            
            # 执行搜索
            results, stats = self.search_parallel(query)
            stats["cache_hit"] = False
            
            # 写入缓存
            cache.set(query, results, ttl=cache_ttl)
            
            return results, stats, False
            
        except ImportError:
            # 缓存不可用，降级到普通搜索
            results, stats = self.search_parallel(query)
            return results, stats, False
    
    def get_stats(self) -> Dict:
        """获取搜索统计"""
        return {
            "top_n": self.top_n,
            "top_m": self.top_m,
            "parallel_enabled": self.parallel,
            "timeout": self.timeout,
            "channel_weights": self.channel_weights
        }


# 全局实例
_parallel_searcher = None


def get_parallel_searcher() -> ParallelChannelSearch:
    """获取全局并行搜索器"""
    global _parallel_searcher
    if _parallel_searcher is None:
        _parallel_searcher = ParallelChannelSearch()
    return _parallel_searcher


# ============================================================
# 独立函数接口
# ============================================================

def search_parallel(query: str, top_k: int = 10) -> Tuple[List[Dict], Dict]:
    """
    并行通道搜索
    
    Example:
        >>> results, stats = search_parallel("用户的项目是什么")
        >>> print(f"耗时: {stats['total_time_ms']}ms, 命中: {len(results)}条")
    """
    searcher = get_parallel_searcher()
    searcher.top_m = top_k
    return searcher.search_parallel(query)


def search_with_cache(query: str, cache_ttl: int = 300) -> Tuple[List[Dict], Dict, bool]:
    """带缓存的并行搜索"""
    searcher = get_parallel_searcher()
    return searcher.search_with_cache(query, cache_ttl)


def benchmark_parallel_vs_serial(query: str, iterations: int = 3) -> Dict:
    """
    对比并行 vs 串行搜索性能
    
    Returns:
        性能对比报告
    """
    searcher = get_parallel_searcher()
    
    # 并行搜索
    parallel_times = []
    for _ in range(iterations):
        _, stats = searcher.search_parallel(query)
        parallel_times.append(stats["total_time_ms"])
    
    # 串行搜索
    serial_searcher = ParallelChannelSearch(parallel=False)
    serial_times = []
    for _ in range(iterations):
        _, stats = serial_searcher.search_parallel(query)
        serial_times.append(stats["total_time_ms"])
    
    avg_parallel = sum(parallel_times) / len(parallel_times)
    avg_serial = sum(serial_times) / len(serial_times)
    improvement = (avg_serial - avg_parallel) / avg_serial * 100
    
    return {
        "query": query,
        "iterations": iterations,
        "parallel_avg_ms": round(avg_parallel, 1),
        "serial_avg_ms": round(avg_serial, 1),
        "improvement_pct": round(improvement, 1),
        "speedup_x": round(avg_serial / avg_parallel, 2)
    }
