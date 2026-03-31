"""
Claw Memory 用户画像模块
从记忆中自动提取用户偏好和特征
"""

from typing import Dict, List, Optional
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class UserProfile:
    """用户画像数据结构"""
    user_id: str
    name: Optional[str] = None
    interests: List[str] = field(default_factory=list)
    preferences: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    work: Optional[str] = None
    role: Optional[str] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "interests": self.interests,
            "preferences": self.preferences,
            "skills": self.skills,
            "locations": self.locations,
            "work": self.work,
            "role": self.role
        }


class UserProfiler:
    """
    用户画像构建器
    
    从记忆内容中自动提取用户特征
    """
    
    # 关键词到类别的映射
    KEYWORD_CATEGORIES = {
        "interests": ["喜欢", "爱好", "兴趣", "热衷", "爱"],
        "preferences": ["偏好", "宁愿", "更愿意", "觉得", "认为"],
        "skills": ["擅长", "精通", "会", "懂", "掌握", "专业"],
        "locations": ["住在", "在", "位于", "位于", "城市"],
        "work": ["工作", "公司", "职业", "职位", "岗位"],
        "role": ["是", "担任", "负责", "角色"]
    }
    
    def extract_profile(self, memories: List[dict]) -> UserProfile:
        """
        从记忆列表中提取用户画像
        
        Args:
            memories: 记忆列表
            
        Returns:
            UserProfile 用户画像对象
        """
        profile = UserProfile(user_id="default")
        
        interests = []
        preferences = []
        skills = []
        locations = []
        
        for mem in memories:
            content = mem.get("content", "")
            mem_type = mem.get("type", "")
            
            # 从fact类型中提取
            if mem_type == "fact":
                interests.extend(self._extract_by_keywords(content, self.KEYWORD_CATEGORIES["interests"]))
                skills.extend(self._extract_by_keywords(content, self.KEYWORD_CATEGORIES["skills"]))
                locations.extend(self._extract_by_keywords(content, self.KEYWORD_CATEGORIES["locations"]))
                
                # 提取工作信息
                work_keywords = self.KEYWORD_CATEGORIES["work"]
                for kw in work_keywords:
                    if kw in content:
                        # 尝试提取工作相关信息
                        parts = content.split(kw)
                        if len(parts) > 1:
                            profile.work = parts[1].split(",")[0].strip()
                            break
            
            # 从preference类型中提取
            elif mem_type == "preference":
                preferences.extend(self._extract_by_keywords(content, self.KEYWORD_CATEGORIES["preferences"]))
        
        # 去重并限制数量
        profile.interests = list(set(interests))[:20]
        profile.preferences = list(set(preferences))[:20]
        profile.skills = list(set(skills))[:20]
        profile.locations = list(set(locations))[:10]
        
        return profile
    
    def _extract_by_keywords(self, content: str, keywords: List[str]) -> List[str]:
        """根据关键词提取相关内容"""
        results = []
        for kw in keywords:
            if kw in content:
                # 简单提取关键词后的内容
                idx = content.find(kw)
                # 提取关键词后面的一段文字
                snippet = content[idx:idx+50]
                results.append(snippet.strip())
        return results
    
    def update_profile_from_memory(
        self,
        profile: UserProfile,
        memory_content: str,
        memory_type: str
    ) -> UserProfile:
        """
        从单条记忆更新画像
        
        Args:
            profile: 当前画像
            memory_content: 记忆内容
            memory_type: 记忆类型
            
        Returns:
            更新后的画像
        """
        if memory_type == "fact":
            # 提取名字
            if "名字叫" in memory_content:
                idx = memory_content.find("名字叫")
                name = memory_content[idx+4:].split(",")[0].strip()
                profile.name = name
            
            # 提取兴趣爱好
            for kw in self.KEYWORD_CATEGORIES["interests"]:
                if kw in memory_content:
                    profile.interests.append(memory_content)
                    break
        
        elif memory_type == "preference":
            profile.preferences.append(memory_content)
        
        # 去重
        profile.interests = list(set(profile.interests))[:20]
        profile.preferences = list(set(profile.preferences))[:20]
        
        return profile


# 全局实例
_profiler: Optional[UserProfiler] = None


def get_profiler() -> UserProfiler:
    """获取画像构建器实例"""
    global _profiler
    if _profiler is None:
        _profiler = UserProfiler()
    return _profiler


def build_user_profile(memories: List[dict]) -> UserProfile:
    """快速构建用户画像"""
    profiler = get_profiler()
    return profiler.extract_profile(memories)
