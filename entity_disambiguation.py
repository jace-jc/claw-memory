"""
实体消歧模块 - Entity Disambiguation
使用LLM判断实体是否指代同一对象，并自动合并
"""
import json
import requests
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
from memory_config import CONFIG


class EntityDisambiguator:
    """
    实体消歧器
    
    功能：
    1. 判断两个实体是否指代同一对象
    2. 维护实体等价类（Equivalence Classes）
    3. 自动合并重复实体
    """
    
    def __init__(self):
        self.ollama_url = CONFIG.get("ollama_url", "http://localhost:11434")
        self.llm_model = CONFIG.get("llm_model", "qwen3.5:27b")
        self.similarity_threshold = 0.75  # 消歧阈值
    
    def judge_entities_same(self, entity1: str, entity2: str, context: str = "") -> Tuple[bool, float]:
        """
        判断两个实体是否指代同一对象
        
        Args:
            entity1: 实体1名称
            entity2: 实体2名称  
            context: 可选的上下文信息
            
        Returns:
            (是否相同, 置信度)
        """
        prompt = f"""判断两个实体名称是否指代同一个对象。

实体1: {entity1}
实体2: {entity2}
上下文: {context if context else "无"}

判断标准：
- 完全相同或明显是同一对象的不同表述 → 是
- 包含关系（如"清华大学"和"清华"）→ 是
- 完全不同或矛盾 → 否

回答格式（只输出JSON）：
{{"same": true/false, "confidence": 0.0-1.0, "reason": "简短原因"}}

答案："""
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 100}
                },
                timeout=30
            )
            
            result_data = response.json()
            content = result_data.get("message", {}).get("content", "")
            
            # 解析JSON响应
            import re
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                same = data.get("same", False)
                confidence = float(data.get("confidence", 0.5))
                return same, confidence
            
            return False, 0.5
            
        except Exception as e:
            print(f"[EntityDisambiguator] judge error: {e}")
            # 默认返回不确定
            return False, 0.5
    
    def find_similar_entities(self, entity_name: str, candidates: List[Dict]) -> List[Dict]:
        """
        在候选实体中找到与给定实体相似的
        
        Args:
            entity_name: 要查找的实体名
            candidates: 候选实体列表 [{"name": "...", "type": "...", ...}]
            
        Returns:
            相似实体列表
        """
        similar = []
        
        for candidate in candidates:
            candidate_name = candidate.get("name", "")
            
            # 快速过滤：完全相同
            if entity_name == candidate_name:
                similar.append((candidate, 1.0, "exact"))
                continue
            
            # 快速过滤：包含关系
            if entity_name in candidate_name or candidate_name in entity_name:
                if len(candidate_name) > 2 and len(entity_name) > 2:
                    similar.append((candidate, 0.85, "substring"))
                    continue
            
            # LLM判断
            same, confidence = self.judge_entities_same(entity_name, candidate_name)
            if same and confidence >= self.similarity_threshold:
                similar.append((candidate, confidence, "llm"))
        
        # 按置信度排序
        similar.sort(key=lambda x: x[1], reverse=True)
        
        return [(c, conf, method) for c, conf, method in similar]
    
    def disambiguate_and_merge(self, entity_name: str, entity_type: str,
                               memory_id: str, existing_entities: List[Dict]) -> Dict:
        """
        消歧并合并实体
        
        Args:
            entity_name: 新实体名
            entity_type: 实体类型
            memory_id: 关联的记忆ID
            existing_entities: 知识图谱中已有的实体
            
        Returns:
            {"action": "merged"|"new"|"skip", "entity_id": "...", "merged_into": "..."}
        """
        if not existing_entities:
            # 创建新实体
            return {"action": "new", "entity_id": None, "entity_name": entity_name}
        
        # 找相似实体
        similar = self.find_similar_entities(entity_name, existing_entities)
        
        if not similar:
            # 没有相似实体，创建新实体
            return {"action": "new", "entity_id": None, "entity_name": entity_name}
        
        # 合并到最相似的实体
        best_match, confidence, method = similar[0]
        
        if confidence >= self.similarity_threshold:
            return {
                "action": "merged",
                "entity_id": best_match.get("id"),
                "entity_name": best_match.get("name"),
                "confidence": confidence,
                "method": method
            }
        
        return {"action": "new", "entity_id": None, "entity_name": entity_name}
    
    def build_equivalence_class(self, entities: List[Dict]) -> Dict[str, List[str]]:
        """
        从实体列表构建等价类
        
        用于将指代同一对象的实体归为一类
        
        Returns:
            {canonical_name: [alias1, alias2, ...]}
        """
        # 使用并查集思想
        parent = {}  # entity -> parent entity
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])  # 路径压缩
            return parent[x]
        
        def union(x, y, same: bool):
            """如果same=True，合并x和y"""
            if not same:
                return
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # 两两比较
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                name1, name2 = e1.get("name", ""), e2.get("name", "")
                same, _ = self.judge_entities_same(name1, name2)
                union(name1, name2, same)
        
        # 构建等价类
        classes = defaultdict(list)
        for e in entities:
            name = e.get("name", "")
            p = find(name)
            if p not in classes:
                classes[p] = []
            classes[p].append(name)
        
        return dict(classes)


# 全局实例
_disambiguator = None


def get_disambiguator() -> EntityDisambiguator:
    """获取消歧器实例"""
    global _disambiguator
    if _disambiguator is None:
        _disambiguator = EntityDisambiguator()
    return _disambiguator
