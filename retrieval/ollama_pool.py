"""
Ollama 连接池与心跳缓存
修复P1问题：减少无效的Ollama连接测试

功能：
- 心跳结果缓存（TTL可配置）
- 连接健康追踪
- 自动重连
"""
import time
import requests
from typing import Optional
from core.memory_config import CONFIG


class OllamaConnectionPool:
    """
    Ollama 连接池
    
    特性：
    - 心跳结果缓存，避免频繁检测
    - 连接健康状态追踪
    - 自动重连
    """
    
    def __init__(self, cache_ttl: int = 60):
        """
        Args:
            cache_ttl: 心跳缓存有效期（秒），默认60秒
        """
        self.cache_ttl = cache_ttl
        self._healthy = None
        self._last_check = 0
        self._error_count = 0
        self._ollama_url = CONFIG.get("ollama_url", "http://localhost:11434")
        self._model = CONFIG.get("embed_model", "bge-m3")
    
    def is_healthy(self) -> bool:
        """
        检查Ollama是否健康
        
        使用缓存避免频繁检测
        """
        current_time = time.time()
        
        # 缓存有效
        if self._healthy is not None and (current_time - self._last_check) < self.cache_ttl:
            return self._healthy
        
        # 执行真正检测
        self._healthy = self._check_connection()
        self._last_check = current_time
        
        return self._healthy
    
    def _check_connection(self) -> bool:
        """执行真正的连接检测"""
        try:
            # 检测API可用性
            response = requests.get(
                f"{self._ollama_url}/api/tags",
                timeout=5
            )
            
            if response.status_code != 200:
                self._error_count += 1
                return False
            
            # 检测模型是否可用
            try:
                import json
                models = json.loads(response.text).get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                # 检查embed模型
                if not any(self._model in name for name in model_names):
                    print(f"[OllamaPool] 模型 {self._model} 不可用，可用模型: {model_names}")
                    # 不算错误，只是模型可能不同
                    
            except Exception as e:
                print(f"[OllamaPool] 模型检测失败: {e}")
            
            self._error_count = 0  # 成功后重置错误计数
            return True
            
        except requests.exceptions.ConnectionError:
            self._error_count += 1
            print(f"[OllamaPool] 连接失败，错误次数: {self._error_count}")
            return False
        except requests.exceptions.Timeout:
            self._error_count += 1
            print(f"[OllamaPool] 连接超时，错误次数: {self._error_count}")
            return False
        except Exception as e:
            self._error_count += 1
            print(f"[OllamaPool] 未知错误: {e}")
            return False
    
    def get_embedding(self, text: str) -> Optional[list]:
        """
        获取文本嵌入（带连接检查）
        
        Returns:
            嵌入向量，或None（如果Ollama不可用）
        """
        if not self.is_healthy():
            return None
        
        try:
            response = requests.post(
                f"{self._ollama_url}/api/embeddings",
                json={
                    "model": self._model,
                    "prompt": text
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("embedding")
            
        except Exception as e:
            print(f"[OllamaPool] Embedding获取失败: {e}")
            # 标记为不健康，下次会重新检测
            self._healthy = None
        
        return None
    
    def force_check(self):
        """强制重新检测连接"""
        self._healthy = None
        self._last_check = 0
        return self.is_healthy()
    
    def get_stats(self) -> dict:
        """获取连接池统计"""
        return {
            "healthy": self._healthy,
            "last_check": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._last_check)),
            "cache_ttl": self.cache_ttl,
            "error_count": self._error_count,
            "ollama_url": self._ollama_url,
            "model": self._model
        }
    
    def reset(self):
        """重置连接池"""
        self._healthy = None
        self._last_check = 0
        self._error_count = 0


# 全局实例
_ollama_pool = None


def get_ollama_pool() -> OllamaConnectionPool:
    """获取Ollama连接池实例"""
    global _ollama_pool
    if _ollama_pool is None:
        _ollama_pool = OllamaConnectionPool()
    return _ollama_pool


# 别名
get_pool = get_ollama_pool
