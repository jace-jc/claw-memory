"""
KG填充工具 - 从已有记忆提取实体填充知识图谱

功能：
1. 从记忆内容中提取实体
2. 构建实体关系
3. 填充知识图谱
"""

from typing import List, Dict, Set
from kg_networkx import get_kg_nx
from lancedb_store import LanceDBStore
from chinese_extract import get_chinese_extractor


def populate_kg_from_memories(limit: int = 100, dry_run: bool = False) -> Dict:
    """
    从已有记忆提取实体填充知识图谱
    
    Args:
        limit: 处理的最大记忆数量
        dry_run: 如果为True，只分析不写入
    
    Returns:
        填充统计
    """
    print(f"[KG Populator] 开始填充KG (limit={limit}, dry_run={dry_run})")
    
    db = LanceDBStore()
    kg = get_kg_nx()
    extractor = get_chinese_extractor()
    
    # 获取所有记忆（使用通用词搜索，避免空查询）
    # 注意：实际应用中应该通过table.scan()获取所有记忆
    memories = db.search("用户", limit=limit)  # 获取前N条记忆
    
    stats = {
        "total_memories": len(memories),
        "entities_extracted": 0,
        "entities_added": 0,
        "relations_extracted": 0,
        "relations_added": 0,
        "errors": []
    }
    
    # 已处理的实体名（避免重复）
    seen_entities: Set[str] = set()
    
    for mem in memories:
        content = mem.get("content", "")
        if not content:
            continue
        
        try:
            # 提取实体
            extracted = extractor.extract(content)
            entities = extracted.get("entities", [])
            relations = extracted.get("relations", [])
            
            stats["entities_extracted"] += len(entities)
            stats["relations_extracted"] += len(relations)
            
            if dry_run:
                continue
            
            # 添加实体到KG
            for entity in entities:
                name = entity.get("name", "")
                if not name or name in seen_entities:
                    continue
                
                seen_entities.add(name)
                entity_type = entity.get("type", "concept")
                
                try:
                    kg.add_entity(name, entity_type=entity_type, properties=entity)
                    stats["entities_added"] += 1
                except Exception as e:
                    if "already exists" not in str(e):
                        stats["errors"].append(f"Entity error: {e}")
            
            # 添加关系到KG
            for relation in relations:
                from_entity = relation.get("from", "")
                to_entity = relation.get("to", "")
                rel_type = relation.get("type", "related_to")
                
                if not from_entity or not to_entity:
                    continue
                
                try:
                    kg.add_relation(from_entity, to_entity, relation_type=rel_type)
                    stats["relations_added"] += 1
                except Exception as e:
                    if "already exists" not in str(e):
                        stats["errors"].append(f"Relation error: {e}")
                        
        except Exception as e:
            stats["errors"].append(f"Memory error: {e}")
            continue
    
    print(f"[KG Populator] 完成!")
    print(f"  处理记忆: {stats['total_memories']}")
    print(f"  提取实体: {stats['entities_extracted']}")
    print(f"  添加实体: {stats['entities_added']}")
    print(f"  提取关系: {stats['relations_extracted']}")
    print(f"  添加关系: {stats['relations_added']}")
    if stats["errors"]:
        print(f"  错误: {len(stats['errors'])}")
    
    return stats


def extract_entities_from_text(text: str) -> List[Dict]:
    """
    从文本中提取实体（简单封装）
    """
    extractor = get_chinese_extractor()
    extracted = extractor.extract(text)
    return extracted.get("entities", [])


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv
    limit = 100
    
    if "--help" in sys.argv:
        print("Usage: python kg_populator.py [--dry-run] [--limit N]")
        print("  --dry-run: 只分析不写入")
        print("  --limit N: 处理的最大记忆数量 (默认100)")
        sys.exit(0)
    
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    
    populate_kg_from_memories(limit=limit, dry_run=dry_run)
