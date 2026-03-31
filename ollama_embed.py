"""
Ollama 嵌入模块 - 使用 bge-m3 生成向量
"""
import requests
import numpy as np
from memory_config import CONFIG

class OllamaEmbedder:
    def __init__(self, model=None, url=None):
        self.model = model or CONFIG["embed_model"]
        self.url = (url or CONFIG["ollama_url"]) + "/api/embeddings"
    
    def embed(self, text: str) -> list[float]:
        """生成单个文本的嵌入向量"""
        try:
            response = requests.post(
                self.url,
                json={"model": self.model, "prompt": text},
                timeout=15  # 减少超时，快速失败
            )
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            print(f"[OllamaEmbedder] embed error: {e}")
            return []
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入向量"""
        results = []
        for text in texts:
            vec = self.embed(text)
            if vec:
                results.append(vec)
            else:
                # 失败时返回零向量
                results.append([0.0] * 1024)  # bge-m3 维度
        return results
    
    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

# 全局实例
embedder = OllamaEmbedder()
