"""
Claw Memory 多部署方案配置系统
支持 4 种部署方案自动切换

方案A: Full Power (高质量)
  - Embedding: Jina jina-embeddings-v5-text-small (API)
  - Reranker:  Jina jiner-reranker-v3 (API)
  - LLM:       OpenAI gpt-4o-mini
  - 需要: JINA_API_KEY + OPENAI_API_KEY

方案B: Budget (免费重排)
  - Embedding: Jina jina-embeddings-v5-text-small (API)
  - Reranker:  SiliconFlow BAAI/bge-reranker-v2-m3 (免费)
  - LLM:       OpenAI gpt-4o-mini
  - 需要: JINA_API_KEY + SILICONFLOW_API_KEY + OPENAI_API_KEY

方案C: Simple (仅OpenAI)
  - Embedding: OpenAI text-embedding-3-small
  - Reranker:  None
  - LLM:       OpenAI gpt-4o-mini
  - 需要: OPENAI_API_KEY

方案D: Fully Local (当前Claw Memory，默认)
  - Embedding: Ollama本地 (bge-m3 或 mxbai-embed-large)
  - Reranker:  None
  - LLM:       Ollama本地 (qwen3:8b)
  - 需要: 无外部API

默认使用方案D；当环境变量存在时自动切换到对应方案。
"""
import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

_logger = logging.getLogger("ClawMemory.ConfigMulti")

# =============================================================================
# 方案定义
# =============================================================================

@dataclass
class DeployScheme:
    name: str
    label: str
    embedding: Dict[str, Any]
    reranker: Optional[Dict[str, Any]]
    llm: Dict[str, Any]
    required_keys: List[str] = field(default_factory=list)

    def has_reranker(self) -> bool:
        return self.reranker is not None


SCHEME_A_FULL_POWER = DeployScheme(
    name="A",
    label="Full Power (高质量)",
    embedding={
        "provider": "jina",
        "model": "jina-embeddings-v5-text-small",
        "dimensions": 1024,
        "url": "https://api.jina.ai/v1/embeddings",
    },
    reranker={
        "provider": "jina",
        "model": "jiner-reranker-v3",
        "url": "https://api.jina.ai/v1/reranker",
    },
    llm={
        "provider": "openai",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
    required_keys=["JINA_API_KEY", "OPENAI_API_KEY"],
)

SCHEME_B_BUDGET = DeployScheme(
    name="B",
    label="Budget (免费重排)",
    embedding={
        "provider": "jina",
        "model": "jina-embeddings-v5-text-small",
        "dimensions": 1024,
        "url": "https://api.jina.ai/v1/embeddings",
    },
    reranker={
        "provider": "siliconflow",
        "model": "BAAI/bge-reranker-v2-m3",
        "url": "https://api.siliconflow.cn/v1/rerank",
    },
    llm={
        "provider": "openai",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
    required_keys=["JINA_API_KEY", "SILICONFLOW_API_KEY", "OPENAI_API_KEY"],
)

SCHEME_C_SIMPLE = DeployScheme(
    name="C",
    label="Simple (仅OpenAI)",
    embedding={
        "provider": "openai",
        "model": "text-embedding-3-small",
        "dimensions": 1536,
        "url": "https://api.openai.com/v1/embeddings",
    },
    reranker=None,
    llm={
        "provider": "openai",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
    required_keys=["OPENAI_API_KEY"],
)

SCHEME_D_LOCAL = DeployScheme(
    name="D",
    label="Fully Local (完全本地)",
    embedding={
        "provider": "ollama",
        "model": "bge-m3:latest",
        "dimensions": 1024,
        "url": "http://localhost:11434/api/embeddings",
    },
    reranker=None,
    llm={
        "provider": "ollama",
        "model": "qwen3:8b",
        "base_url": "http://localhost:11434",
    },
    required_keys=[],  # 无外部API
)

ALL_SCHEMES: Dict[str, DeployScheme] = {
    "A": SCHEME_A_FULL_POWER,
    "B": SCHEME_B_BUDGET,
    "C": SCHEME_C_SIMPLE,
    "D": SCHEME_D_LOCAL,
}


# =============================================================================
# 环境变量检测
# =============================================================================

def _check_keys(keys: List[str]) -> bool:
    """检查所有指定的环境变量是否存在"""
    return all(os.environ.get(k) for k in keys)


def _check_any_key(keys: List[str]) -> bool:
    """检查是否有任何一个指定的环境变量存在"""
    return any(os.environ.get(k) for k in keys)


def detect_scheme() -> str:
    """
    自动检测最佳部署方案。
    
    检测顺序（优先级从高到低）：
    1. 强制方案：MEMORY_SCHEME 环境变量
    2. 方案A：同时有 JINA_API_KEY + OPENAI_API_KEY
    3. 方案B：同时有 JINA_API_KEY + SILICONFLOW_API_KEY + OPENAI_API_KEY
    4. 方案C：有 OPENAI_API_KEY（且不是A/B）
    5. 默认：方案D（完全本地）
    """
    # 1. 强制指定
    forced = os.environ.get("MEMORY_SCHEME", "").upper()
    if forced in ALL_SCHEMES:
        _logger.info(f"[ConfigMulti] 强制使用方案 {forced}: {ALL_SCHEMES[forced].label}")
        return forced
    
    # 2. 方案B（优先检查，比A更具体）
    if _check_keys(["JINA_API_KEY", "SILICONFLOW_API_KEY", "OPENAI_API_KEY"]):
        _logger.info("[ConfigMulti] 检测到方案B: Budget (Jina + SiliconFlow + OpenAI)")
        return "B"
    
    # 3. 方案A
    if _check_keys(["JINA_API_KEY", "OPENAI_API_KEY"]):
        _logger.info("[ConfigMulti] 检测到方案A: Full Power (Jina + OpenAI)")
        return "A"
    
    # 4. 方案C
    if _check_keys(["OPENAI_API_KEY"]):
        _logger.info("[ConfigMulti] 检测到方案C: Simple (OpenAI only)")
        return "C"
    
    # 5. 默认方案D
    _logger.info("[ConfigMulti] 使用默认方案D: Fully Local (Ollama)")
    return "D"


# =============================================================================
# 当前激活方案
# =============================================================================

class ActiveConfig:
    """
    当前激活的多部署配置。
    支持通过环境变量 MEMORY_SCHEME 强制指定方案。
    """
    
    def __init__(self, scheme_name: str = None):
        if scheme_name is None:
            scheme_name = detect_scheme()
        self.scheme_name = scheme_name
        self.scheme = ALL_SCHEMES[scheme_name]
        self._embed_provider = None
        self._reranker_provider = None
        self._llm_provider = None
    
    def __repr__(self):
        return f"ActiveConfig(scheme={self.scheme_name}, label={self.scheme.label})"
    
    # ---- Embedding ----
    
    def get_embedding_config(self) -> Dict[str, Any]:
        """获取当前方案的 embedding 配置"""
        return self.scheme.embedding.copy()
    
    def get_embedding_provider_name(self) -> str:
        return self.scheme.embedding["provider"]
    
    def is_embedding_local(self) -> bool:
        return self.get_embedding_provider_name() == "ollama"
    
    # ---- Reranker ----
    
    def has_reranker(self) -> bool:
        return self.scheme.has_reranker()
    
    def get_reranker_config(self) -> Optional[Dict[str, Any]]:
        if not self.has_reranker():
            return None
        return self.scheme.reranker.copy()
    
    def get_reranker_provider_name(self) -> Optional[str]:
        if not self.has_reranker():
            return None
        return self.scheme.reranker["provider"]
    
    # ---- LLM ----
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取当前方案的 LLM 配置"""
        return self.scheme.llm.copy()
    
    def get_llm_provider_name(self) -> str:
        return self.scheme.llm["provider"]
    
    def is_llm_local(self) -> bool:
        return self.get_llm_provider_name() == "ollama"
    
    # ---- 汇总信息 ----
    
    def summary(self) -> Dict[str, Any]:
        """获取完整配置摘要"""
        return {
            "scheme": self.scheme_name,
            "label": self.scheme.label,
            "embedding": self.get_embedding_config(),
            "has_reranker": self.has_reranker(),
            "reranker": self.get_reranker_config(),
            "llm": self.get_llm_config(),
            "required_keys": self.scheme.required_keys,
            "missing_keys": [k for k in self.scheme.required_keys if not os.environ.get(k)],
            "is_embedding_local": self.is_embedding_local(),
            "is_llm_local": self.is_llm_local(),
            "is_fully_local": self.is_embedding_local() and self.is_llm_local(),
        }
    
    def print_summary(self):
        """打印配置摘要到日志"""
        s = self.summary()
        _logger.info(f"=== Deploy Config [{s['scheme']}]: {s['label']} ===")
        _logger.info(f"  Embedding: {s['embedding']['provider']} / {s['embedding']['model']} "
                     f"(local={s['is_embedding_local']})")
        _logger.info(f"  Reranker:  {s['reranker']['provider']+'/'+s['reranker']['model'] if s['reranker'] else 'None'}")
        _logger.info(f"  LLM:       {s['llm']['provider']} / {s['llm']['model']} "
                     f"(local={s['is_llm_local']})")
        missing = s["missing_keys"]
        if missing:
            _logger.warning(f"  Missing keys: {missing}")
        else:
            _logger.info(f"  All required keys present ✓")


# =============================================================================
# 全局单例
# =============================================================================

_active_config: Optional[ActiveConfig] = None


def get_active_config() -> ActiveConfig:
    """获取当前激活的配置单例"""
    global _active_config
    if _active_config is None:
        _active_config = ActiveConfig()
    return _active_config


def reload_config(scheme_name: str = None) -> ActiveConfig:
    """重新加载配置（可指定方案）"""
    global _active_config
    _active_config = ActiveConfig(scheme_name)
    return _active_config
