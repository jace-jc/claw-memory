"""
Claw Memory 多模态支持模块
支持图像记忆的存储和检索

【规划】未来版本将支持:
- 图像描述生成 (image captioning)
- 跨模态检索 (clip embeddings)
- 语音转文字 (whisper)
"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class ImageMemory:
    """图像记忆数据结构"""
    image_path: str
    caption: str  # 图像描述
    ocr_text: Optional[str] = None  # OCR提取的文字
    entities: Optional[List[str]] = None  # 识别的实体
    memory_id: Optional[str] = None  # 关联的记忆ID


class MultimodalExtractor:
    """
    多模态信息提取器
    
    当前版本：仅支持结构化输入
    未来版本：集成 CLIP/Whisper/OCR
    """
    
    def extract_from_image(self, image_path: str) -> ImageMemory:
        """
        从图像中提取记忆信息
        
        当前版本需要手动提供caption
        未来版本将自动生成
        """
        return ImageMemory(
            image_path=image_path,
            caption="",  # 待实现：自动生成
            ocr_text=None,
            entities=None,
            memory_id=None
        )
    
    def extract_from_audio(self, audio_path: str) -> dict:
        """
        从音频中提取记忆信息
        
        当前版本返回None
        未来版本将集成Whisper
        """
        return None  # 待实现
    
    def generate_caption(self, image_path: str) -> str:
        """
        为图像生成描述
        
        当前版本返回空字符串
        未来版本将使用图像描述模型
        """
        return ""  # 待实现


def store_image_memory(
    image_path: str,
    caption: str,
    importance: float = 0.5,
    scope: str = "user"
) -> dict:
    """
    存储图像记忆
    
    Args:
        image_path: 图像路径
        caption: 图像描述
        importance: 重要性 0.0-1.0
        scope: 记忆范围
    
    Returns:
        存储结果
    """
    extractor = MultimodalExtractor()
    image_mem = extractor.extract_from_image(image_path)
    image_mem.caption = caption
    
    # 存储到主数据库
    from memory_main import get_db
    db = get_db()
    
    result = db.store({
        "content": f"[图片] {caption}",
        "type": "fact",
        "importance": importance,
        "scope": scope,
        "metadata": {
            "image_path": image_path,
            "caption": caption,
            "memory_type": "image"
        }
    })
    
    return result


# 导出单例
multimodal_extractor = MultimodalExtractor()
