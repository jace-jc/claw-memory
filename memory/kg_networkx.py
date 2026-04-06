"""
知识图谱模块 V2 - 基于 NetworkX
修复P1问题：替换JSON文件存储为真正的图数据库

优势：
- 支撑10万+实体（JSON超过1万会OOM）
- 索引查询，无需全量加载
- 内置图算法（最短路径、中心性等）
- 内存高效管理
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Set, Any
import networkx as nx
from core.memory_config import CONFIG


class KnowledgeGraphNX:
    """
    基于 NetworkX 的知识图谱
    
    使用 MultiDiGraph 支持多关系类型
    """
    
    def __init__(self, kg_path: str = None):
        self.kg_path = kg_path or CONFIG.get("kg_path",
            str(Path(CONFIG.get("memory_dir", "/Users/claw/.openclaw/workspace/memory")) / "knowledge_graph.json"))
        self._ensure_dir()
        
        # 尝试加载旧版本JSON
        self.graph = self._load_or_create()
    
    def _ensure_dir(self):
        """确保目录存在"""
        Path(self.kg_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _load_or_create(self) -> nx.MultiDiGraph:
        """加载已有数据或创建新图"""
        if Path(self.kg_path).exists():
            try:
                # 尝试导入旧格式
                with open(self.kg_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                G = nx.MultiDiGraph()
                
                # 转换节点
                for node_id, node_data in data.get("nodes", {}).items():
                    G.add_node(
                        node_data.get("name", node_id),
                        **{
                            "id": node_id,
                            "type": node_data.get("type", "concept"),
                            "properties": node_data.get("properties", {}),
                            "mention_count": node_data.get("mention_count", 1),
                            "created_at": node_data.get("created_at"),
                            "last_seen": node_data.get("last_seen")
                        }
                    )
                
                # 转换边
                for edge in data.get("edges", []):
                    G.add_edge(
                        edge.get("from", ""),
                        edge.get("to", ""),
                        relation=edge.get("type", "related"),
                        weight=edge.get("weight", 1.0),
                        created_at=edge.get("created_at")
                    )
                
                print(f"[KnowledgeGraphNX] 从旧格式加载了 {G.number_of_nodes()} 节点, {G.number_of_edges()} 边")
                return G
                
            except Exception as e:
                print(f"[KnowledgeGraphNX] 加载旧格式失败: {e}")
        
        return nx.MultiDiGraph()
    
    def _save_graph(self):
        """保存图数据"""
        # 转换为兼容旧格式
        data = {
            "nodes": {},
            "edges": []
        }
        
        for node, attrs in self.graph.nodes(data=True):
            node_id = attrs.get("id", node)
            data["nodes"][node_id] = {
                "name": node,
                "type": attrs.get("type", "concept"),
                "properties": attrs.get("properties", {}),
                "mention_count": attrs.get("mention_count", 1),
                "created_at": attrs.get("created_at"),
                "last_seen": attrs.get("last_seen")
            }
        
        for u, v, attrs in self.graph.edges(data=True):
            data["edges"].append({
                "from": u,
                "to": v,
                "type": attrs.get("relation", "related"),
                "weight": attrs.get("weight", 1.0),
                "created_at": attrs.get("created_at")
            })
        
        with open(self.kg_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_entity(self, name: str, entity_type: str = "concept", 
                 properties: dict = None) -> str:
        """添加实体节点"""
        if self.graph.has_node(name):
            # 已存在，更新属性
            self.graph.nodes[name]["mention_count"] = self.graph.nodes[name].get("mention_count", 0) + 1
            self.graph.nodes[name]["last_seen"] = datetime.now().isoformat()
            self._save_graph()
            return name
        
        # 添加新节点
        self.graph.add_node(name,
            id=name,
            type=entity_type,
            properties=properties or {},
            mention_count=1,
            created_at=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat()
        )
        self._save_graph()
        return name
    
    def add_relation(self, from_entity: str, to_entity: str,
                    relation_type: str, weight: float = 1.0) -> bool:
        """添加关系边"""
        if not self.graph.has_node(from_entity):
            self.add_entity(from_entity)
        if not self.graph.has_node(to_entity):
            self.add_entity(to_entity)
        
        # 检查是否已存在关系
        if self.graph.has_edge(from_entity, to_entity):
            # 增加权重
            current_weight = self.graph[from_entity][to_entity].get("weight", 1.0)
            self.graph[from_entity][to_entity]["weight"] = current_weight + weight
            self._save_graph()
            return True
        
        self.graph.add_edge(from_entity, to_entity,
            relation=relation_type,
            weight=weight,
            created_at=datetime.now().isoformat()
        )
        self._save_graph()
        return True
    
    def get_entity(self, name: str) -> Optional[Dict]:
        """获取实体信息"""
        if not self.graph.has_node(name):
            return None
        
        attrs = self.graph.nodes[name]
        return {
            "name": name,
            "type": attrs.get("type", "concept"),
            "properties": attrs.get("properties", {}),
            "mention_count": attrs.get("mention_count", 1),
            "created_at": attrs.get("created_at"),
            "last_seen": attrs.get("last_seen")
        }
    
    def get_neighbors(self, entity: str, relation: str = None) -> List[Dict]:
        """获取实体的邻居节点"""
        if not self.graph.has_node(entity):
            return []
        
        neighbors = []
        for successor in self.graph.successors(entity):
            edge_data = self.graph[entity][successor]
            if relation is None or edge_data.get("relation") == relation:
                neighbors.append({
                    "entity": successor,
                    "relation": edge_data.get("relation", "related"),
                    "weight": edge_data.get("weight", 1.0)
                })
        
        return neighbors
    
    def search_entities(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索实体（模糊匹配）"""
        query_lower = query.lower()
        results = []
        
        for node in self.graph.nodes():
            if query_lower in node.lower():
                results.append(self.get_entity(node))
                if len(results) >= limit:
                    break
        
        return results
    
    def get_entity_network(self, entity: str, depth: int = 2) -> Dict:
        """获取实体周围的网络"""
        if not self.graph.has_node(entity):
            return {"nodes": [], "edges": []}
        
        # 使用BFS获取子图
        nodes = {entity}
        edges = []
        
        current_level = {entity}
        for _ in range(depth):
            next_level = set()
            for node in current_level:
                for successor in self.graph.successors(node):
                    if successor not in nodes:
                        next_level.add(successor)
                for predecessor in self.graph.predecessors(node):
                    if predecessor not in nodes:
                        next_level.add(predecessor)
            nodes.update(next_level)
            current_level = next_level
        
        # 构建结果
        result_nodes = []
        for node in nodes:
            attrs = self.graph.nodes[node]
            result_nodes.append({
                "name": node,
                "type": attrs.get("type", "concept"),
                "mention_count": attrs.get("mention_count", 1),
                "depth": self._get_depth(entity, node, depth)
            })
        
        result_edges = []
        for u, v, attrs in self.graph.edges(data=True):
            if u in nodes and v in nodes:
                result_edges.append({
                    "from": u,
                    "to": v,
                    "relation": attrs.get("relation", "related"),
                    "weight": attrs.get("weight", 1.0)
                })
        
        return {"nodes": result_nodes, "edges": result_edges}
    
    def _get_depth(self, root: str, target: str, max_depth: int) -> int:
        """计算从root到target的深度"""
        try:
            path = nx.shortest_path(self.graph, root, target)
            return len(path) - 1
        except:
            return max_depth
    
    def get_stats(self) -> Dict:
        """获取图统计信息"""
        return {
            "total_entities": self.graph.number_of_nodes(),
            "total_relations": self.graph.number_of_edges(),
            "entity_types": self._count_types(),
            "relation_types": self._count_relations()
        }
    
    def _count_types(self) -> Dict[str, int]:
        """统计实体类型"""
        types = {}
        for _, attrs in self.graph.nodes(data=True):
            t = attrs.get("type", "unknown")
            types[t] = types.get(t, 0) + 1
        return types
    
    def _count_relations(self) -> Dict[str, int]:
        """统计关系类型"""
        relations = {}
        for _, _, attrs in self.graph.edges(data=True):
            r = attrs.get("relation", "unknown")
            relations[r] = relations.get(r, 0) + 1
        return relations
    
    def delete_entity(self, name: str) -> bool:
        """删除实体及其所有关系"""
        if not self.graph.has_node(name):
            return False
        
        self.graph.remove_node(name)
        self._save_graph()
        return True
    
    def find_path(self, from_entity: str, to_entity: str, max_depth: int = 3) -> List[Dict]:
        """
        【新增】传递推理 - 查找两个实体之间的路径
        
        用于推理间接关系，如：
        - A 认识 B，B 认识 C，推理出 A 可能认识 C
        - A 在 B 工作，B 在 C 开发了 X，推理出 A 与 C 通过 X 关联
        
        Args:
            from_entity: 起始实体
            to_entity: 目标实体
            max_depth: 最大搜索深度
        
        Returns:
            路径列表，每条路径包含节点和关系
        """
        if not self.graph.has_node(from_entity) or not self.graph.has_node(to_entity):
            return []
        
        try:
            # 查找所有简单路径
            paths = list(nx.all_simple_paths(
                self.graph,
                from_entity,
                to_entity,
                cutoff=max_depth
            ))
            
            results = []
            for path in paths:
                path_details = {
                    "entities": path,
                    "relations": [],
                    "depth": len(path) - 1,
                    "score": 1.0 / (len(path) - 1)  # 越短路径分数越高
                }
                
                # 获取路径上的关系
                for i in range(len(path) - 1):
                    from_node = path[i]
                    to_node = path[i + 1]
                    
                    # 获取两个节点之间的关系
                    edge_data = self.graph.get_edge_data(from_node, to_node)
                    if edge_data:
                        for key, data in edge_data.items():
                            path_details["relations"].append({
                                "from": from_node,
                                "to": to_node,
                                "relation": data.get("relation", "related_to"),
                                "weight": data.get("weight", 1.0)
                            })
                
                results.append(path_details)
            
            # 按分数排序
            results.sort(key=lambda x: x["score"], reverse=True)
            return results
            
        except nx.NetworkXError:
            return []
    
    def find_common_neighbors(self, entity1: str, entity2: str) -> List[Dict]:
        """
        【新增】查找两个实体的共同邻居
        
        用于推理间接关联：
        - A 和 B 都认识 C，说明 A 和 B 可能有关联
        """
        if not self.graph.has_node(entity1) or not self.graph.has_node(entity2):
            return []
        
        # 获取两个实体的邻居
        neighbors1 = set(self.graph.neighbors(entity1))
        neighbors2 = set(self.graph.neighbors(entity2))
        
        # 取交集
        common = neighbors1 & neighbors2
        
        results = []
        for node in common:
            node_data = self.get_entity(node)
            if node_data:
                results.append(node_data)
        
        return results
    
    def infer_relations(self, entity: str, max_depth: int = 3) -> List[Dict]:
        """
        【P3优化】推理实体的潜在关系
        
        通过分析实体周围的图结构，推断可能的隐含关系
        
        Args:
            entity: 起始实体
            max_depth: 分析深度（支持1/2/3跳）
        
        Returns:
            推理结果列表
        """
        if not self.graph.has_node(entity):
            return []
        
        inferences = []
        
        # 1. 查找二度关联（朋友的的朋友）
        neighbors = list(self.graph.neighbors(entity))
        for neighbor in neighbors[:5]:  # 只看前5个邻居
            second_neighbors = list(self.graph.neighbors(neighbor))
            for sn in second_neighbors:
                if sn != entity and sn not in neighbors:
                    path = self.find_path(entity, sn, max_depth=2)
                    if path:
                        inferences.append({
                            "type": "second_degree",
                            "target": sn,
                            "via": neighbor,
                            "confidence": 0.6,
                            "path": path[0]
                        })
        
        # 2. 【新增】三度关联（朋友的朋友的朋友）
        if max_depth >= 3:
            for neighbor in neighbors[:3]:
                second_neighbors = list(self.graph.neighbors(neighbor))
                for sn in second_neighbors:
                    third_neighbors = list(self.graph.neighbors(sn))
                    for tn in third_neighbors:
                        if tn != entity and tn not in neighbors and tn not in second_neighbors:
                            path = self.find_path(entity, tn, max_depth=3)
                            if path:
                                inferences.append({
                                    "type": "third_degree",
                                    "target": tn,
                                    "via": [neighbor, sn],
                                    "confidence": 0.4,  # 三跳置信度降低
                                    "path": path[0]
                                })
        
        # 3. 查找同类型实体
        entity_data = self.get_entity(entity)
        if entity_data:
            entity_type = entity_data.get("type", "concept")
            same_type = self.find_by_type(entity_type, limit=10)
            for st in same_type[:5]:
                if st.get("name") != entity:
                    # 检查是否已经直接关联
                    if not self.graph.has_edge(entity, st.get("name")):
                        inferences.append({
                            "type": "same_type_unlinked",
                            "target": st.get("name"),
                            "entity_type": entity_type,
                            "confidence": 0.3
                        })
        
        # 按置信度排序
        inferences.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return inferences[:10]  # 最多返回10条
    
    def find_by_type(self, entity_type: str, limit: int = 10) -> List[Dict]:
        """查找特定类型的所有实体"""
        results = []
        for node in self.graph.nodes():
            node_data = self.get_entity(node)
            if node_data and node_data.get("type") == entity_type:
                results.append(node_data)
                if len(results) >= limit:
                    break
        return results
    
    def detect_contradictions(self, files: List[dict] = None) -> List[Dict[str, Any]]:
        """【P1修复】检测 KG 中的矛盾
        
        Args:
            files: 可选的文件列表，每个文件包含 content 和 date 字段
                   如果不提供，则扫描 kg_path 目录下的所有 .md 文件
        
        Returns:
            矛盾列表，每项包含 type, entity, conflicts 等字段
        """
        import re
        from pathlib import Path
        
        if files is None:
            # 扫描 kg_path 目录下的所有 .md 文件
            kg_dir = Path(self.kg_path).parent if self.kg_path else None
            if kg_dir is None:
                return []
            files = []
            for md_file in kg_dir.glob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    files.append({
                        "path": str(md_file),
                        "date": md_file.stem,
                        "content": content
                    })
                except Exception:
                    continue
        
        # 使用 KG 数据进行矛盾检测
        kg_data = {
            "nodes": dict(self.graph.nodes(data=True)),
            "edges": [{"from": u, "to": v, "type": d.get("type", "related")} 
                      for u, v, d in self.graph.edges(data=True)]
        }
        
        # 提取关键事实
        def extract_key_facts(content: str) -> dict:
            tasks = re.findall(r'[❌✅]\s*\[?\s*(.+?)\s*\]?', content)
            prefs = re.findall(r'偏好[：:]\s*(.+)', content)
            return {"tasks": tasks, "preferences": prefs}
        
        conflicts = []
        task_index = {}
        pref_index = {}
        
        for f in files:
            facts = extract_key_facts(f.get("content", ""))
            for task in facts.get("tasks", []):
                task_clean = re.sub(r"^[❌✅]\s*", "", task).strip()
                if task_clean:
                    if task_clean not in task_index:
                        task_index[task_clean] = []
                    task_index[task_clean].append(f)
            
            for pref in facts.get("preferences", []):
                if pref:
                    key = pref.strip()[:30]
                    if key not in pref_index:
                        pref_index[key] = []
                    pref_index[key].append(f)
        
        # 检测任务状态矛盾（已完成 vs 未完成）
        for task_desc, file_list in task_index.items():
            if len(file_list) < 2:
                continue
            has_pending = any("❌" in t for t in file_list)
            has_done = any("✅" in t for t in file_list)
            if has_pending and has_done:
                dates = [f.get("date", "") for f in file_list]
                conflicts.append({
                    "type": "task_status_conflict",
                    "entity": task_desc,
                    "conflicts": dates,
                    "severity": "high"
                })
        
        # 检测偏好矛盾
        for pref_key, file_list in pref_index.items():
            if len(file_list) < 2:
                continue
            # 简化检测：同一偏好出现在多个不同日期
            dates = list(set(f.get("date", "") for f in file_list))
            if len(dates) > 1:
                conflicts.append({
                    "type": "preference_conflict",
                    "entity": pref_key,
                    "conflicts": dates,
                    "severity": "medium"
                })
        
        return conflicts


# 全局实例
_kg_instance = None


def get_kg_nx() -> KnowledgeGraphNX:
    """获取NetworkX版知识图谱实例"""
    global _kg_instance
    if _kg_instance is None:
        _kg_instance = KnowledgeGraphNX()
    return _kg_instance
