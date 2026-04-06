"""
知识图谱模块 - 记忆实体关系管理
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from collections import defaultdict
from core.memory_config import CONFIG


class KnowledgeGraph:
    """
    轻量级知识图谱 - 在 LanceDB 基础上构建实体关系网络
    """
    
    def __init__(self, kg_path: str = None):
        self.kg_path = kg_path or CONFIG.get("kg_path", 
            str(Path(CONFIG.get("memory_dir", "/Users/claw/.openclaw/workspace/memory")) / "knowledge_graph.json"))
        self._ensure_dir()
        self.graph = self._load_graph()
    
    def _ensure_dir(self):
        Path(self.kg_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _load_graph(self) -> dict:
        """加载知识图谱"""
        if Path(self.kg_path).exists():
            try:
                with open(self.kg_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"nodes": {}, "edges": []}
    
    def _save_graph(self):
        """保存知识图谱"""
        with open(self.kg_path, 'w', encoding='utf-8') as f:
            json.dump(self.graph, f, ensure_ascii=False, indent=2)
    
    def add_entity(self, name: str, entity_type: str, properties: dict = None) -> str:
        """
        添加实体节点
        
        Args:
            name: 实体名称
            entity_type: 实体类型 (person/company/project/tool/concept/location)
            properties: 实体属性
        """
        entity_id = f"entity_{uuid.uuid4().hex[:8]}"
        
        self.graph["nodes"][entity_id] = {
            "id": entity_id,
            "name": name,
            "type": entity_type,
            "properties": properties or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "mention_count": 1,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }
        
        self._save_graph()
        return entity_id
    
    def get_or_create_entity(self, name: str, entity_type: str = "concept", 
                            properties: dict = None) -> tuple[str, bool]:
        """
        获取或创建实体
        
        Returns:
            (entity_id, is_new)
        """
        # 查找已存在的同名实体
        for node_id, node in self.graph["nodes"].items():
            if node["name"] == name:
                # 更新属性和时间
                node["mention_count"] += 1
                node["last_seen"] = datetime.now().isoformat()
                if properties:
                    node["properties"].update(properties)
                node["updated_at"] = datetime.now().isoformat()
                self._save_graph()
                return node_id, False
        
        # 创建新实体
        entity_id = self.add_entity(name, entity_type, properties)
        return entity_id, True
    
    def add_relation(self, from_entity: str, to_entity: str, 
                     relation_type: str, properties: dict = None) -> str:
        """
        添加关系边
        
        Args:
            from_entity: 起始实体名
            to_entity: 目标实体名
            relation_type: 关系类型 (works_at/uses/created_by/lives_in/knows)
            properties: 关系属性
        """
        edge_id = f"edge_{uuid.uuid4().hex[:8]}"
        
        edge = {
            "id": edge_id,
            "from": from_entity,
            "to": to_entity,
            "type": relation_type,
            "properties": properties or {},
            "created_at": datetime.now().isoformat(),
            "weight": 1.0,
        }
        
        # 检查是否已存在相同关系
        for existing in self.graph["edges"]:
            if (existing["from"] == from_entity and 
                existing["to"] == to_entity and 
                existing["type"] == relation_type):
                # 增加权重
                existing["weight"] += 0.5
                existing["updated_at"] = datetime.now().isoformat()
                self._save_graph()
                return existing["id"]
        
        self.graph["edges"].append(edge)
        self._save_graph()
        return edge_id
    
    def disambiguate_entity(self, entity_name: str, entity_type: str = None,
                           context: str = "") -> dict:
        """
        【P1新增】实体消歧 - 判断实体是否已存在
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型（可选）
            context: 上下文信息
            
        Returns:
            {"action": "merged"|"existing"|"new", "entity_id": "...", "entity": {...}}
        """
        try:
            from entity_disambiguation import get_disambiguator
            disambiguator = get_disambiguator()
        except ImportError:
            # 如果消歧模块不可用，使用简单匹配
            for node_id, node in self.graph["nodes"].items():
                if node["name"] == entity_name:
                    return {
                        "action": "existing",
                        "entity_id": node_id,
                        "entity": node
                    }
            return {"action": "new", "entity_id": None, "entity": None}
        
        # 获取所有已存在实体
        existing_entities = list(self.graph["nodes"].values())
        
        # 执行消歧
        result = disambiguator.disambiguate_and_merge(
            entity_name=entity_name,
            entity_type=entity_type or "concept",
            memory_id="",  # 消歧时不关联记忆
            existing_entities=existing_entities
        )
        
        if result["action"] == "merged":
            # 找到被合并的实体
            entity_id = result["entity_id"]
            entity = self.graph["nodes"].get(entity_id, {})
            
            # 更新mention_count
            if entity:
                entity["mention_count"] += 1
                entity["last_seen"] = datetime.now().isoformat()
                self._save_graph()
            
            return {
                "action": "merged",
                "entity_id": entity_id,
                "entity_name": result["entity_name"],
                "confidence": result.get("confidence", 0),
                "merged_into": result["entity_name"]
            }
        
        # 创建新实体
        entity_id = self.add_entity(entity_name, entity_type or "concept")
        entity = self.graph["nodes"][entity_id]
        
        return {
            "action": "new",
            "entity_id": entity_id,
            "entity": entity
        }
    
    def merge_entities(self, source_id: str, target_id: str) -> bool:
        """
        【P1新增】合并两个实体
        
        Args:
            source_id: 被合并的实体ID
            target_id: 目标实体ID
            
        Returns:
            是否成功
        """
        if source_id not in self.graph["nodes"] or target_id not in self.graph["nodes"]:
            return False
        
        source = self.graph["nodes"][source_id]
        target = self.graph["nodes"][target_id]
        
        # 合并属性
        if "aliases" not in target:
            target["aliases"] = []
        target["aliases"].append(source["name"])
        target["mention_count"] += source.get("mention_count", 1)
        
        # 更新关系：将source的关系指向target
        for edge in self.graph["edges"]:
            if edge["from"] == source["name"]:
                edge["from"] = target["name"]
            if edge["to"] == source["name"]:
                edge["to"] = target["name"]
        
        # 删除source实体
        del self.graph["nodes"][source_id]
        self._save_graph()
        
        return True
    
    def extract_and_link(self, memory_content: str, memory_id: str = None) -> dict:
        """
        从记忆内容中提取实体和关系并添加到图谱
        
        使用规则+LLM混合抽取
        """
        extracted = {
            "entities": [],
            "relations": [],
            "linked_memory": memory_id
        }
        
        # 规则抽取常见模式
        patterns = [
            # 实体模式
            (r'([A-Z][A-Za-z]+)在([A-Z][A-Za-z]+)工作', 'person', 'company', 'works_at'),
            (r'使用([A-Za-z0-9]+)框架', None, 'framework', 'uses'),
            (r'是([A-Za-z0-9]+)工程师', 'person', 'profession', 'is_a'),
            (r'项目([A-Za-z0-9]+)', None, 'project', 'project_named'),
            (r'公司([A-Za-z0-9]+)', None, 'company', 'company_named'),
            (r'喜欢(.+?)[,。]', None, 'preference', 'likes'),
            (r'使用(.+?)[,。]', None, 'tool', 'uses'),
        ]
        
        # 简单规则抽取（避免LLM调用开销大）
        import re
        
        # 提取"XX是YY"模式
        is_patterns = re.findall(r'([A-Za-z0-9\u4e00-\u9fff]+)是的?([A-Za-z0-9\u4e00-\u9fff]+)', memory_content)
        for subject, obj in is_patterns:
            if len(subject) > 1 and len(obj) > 1 and subject != obj:
                entity_id, is_new = self.get_or_create_entity(subject, "entity")
                if is_new:
                    extracted["entities"].append(subject)
                
                entity_id2, is_new2 = self.get_or_create_entity(obj, "concept")
                if is_new2:
                    extracted["entities"].append(obj)
                
                self.add_relation(subject, obj, "is_a")
                extracted["relations"].append((subject, "is_a", obj))
        
        # 提取"使用XX"模式
        uses_patterns = re.findall(r'使用([A-Za-z0-9\u4e00-\u9fff]+)', memory_content)
        for tool in uses_patterns:
            if len(tool) > 1:
                entity_id, is_new = self.get_or_create_entity(tool, "tool")
                if is_new:
                    extracted["entities"].append(tool)
        
        # 提取"在XX工作"模式
        works_patterns = re.findall(r'在([A-Za-z0-9\u4e00-\u9fff]+)工作', memory_content)
        for company in works_patterns:
            if len(company) > 1:
                entity_id, is_new = self.get_or_create_entity(company, "company")
                if is_new:
                    extracted["entities"].append(company)
        
        return extracted
    
    def get_entity_network(self, entity_name: str, depth: int = 2) -> dict:
        """
        获取实体网络（ego graph）
        
        Args:
            entity_name: 实体名称
            depth: 探索深度
        """
        network = {
            "center": entity_name,
            "depth": depth,
            "nodes": [],
            "edges": [],
            "paths": []
        }
        
        # 收集直接相连的实体
        visited = set()
        frontier = [(entity_name, 0)]
        
        while frontier:
            current, d = frontier.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)
            
            if current not in [n["name"] for n in network["nodes"]]:
                network["nodes"].append({"name": current, "depth": d})
            
            if d >= depth:
                continue
            
            # 找所有直接关系
            for edge in self.graph["edges"]:
                if edge["from"] == current and edge["to"] not in visited:
                    network["edges"].append(edge)
                    frontier.append((edge["to"], d + 1))
                elif edge["to"] == current and edge["from"] not in visited:
                    network["edges"].append(edge)
                    frontier.append((edge["from"], d + 1))
        
        return network
    
    def search_by_entity(self, entity_name: str) -> dict:
        """
        基于实体搜索相关记忆
        """
        # 获取实体网络
        network = self.get_entity_network(entity_name, depth=1)
        
        # 收集相关实体
        related_entities = [n["name"] for n in network["nodes"]]
        
        return {
            "entity": entity_name,
            "related_entities": related_entities,
            "relations": network["edges"],
        }
    
    def get_stats(self) -> dict:
        """获取图谱统计"""
        node_types = defaultdict(int)
        relation_types = defaultdict(int)
        
        for node in self.graph["nodes"].values():
            node_types[node["type"]] += 1
        
        for edge in self.graph["edges"]:
            relation_types[edge["type"]] += 1
        
        return {
            "total_entities": len(self.graph["nodes"]),
            "total_relations": len(self.graph["edges"]),
            "entity_types": dict(node_types),
            "relation_types": dict(relation_types),
        }
    
    def suggest_connections(self, memory_content: str) -> list:
        """
        基于新记忆内容建议新连接
        """
        suggestions = []
        
        # 提取当前内容中的实体
        extracted = self.extract_and_link(memory_content)
        
        # 检查已有实体之间是否可以建立新连接
        entities = extracted.get("entities", [])
        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                # 检查是否已存在关系
                has_relation = any(
                    (edge["from"] == e1 and edge["to"] == e2) or
                    (edge["from"] == e2 and edge["to"] == e1)
                    for edge in self.graph["edges"]
                )
                
                if not has_relation:
                    suggestions.append({
                        "from": e1,
                        "to": e2,
                        "reason": f"同时出现在同一记忆片段中，可能存在关联"
                    })
        
        return suggestions


# 全局实例
_kg_instance = None


def get_kg() -> KnowledgeGraph:
    """懒加载单例"""
    global _kg_instance
    if _kg_instance is None:
        _kg_instance = KnowledgeGraph()
    return _kg_instance
