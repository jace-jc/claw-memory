"""
多提供者统一 Embedder
支持 Ollama / Jina / OpenAI / SiliconFlow

由 memory_config_multi.py 驱动，自动适配当前部署方案。
"""
import os
import logging
from typing import Optional, List, Dict, Any

_logger = logging.getLogger("ClawMemory.MultiEmbed")

# 全局 embedder 实例
_embedder = None


class MultiEmbedder:
    """
    统一嵌入向量生成器。
    根据 memory_config_multi.py 的激活方案自动选择提供者。
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            from core.memory_config_multi import get_active_config
            config = get_active_config().get_embedding_config()
        
        self.provider = config.get("provider", "ollama")
        self.model = config.get("model", "bge-m3:latest")
        self.url = config.get("url", "http://localhost:11434/api/embeddings")
        self.dimensions = config.get("dimensions", 1024)
        self._client = None
    
    def embed(self, text: str) -> Optional[List[float]]:
        """生成单个文本的嵌入向量"""
        try:
            if self.provider == "ollama":
                return self._embed_ollama(text)
            elif self.provider == "jina":
                return self._embed_jina(text)
            elif self.provider == "openai":
                return self._embed_openai(text)
            elif self.provider == "siliconflow":
                return self._embed_siliconflow(text)
            else:
                _logger.warning(f"[MultiEmbed] Unknown provider: {self.provider}, falling back to ollama")
                return self._embed_ollama(text)
        except Exception as e:
            _logger.error(f"[MultiEmbed] embed error ({self.provider}): {e}")
            return None
    
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
    
    def _embed_ollama(self, text: str) -> Optional[List[float]]:
        """Ollama 本地嵌入"""
        import requests
        resp = requests.post(
            self.url,
            json={"model": self.model, "prompt": text},
            timeout=15
        )
        resp.raise_for_status()
        return resp.json().get("embedding", [])
    
    def _embed_jina(self, text: str) -> Optional[List[float]]:
        """Jina API 嵌入"""
        import requests
        api_key = os.environ.get("JINA_API_KEY")
        if not api_key:
            _logger.error("[MultiEmbed] JINA_API_KEY not set")
            return None
        resp = requests.post(
            self.url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "input": text
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [{}])[0].get("embedding", [])
    
    def _embed_openai(self, text: str) -> Optional[List[float]]:
        """OpenAI API 嵌入"""
        import requests
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            _logger.error("[MultiEmbed] OPENAI_API_KEY not set")
            return None
        resp = requests.post(
            self.url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "input": text
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [{}])[0].get("embedding", [])
    
    def _embed_siliconflow(self, text: str) -> Optional[List[float]]:
        """SiliconFlow API 嵌入"""
        import requests
        api_key = os.environ.get("SILICONFLOW_API_KEY")
        if not api_key:
            _logger.error("[MultiEmbed] SILICONFLOW_API_KEY not set")
            return None
        resp = requests.post(
            self.url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "input": text
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [{}])[0].get("embedding", [])
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            return bool(self.embed("health check test"))
        except Exception as e:
            logger.warning(f"健康检查失败: {e}")
            return False
    
    def __repr__(self):
        return f"MultiEmbed(provider={self.provider}, model={self.model}, dims={self.dimensions})"


def get_embedder() -> MultiEmbedder:
    """获取全局 MultiEmbedder 单例"""
    global _embedder
    if _embedder is None:
        _embedder = MultiEmbedder()
    return _embedder
