"""
Claw Memory 错误处理模块
提供友好的错误信息和解决方案
"""

from typing import Optional, Dict
from enum import Enum


class MemoryErrorType(Enum):
    """记忆系统错误类型"""
    # 连接错误
    OLLAMA_NOT_CONNECTED = "ollama_not_connected"
    DATABASE_NOT_INITIALIZED = "database_not_initialized"
    
    # 存储错误
    STORE_FAILED = "store_failed"
    MEMORY_NOT_FOUND = "memory_not_found"
    
    # 搜索错误
    SEARCH_FAILED = "search_failed"
    EMPTY_QUERY = "empty_query"
    
    # 权限错误
    PERMISSION_DENIED = "permission_denied"
    
    # 通用错误
    UNKNOWN = "unknown"


# 别名，保持向后兼容
MemoryError = MemoryErrorType


# 错误信息映射
ERROR_MESSAGES = {
    MemoryError.OLLAMA_NOT_CONNECTED: {
        "user": "无法连接到 Ollama 服务",
        "detail": "Ollama 是本地运行的 AI 模型服务，用于生成向量嵌入",
        "solution": "请确保 Ollama 已启动：ollama serve"
    },
    MemoryError.DATABASE_NOT_INITIALIZED: {
        "user": "记忆数据库未初始化",
        "detail": "系统需要先初始化才能使用",
        "solution": "调用 get_db() 初始化数据库"
    },
    MemoryError.STORE_FAILED: {
        "user": "记忆存储失败",
        "detail": "无法将记忆保存到数据库",
        "solution": "检查磁盘空间和数据库权限"
    },
    MemoryError.MEMORY_NOT_FOUND: {
        "user": "未找到指定记忆",
        "detail": "请求的记忆不存在或已被删除",
        "solution": "检查记忆ID是否正确"
    },
    MemoryError.SEARCH_FAILED: {
        "user": "搜索失败",
        "detail": "检索记忆时发生错误",
        "solution": "请稍后重试，或检查系统日志"
    },
    MemoryError.EMPTY_QUERY: {
        "user": "搜索词为空",
        "detail": "请提供搜索关键词",
        "solution": "输入有效的搜索词"
    },
    MemoryError.PERMISSION_DENIED: {
        "user": "权限不足",
        "detail": "没有权限执行此操作",
        "solution": "检查 scope 权限设置"
    },
    MemoryError.UNKNOWN: {
        "user": "发生未知错误",
        "detail": "一个意料之外的问题发生了",
        "solution": "请查看系统日志或联系开发者"
    }
}


class MemoryErrorException(Exception):
    """记忆系统异常"""
    
    def __init__(
        self,
        error_type: MemoryErrorType,
        message: str = None,
        detail: str = None,
        solution: str = None,
        cause: Exception = None
    ):
        self.error_type = error_type
        self.message = message or ERROR_MESSAGES[error_type]["user"]
        self.detail = detail or ERROR_MESSAGES[error_type]["detail"]
        self.solution = solution or ERROR_MESSAGES[error_type]["solution"]
        self.cause = cause
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "error": self.error_type.value,
            "message": self.message,
            "detail": self.detail,
            "solution": self.solution,
            "success": False
        }
    
    def __str__(self) -> str:
        """友好的错误字符串"""
        lines = [
            f"❌ {self.message}",
            f"   原因: {self.detail}",
            f"   解决: {self.solution}"
        ]
        if self.cause:
            lines.append(f"   详情: {str(self.cause)}")
        return "\n".join(lines)


def handle_memory_error(error: Exception, operation: str = "操作") -> Dict:
    """
    处理记忆系统错误的快捷函数
    
    Args:
        error: 原始异常
        operation: 正在进行的操作
        
    Returns:
        标准错误响应字典
    """
    if isinstance(error, MemoryErrorException):
        return error.to_dict()
    
    # 根据异常类型判断
    error_str = str(error).lower()
    
    if "ollama" in error_str or "connection" in error_str:
        err_type = MemoryError.OLLAMA_NOT_CONNECTED
    elif "database" in error_str or "lance" in error_str:
        err_type = MemoryError.DATABASE_NOT_INITIALIZED
    elif "timeout" in error_str:
        err_type = MemoryError.SEARCH_FAILED
    else:
        err_type = MemoryError.UNKNOWN
    
    exc = MemoryErrorException(error_type=err_type, cause=error)
    return exc.to_dict()


# 便捷函数
def raise_error(error_type: MemoryError, **kwargs):
    """抛出记忆系统异常"""
    raise MemoryErrorException(error_type=error_type, **kwargs)


def format_error_response(error: Exception) -> str:
    """
    格式化错误响应（用于控制台输出）
    """
    if isinstance(error, MemoryErrorException):
        return str(error)
    
    # 未知错误
    return f"❌ 操作失败\n   原因: {str(error)}\n   解决: 请稍后重试"
