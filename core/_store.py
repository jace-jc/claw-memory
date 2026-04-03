"""
Store method for LanceDBStore
Phase 2: Split from lancedb_store.py
"""
import json
import uuid
import traceback
from datetime import datetime
from typing import Union

_logger = __import__('logging').getLogger("ClawMemory")


def store(self, memory: dict, skip_dedup: bool = False, skip_post_processing: bool = False) -> Union[str, bool]:
    """存储记忆
    
    Args:
        memory: 记忆字典
        skip_dedup: 是否跳过去重检查（用于benchmark等场景，避免误判）
        skip_post_processing: 是否跳过存储后处理（矛盾检测/双缓冲注册），用于benchmark隔离测试
    
    Returns:
        成功返回记忆ID（str），失败返回False
        注意：返回ID时仍然是truthy，原有 `if store():` 判断不受影响
    """
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
        
        # 【v2.9 P0新增】记忆质量过滤：去噪 + 阈值强制化
        try:
            from denoise_filter import should_store_memory, get_importance_threshold
            
            # 检查是否应该存储
            importance_in = float(memory.get("importance", 0.5))
            confidence_in = float(memory.get("confidence", 0.8))
            source_in = memory.get("source", "")
            
            should_store, filter_reason = should_store_memory(
                content, importance_in, confidence_in, source_in
            )
            
            if not should_store:
                _logger.info(f"[质量过滤] 拒绝存储: {filter_reason}")
                return False
            
            # 重要性阈值强制化
            threshold = get_importance_threshold()
            storage_tier = threshold.classify(importance_in)
            
            if storage_tier == "discard":
                _logger.info(f"[质量过滤] 重要性{importance_in:.2f}低于阈值，直接丢弃")
                return False
            
            # 标记存储层级
            memory["_storage_tier"] = storage_tier
            
        except ImportError:
            pass  # 过滤器不可用，跳过检查
        
        # 【v2.9 P0新增】recall防幻觉检查：如果内容刚被召回，则跳过存储
        try:
            from recall_guard import is_content_recalled, mark_content_recalled
            
            if is_content_recalled(content):
                _logger.info(f"[Recall Guard] 跳过已recall内容（防幻觉放大）: {content[:50]}...")
                return False
            
        except ImportError:
            pass  # recall_guard不可用，跳过检查
        
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
        
        # 【v3.1 P0-B新增】Weibull衰减字段
        try:
            from weibull_decay import WeibullDecayModel
            decay_model = WeibullDecayModel()
            initial_decay_score = decay_model.get_current_importance(memory.get("id", ""))
            if initial_decay_score is None:
                initial_decay_score = importance
        except ImportError:
            initial_decay_score = importance  # fallback
        
        # 【v3.1 P0-E新增】作用域隔离
        scope = memory.get("scope", "global")
        scope_id = memory.get("scope_id", "")
        
        # 构建record（根据实际schema添加字段）
        record = {
            "id": memory.get("id", str(uuid.uuid4())),
            "type": memory.get("type", "fact"),
            "content": content,
            "summary": memory.get("summary", ""),
            "importance": importance,
            "source": memory.get("source", ""),
            "transcript": memory.get("transcript", ""),
            "tags": json.dumps(memory.get("tags", [])),
            "scope": scope,
            "scope_id": scope_id,
            "vector": vector,
            "created_at": memory.get("created_at", now),
            "updated_at": now,
            "last_accessed": now,
            "access_count": 1,
            "revision_chain": json.dumps(memory.get("revision_chain", [])),
            "superseded_by": memory.get("superseded_by", ""),
        }
        
        # 【v3.1 P0-B/Fix】确保decay_score/decay_rate字段存在
        try:
            if self.table is not None:
                schema = self.table.schema
                field_names = [f.name for f in schema]
                
                # 如果缺少decay_score字段，添加到schema
                if "decay_score" not in field_names:
                    self.table.add_columns([
                        ("decay_score", "float"),
                        ("decay_rate", "float")
                    ])
                    _logger.debug("[Weibull] 已添加decay_score/decay_rate字段")
                
                # 添加到record
                record["decay_score"] = initial_decay_score
                record["decay_rate"] = memory.get("decay_rate", 0.5)
        except Exception as e:
            _logger.debug(f"[Weibull] 字段添加跳过: {e}")
        
        # 【P2新增】两阶段去重检查（skip_dedup=True时跳过，用于benchmark）
        if not skip_dedup:
            from two_stage_dedup import DedupDecision
            dedup_result = self._dedup.check(content, memory.get("type"))
            if dedup_result.decision == DedupDecision.SKIP:
                _logger.info(f"[TwoStageDedup] 跳过重复内容: {dedup_result.reason}")
                return False
            elif dedup_result.decision == DedupDecision.MERGE:
                _logger.info(f"[TwoStageDedup] 合并到已有记忆: {dedup_result.matched_memory_id}")
                # 记录合并到WAL
                self._wal.add_decision(f"MERGE memory {record['id']} into {dedup_result.matched_memory_id}")
                # 对于MERGE，更新已有记忆而非添加新记录
                try:
                    self._update_memory_content(dedup_result.matched_memory_id, content)
                    return True
                except Exception:
                    pass  # 合并失败则继续创建
        
        # 【P2新增】WAL预写日志
        try:
            self._wal.set_current_task(f"store memory {record['id']}")
            self._wal.update_context(f"Storing {memory.get('type', 'fact')}: {content[:100]}...")
        except Exception:
            pass
        
        self.table.add([record])
        
        # 更新去重器内存
        self._dedup.add_memory({"id": record["id"], "content": content})
        
        # 【v2.9 P0新增】存储后处理：矛盾检测 + 双缓冲注册（benchmark时跳过）
        if not skip_post_processing:
            try:
                from denoise_filter import check_contradiction, register_stored_memory
                from recall_extraction_isolation import get_recall_extraction_isolation
                
                # 1. 矛盾检测
                contradiction = check_contradiction(content, memory.get("type"))
                if contradiction:
                    _logger.info(f"[矛盾检测] 检测到矛盾: old={contradiction.get('old_memory',{}).get('content','')[:50]}...")
                
                # 2. 注册到矛盾检测器
                register_stored_memory(memory)
                
                # 3. 注册到双缓冲提取池
                isolation = get_recall_extraction_isolation()
                isolation.store_with_isolation(memory)
                
            except ImportError:
                pass
        
        return record["id"]  # 返回记忆ID，便于后续引用（如删除）
    except Exception as e:
        _logger.error(f"store error: {e}")
        import traceback
        traceback.print_exc()
        return False
