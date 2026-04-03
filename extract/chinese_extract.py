"""
中文实体抽取模块
修复P1问题：添加中文实体抽取规则

支持：
- 中文公司名、人名抽取
- 中文技术栈抽取
- LLM fallback
"""
import re
from typing import List, Dict, Tuple, Optional


class ChineseEntityExtractor:
    """
    中文实体抽取器
    
    使用正则 + 关键词匹配进行抽取，
    复杂情况调用LLM fallback
    """
    
    def __init__(self):
        self.patterns = self._init_patterns()
    
    def _init_patterns(self) -> List[Dict]:
        """初始化抽取模式"""
        return [
            # 中文公司模式
            {
                "pattern": r'([\u4e00-\u9fff]{2,8})(?:在|于|就职于|工作于)([\u4e00-\u9fff]{2,10})(?:公司|集团|企业|工作室)',
                "type": "person_company",
                "subject_idx": 0,
                "object_idx": 1,
                "relation": "works_at"
            },
            # 中文公司直接提及
            {
                "pattern": r'(?:在|于|就职于)([\u4e00-\u9fff]{2,10})(?:公司|集团|企业)',
                "type": "company",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "is_company"
            },
            # 使用XX框架/语言
            {
                "pattern": r'(?:使用|采用|基于)(React|Vue|Angular|Python|Java|Go|Rust|JavaScript|TypeScript|\S+)',
                "type": "person_tool",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "uses"
            },
            # 是XX工程师
            {
                "pattern": r'([\u4e00-\u9fff]{2,4})(?:是|担任)([\u4e00-\u9fff]+)工程师',
                "type": "person_profession",
                "subject_idx": 0,
                "object_idx": 1,
                "relation": "is_a"
            },
            # 喜欢XX
            {
                "pattern": r'(?:喜欢|爱|偏好)([\u4e00-\u9fffA-Za-z0-9]+)',
                "type": "preference",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "likes"
            },
            # 项目XX
            {
                "pattern": r'(?:项目|做了)([\u4e00-\u9fffA-Za-z0-9]{2,15})',
                "type": "project",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "worked_on"
            },
            # 在XX公司工作
            {
                "pattern": r'(?:在|于)([\u4e00-\u9fff]{2,10})(?:公司|集团|企业)(?:工作|任职)',
                "type": "company",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "works_at"
            },
            # 科技公司检测
            {
                "pattern": r'((?:字节跳动|阿里巴巴|腾讯|百度|京东|美团|滴滴|小米|华为|网易|新浪|搜狐|360|快手|拼多多|抖音|头条|微信|支付宝)[\u4e00-\u9fff]*)',
                "type": "tech_company",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "mentioned"
            },
            # 住在XX
            {
                "pattern": r'(?:住在|定居于|位于)([\u4e00-\u9fff]{2,10})',
                "type": "location",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "lives_in"
            },
            # 毕业于XX学校
            {
                "pattern": r'(?:毕业于|就读于)([\u4e00-\u9fff]{2,15})(?:大学|学院|学校)',
                "type": "education",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "graduated_from"
            },
            # 职位是XX
            {
                "pattern": r'(?:职位是|担任|当)([\u4e00-\u9fff]{2,8})(?:工程|开发|设计|产品|运营|市场|销售|经理|总监| CTO| CEO| CFO| COO| VP)',
                "type": "position",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "has_position"
            },
            # 有XX个朋友
            {
                "pattern": r'(?:有|认识|结交了)([\u4e00-\u9fff]{1,5})(?:朋友|同事|伙伴)',
                "type": "social",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "has_social"
            },
            # 不喜欢XX
            {
                "pattern": r'(?:不喜欢|讨厌|厌恶|反感)([\u4e00-\u9fffA-Za-z0-9]+)',
                "type": "dislike",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "dislikes"
            },
            # 过敏XX
            {
                "pattern": r'(?:对|过敏|敏感)([\u4e00-\u9fffA-Za-z0-9]+)(?:过敏|敏感)',
                "type": "allergy",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "allergic_to"
            },
            # 朋友XX
            {
                "pattern": r'(?:朋友|同学|同事)([\u4e00-\u9fff]{1,5})(?:叫|名|是)',
                "type": "person_known",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "knows"
            },
            # 学过XX
            {
                "pattern": r'(?:学过|学习过|掌握|精通)([\u4e00-\u9fffA-Za-z0-9]+)',
                "type": "skill_acquired",
                "subject_idx": None,
                "object_idx": 0,
                "relation": "learned"
            }
        ]
    
    def extract(self, text: str) -> Dict:
        """
        从文本中抽取实体和关系
        
        Returns:
            {
                "entities": [{"name": "...", "type": "..."}],
                "relations": [{"from": "...", "to": "...", "type": "..."}]
            }
        """
        entities = []
        relations = []
        seen_entities = set()
        
        # 应用正则模式
        for pattern_info in self.patterns:
            pattern = re.compile(pattern_info["pattern"])
            matches = pattern.findall(text)
            
            for match in matches:
                # 提取subject
                subject_idx = pattern_info["subject_idx"]
                if subject_idx is not None:
                    subject = match[subject_idx] if isinstance(match, tuple) else match
                    if subject and subject not in seen_entities:
                        entities.append({"name": subject, "type": "person"})
                        seen_entities.add(subject)
                
                # 提取object
                object_idx = pattern_info["object_idx"]
                if isinstance(match, tuple):
                    obj = match[object_idx] if object_idx < len(match) else None
                else:
                    obj = match if object_idx == 0 else None
                
                if obj and obj not in seen_entities:
                    entity_type = self._infer_entity_type(obj)
                    entities.append({"name": obj, "type": entity_type})
                    seen_entities.add(obj)
                
                # 创建关系
                if subject_idx is not None and object_idx is not None:
                    subject = match[subject_idx] if isinstance(match, tuple) else None
                    obj = match[object_idx] if isinstance(match, tuple) else match
                    if subject and obj:
                        relations.append({
                            "from": subject,
                            "to": obj,
                            "type": pattern_info["relation"]
                        })
        
        # 检测技术栈
        tech_keywords = self._get_tech_keywords()
        for category, keywords in tech_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text.lower() and keyword not in seen_entities:
                    entities.append({"name": keyword, "type": "technology"})
                    seen_entities.add(keyword)
        
        return {
            "entities": entities,
            "relations": relations
        }
    
    def _get_tech_keywords(self) -> dict:
        """获取技术栈关键词（延迟初始化）"""
        return {
            "frontend": ["React", "Vue", "Angular", "Svelte", "jQuery", "HTML", "CSS"],
            "backend": ["Node.js", "Python", "Java", "Go", "Rust", "C++", "C#", "Ruby", "PHP"],
            "database": ["MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch"],
            "cloud": ["AWS", "Azure", "GCP", "阿里云", "腾讯云"],
            "ai": ["TensorFlow", "PyTorch", "Keras", "scikit-learn", "OpenAI"],
            "mobile": ["React Native", "Flutter", "Swift", "Kotlin", "Android", "iOS"]
        }
    
    def _infer_entity_type(self, name: str) -> str:
        """推断实体类型"""
        # 公司关键词
        company_keywords = ["公司", "集团", "企业", "工作室", "医院", "学校", "银行"]
        for kw in company_keywords:
            if kw in name:
                return "company"
        
        # 科技公司
        tech_companies = ["字节跳动", "阿里巴巴", "腾讯", "百度", "京东", "美团", "小米", "华为", "网易", "新浪", "搜狐", "快手", "拼多多", "滴滴", "抖音", "微信", "支付宝"]
        for tc in tech_companies:
            if tc in name:
                return "company"
        
        # 城市
        cities = ["北京", "上海", "深圳", "广州", "杭州", "南京", "成都", "武汉", "西安", "苏州", "天津", "重庆", "长沙", "郑州", "东莞", "青岛", "沈阳", "大连", "厦门", "福州"]
        for city in cities:
            if city in name:
                return "location"
        
        # 技术栈
        all_techs = []
        for keywords in self._get_tech_keywords().values():
            all_techs.extend(keywords)
        for tech in all_techs:
            if tech.lower() in name.lower():
                return "technology"
        
        return "concept"
    
    def extract_with_llm_fallback(self, text: str) -> Dict:
        """
        使用LLM进行复杂抽取（fallback）
        
        当正则无法抽取时调用
        """
        prompt = f"""从以下文本中抽取实体和关系。

文本：{text}

请以JSON格式输出：
{{
    "entities": [
        {{"name": "实体名", "type": "person|company|technology|project|concept"}},
        ...
    ],
    "relations": [
        {{"from": "实体A", "to": "实体B", "type": "关系类型"}},
        ...
    ]
}}

只输出JSON，不要其他内容。"""
        
        try:
            import requests
            from core.memory_config import CONFIG
            
            response = requests.post(
                f"{CONFIG.get('ollama_url', 'http://localhost:11434')}/api/chat",
                json={
                    "model": CONFIG.get("llm_model", "qwen3.5:27b"),
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                },
                timeout=30
            )
            
            result_data = response.json()
            content = result_data.get("message", {}).get("content", "")
            
            # 解析JSON
            import json as json_module
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json_module.loads(json_match.group())
                return data
                
        except Exception as e:
            print(f"[ChineseEntityExtractor] LLM fallback失败: {e}")
        
        return {"entities": [], "relations": []}


# 全局实例
_extractor = None


def get_chinese_extractor() -> ChineseEntityExtractor:
    """获取中文抽取器实例"""
    global _extractor
    if _extractor is None:
        _extractor = ChineseEntityExtractor()
    return _extractor
