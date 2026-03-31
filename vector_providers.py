"""
向量提供者模块 - Vector Providers
支持多提供者：Ollama / OpenAI / 阿里云 / 本地备用

架构：
1. Ollama（本地，默认主选）
2. OpenAI（云端，备选）
3. 阿里云（云端，备选）
4. SimpleHash（本地备用，最后备选）

配置：
    VECTOR_PROVIDERS = {
        "primary": "ollama",
        "fallback": "openai",  # 可选
        "providers": {
            "ollama": {...},
            "openai": {...},
        }
    }
"""
import hashlib
import numpy as np
from typing import List, Optional, Dict
import logging

_logger = logging.getLogger("ClawMemory.VectorProviders")

# 默认配置
DEFAULT_CONFIG = {
    "primary": "ollama",
    "fallback": None,  # 不使用备选
    "providers": {
        "ollama": {
            "model": "bge-m3",
            "url": "http://localhost:11434",
            "timeout": 10,
            "dimensions": 1024  # bge-m3
        },
        # 其他提供者可以在这里添加
    },
    # 当所有提供者都失败时的最后备选
    "emergency_fallback": "simple_hash"  # 简单哈希（始终可用）
}


class VectorProvider:
    """
    向量生成提供者基类
    """
    def __init__(self, config: dict):
        self.config = config
        self.name = "base"
        self.dimensions = config.get("dimensions", 1024)
    
    def embed(self, text: str) -> Optional[List[float]]:
        """生成单个文本的嵌入向量"""
        raise NotImplementedError
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成嵌入向量"""
        results = []
        for text in texts:
            vec = self.embed(text)
            if vec:
                results.append(vec)
            else:
                results.append([0.0] * self.dimensions)
        return results
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            return len(self.embed("test")) > 0
        except:
            return False


class OllamaProvider(VectorProvider):
    """Ollama本地向量提供者"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "ollama"
        self.model = config.get("model", "bge-m3")
        self.url = config.get("url", "http://localhost:11434") + "/api/embeddings"
        self.timeout = config.get("timeout", 10)
    
    def embed(self, text: str) -> Optional[List[float]]:
        try:
            import requests
            response = requests.post(
                self.url,
                json={"model": self.model, "prompt": text},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            _logger.warning(f"Ollama embed failed: {e}")
            return None
    
    def health_check(self) -> bool:
        try:
            import requests
            response = requests.get(
                self.url.replace("/api/embeddings", "/api/tags"),
                timeout=5
            )
            return response.status_code == 200
        except:
            return False


class OpenAIProvider(VectorProvider):
    """OpenAI云端向量提供者"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "openai"
        self.model = config.get("model", "text-embedding-3-small")
        self.api_key = config.get("api_key", "")
        self.dimensions = config.get("dimensions", 1536)
    
    def embed(self, text: str) -> Optional[List[float]]:
        if not self.api_key:
            _logger.warning("OpenAI API key not configured")
            return None
        
        try:
            import requests
            response = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": text,
                    "dimensions": self.dimensions
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [{}])[0].get("embedding", [])
        except Exception as e:
            _logger.warning(f"OpenAI embed failed: {e}")
            return None


class SimpleHashProvider(VectorProvider):
    """
    简单哈希提供者（最后的备用方案）
    将文本转为确定性哈希向量
    质量较低但始终可用
    """
    
    def __init__(self, config: dict = None):
        super().__init__(config or {})
        self.name = "simple_hash"
        self.dimensions = config.get("dimensions", 1024) if config else 1024
    
    def embed(self, text: str) -> Optional[List[float]]:
        """生成基于哈希的伪向量"""
        # 使用多个哈希函数生成确定性向量
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        # 将哈希字节转换为浮点数向量
        vec = []
        for i in range(min(len(hash_bytes), self.dimensions)):
            # 将字节值转换为0-1之间的浮点数
            vec.append(hash_bytes[i] / 255.0)
        
        # 填充剩余维度
        while len(vec) < self.dimensions:
            vec.append(0.0)
        
        # L2归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = [v / norm for v in vec]
        
        return vec
    
    def health_check(self) -> bool:
        """SimpleHash始终可用"""
        return True


class VectorProviderManager:
    """
    向量提供者管理器
    支持主/备自动切换
    """
    
    def __init__(self, config: dict = None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.providers: Dict[str, VectorProvider] = {}
        self._init_providers()
        self._current = self.config.get("primary", "ollama")
        self._fallback = self.config.get("fallback")
    
    def _init_providers(self):
        """初始化所有提供者"""
        provider_configs = self.config.get("providers", {})
        
        # 注册 Ollama
        if "ollama" in provider_configs:
            self.providers["ollama"] = OllamaProvider(provider_configs["ollama"])
        
        # 注册 OpenAI
        if "openai" in provider_configs:
            self.providers["openai"] = OpenAIProvider(provider_configs["openai"])
        
        # 注册 SimpleHash（始终可用）
        self.providers["simple_hash"] = SimpleHashProvider()
    
    def embed(self, text: str, force_provider: str = None) -> Optional[List[float]]:
        """
        生成嵌入向量，自动处理降级
        
        Args:
            text: 文本
            force_provider: 强制使用某个提供者（测试用）
        
        Returns:
            向量列表
        """
        # 1. 尝试当前提供者
        if force_provider:
            provider = self.providers.get(force_provider)
            if provider:
                result = provider.embed(text)
                if result:
                    return result
        
        # 2. 尝试主提供者
        primary = self.providers.get(self._current)
        if primary:
            result = primary.embed(text)
            if result:
                return result
        
        # 3. 尝试备用提供者
        if self._fallback and self._fallback != self._current:
            fallback = self.providers.get(self._fallback)
            if fallback:
                _logger.info(f"Primary {self._current} failed, trying fallback {self._fallback}")
                result = fallback.embed(text)
                if result:
                    self._current = self._fallback  # 标记当前使用备用
                    return result
        
        # 4. 最后备选：SimpleHash
        simple = self.providers.get("simple_hash")
        if simple:
            _logger.warning("All providers failed, using emergency SimpleHash fallback")
            return simple.embed(text)
        
        return None
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成嵌入向量"""
        return [self.embed(text) or [0.0] * self.dimensions for text in texts]
    
    @property
    def dimensions(self) -> int:
        """获取当前提供者的向量维度"""
        provider = self.providers.get(self._current)
        if provider:
            return provider.dimensions
        return 1024
    
    @property
    def current_provider(self) -> str:
        """获取当前提供者名称"""
        return self._current
    
    def get_stats(self) -> dict:
        """获取提供者状态"""
        stats = {}
        for name, provider in self.providers.items():
            stats[name] = {
                "available": provider.health_check(),
                "dimensions": provider.dimensions
            }
        return {
            "current": self._current,
            "fallback": self._fallback,
            "providers": stats
        }
    
    def set_primary(self, provider: str):
        """设置主提供者"""
        if provider in self.providers:
            self._current = provider
            _logger.info(f"Primary provider set to {provider}")
    
    def set_fallback(self, provider: str):
        """设置备用提供者"""
        if provider in self.providers or provider is None:
            self._fallback = provider
            _logger.info(f"Fallback provider set to {provider}")


# 全局实例
_provider_manager = None


def get_vector_manager() -> VectorProviderManager:
    """获取向量管理器单例"""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = VectorProviderManager()
    return _provider_manager


def embed_text(text: str) -> Optional[List[float]]:
    """便捷函数：生成单个文本的嵌入向量"""
    return get_vector_manager().embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """便捷函数：批量生成嵌入向量"""
    return get_vector_manager().embed_batch(texts)
