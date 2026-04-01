"""
附件持久化系统 - Attachment Persistence System
支持记忆附带原始文件（截图/代码片段/语音/文档）

功能：
1. 附件存储：按 memory_id 归类到目录
2. 元数据管理：JSON metadata 关联附件与记忆
3. 多格式支持：png/jpg/pdf/txt/code/音频/视频
4. 检索集成：可展示附件缩略图，减少 LLM token

目录结构：
memory/
  attachments/
    <memory_id>/
      <attachment_id>.<ext>
      metadata.json
    ...
  attachments_index.json  # 全局索引
"""
import os
import json
import uuid
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Union
from dataclasses import dataclass, asdict


# 配置文件路径
MEMORY_DIR = Path("/Users/claw/.openclaw/workspace/memory")
ATTACHMENTS_DIR = MEMORY_DIR / "attachments"
INDEX_FILE = ATTACHMENTS_DIR / "attachments_index.json"

# 支持的附件类型及对应 MIME
SUPPORTED_TYPES = {
    "image": ["png", "jpg", "jpeg", "gif", "webp", "bmp"],
    "document": ["pdf", "doc", "docx", "txt", "md"],
    "code": ["py", "js", "ts", "java", "cpp", "go", "rs", "sh", "yaml", "json"],
    "audio": ["mp3", "wav", "ogg", "m4a", "flac"],
    "video": ["mp4", "webm", "mov", "avi"],
    "archive": ["zip", "tar", "gz", "rar"],
}

# 每个附件最大大小（MB）
MAX_FILE_SIZE = {
    "image": 20,
    "document": 50,
    "code": 5,
    "audio": 30,
    "video": 200,
    "archive": 100,
}


@dataclass
class AttachmentMetadata:
    """附件元数据"""
    attachment_id: str
    memory_id: str
    filename: str
    file_type: str        # image/document/code/audio/video/archive
    mime_type: str
    size_bytes: int
    size_display: str      # 人类可读大小
    hash_sha256: str
    created_at: str
    description: str = ""
    tags: List[str] = None
    related_memory_ids: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.related_memory_ids is None:
            self.related_memory_ids = []


class AttachmentStore:
    """
    附件存储管理器
    
    管理记忆附件的存储、检索和元数据维护。
    附件按 memory_id 归类，支持多种格式。
    """
    
    def __init__(self, attachments_dir: Path = ATTACHMENTS_DIR):
        self.attachments_dir = attachments_dir
        self.index_file = attachments_dir / "attachments_index.json"
        
        # 确保目录存在
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载索引
        self.index = self._load_index()
    
    def _load_index(self) -> Dict:
        """加载附件索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"attachments": {}, "by_memory": {}, "by_type": {}}
    
    def _save_index(self):
        """保存附件索引"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)
    
    def _get_file_type(self, filename: str) -> Optional[str]:
        """根据文件扩展名判断类型"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        for ftype, exts in SUPPORTED_TYPES.items():
            if ext in exts:
                return ftype
        return None
    
    def _get_mime_type(self, filename: str) -> str:
        """获取 MIME 类型"""
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "md": "text/markdown",
            "py": "text/x-python",
            "js": "text/javascript",
            "ts": "text/typescript",
            "java": "text/x-java",
            "cpp": "text/x-c++src",
            "go": "text/x-go",
            "rs": "text/x-rust",
            "sh": "application/x-sh",
            "yaml": "text/yaml",
            "json": "application/json",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "ogg": "audio/ogg",
            "m4a": "audio/mp4",
            "flac": "audio/flac",
            "mp4": "video/mp4",
            "webm": "video/webm",
            "mov": "video/quicktime",
            "avi": "video/x-msvideo",
            "zip": "application/zip",
            "tar": "application/x-tar",
            "gz": "application/gzip",
            "rar": "application/vnd.rar",
        }
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        return mime_map.get(ext, "application/octet-stream")
    
    def _format_size(self, size_bytes: int) -> str:
        """人类可读的文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    def _compute_hash(self, file_path: Path) -> str:
        """计算文件 SHA256 哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def add_attachment(
        self,
        memory_id: str,
        file_path: Union[str, Path],
        description: str = "",
        tags: List[str] = None,
        related_memory_ids: List[str] = None
    ) -> Dict:
        """
        添加附件到记忆
        
        Args:
            memory_id: 关联的记忆ID
            file_path: 源文件路径
            description: 附件描述
            tags: 标签列表
            related_memory_ids: 关联的其他记忆ID
            
        Returns:
            添加结果
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        # 检查文件类型
        file_type = self._get_file_type(file_path.name)
        if not file_type:
            return {"success": False, "error": f"不支持的文件类型: {file_path.suffix}"}
        
        # 检查文件大小
        file_size = file_path.stat().st_size
        max_size = MAX_FILE_SIZE.get(file_type, 10) * 1024 * 1024
        if file_size > max_size:
            return {"success": False, "error": f"文件超过大小限制 ({MAX_FILE_SIZE[file_type]}MB)"}
        
        # 生成附件ID
        attachment_id = str(uuid.uuid4())[:12]
        
        # 创建记忆专属目录
        memory_dir = self.attachments_dir / memory_id
        memory_dir.mkdir(exist_ok=True)
        
        # 复制文件（保持原扩展名）
        dest_filename = f"{attachment_id}{file_path.suffix}"
        dest_path = memory_dir / dest_filename
        
        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            return {"success": False, "error": f"文件复制失败: {e}"}
        
        # 计算哈希
        file_hash = self._compute_hash(dest_path)
        
        # 创建元数据
        metadata = AttachmentMetadata(
            attachment_id=attachment_id,
            memory_id=memory_id,
            filename=file_path.name,
            file_type=file_type,
            mime_type=self._get_mime_type(file_path.name),
            size_bytes=file_size,
            size_display=self._format_size(file_size),
            hash_sha256=file_hash,
            created_at=datetime.now().isoformat(),
            description=description,
            tags=tags or [],
            related_memory_ids=related_memory_ids or []
        )
        
        # 保存元数据
        metadata_file = memory_dir / f"{attachment_id}.metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(asdict(metadata), f, indent=2, ensure_ascii=False)
        
        # 更新索引
        self.index["attachments"][attachment_id] = {
            "memory_id": memory_id,
            "filename": file_path.name,
            "file_type": file_type,
            "size_display": metadata.size_display,
            "metadata_file": str(metadata_file)
        }
        
        if memory_id not in self.index["by_memory"]:
            self.index["by_memory"][memory_id] = []
        self.index["by_memory"][memory_id].append(attachment_id)
        
        if file_type not in self.index["by_type"]:
            self.index["by_type"][file_type] = []
        self.index["by_type"][file_type].append(attachment_id)
        
        self._save_index()
        
        return {
            "success": True,
            "attachment_id": attachment_id,
            "memory_id": memory_id,
            "file_path": str(dest_path),
            "metadata": asdict(metadata),
            "size": metadata.size_display
        }
    
    def get_attachment(self, attachment_id: str) -> Optional[Dict]:
        """获取附件信息"""
        if attachment_id not in self.index["attachments"]:
            return None
        
        entry = self.index["attachments"][attachment_id]
        memory_id = entry["memory_id"]
        metadata_file = Path(entry["metadata_file"])
        
        if not metadata_file.exists():
            return None
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # 附件文件路径
        memory_dir = metadata_file.parent
        attachment_files = list(memory_dir.glob(f"{attachment_id}.*"))
        
        if attachment_files:
            metadata["file_path"] = str(attachment_files[0])
            metadata["url"] = f"file://{attachment_files[0]}"
        
        return metadata
    
    def get_memory_attachments(self, memory_id: str) -> List[Dict]:
        """获取某记忆的所有附件"""
        if memory_id not in self.index["by_memory"]:
            return []
        
        attachments = []
        for att_id in self.index["by_memory"][memory_id]:
            att = self.get_attachment(att_id)
            if att:
                attachments.append(att)
        
        return attachments
    
    def get_attachments_by_type(self, file_type: str) -> List[Dict]:
        """按类型获取附件"""
        if file_type not in self.index["by_type"]:
            return []
        
        attachments = []
        for att_id in self.index["by_type"][file_type]:
            att = self.get_attachment(att_id)
            if att:
                attachments.append(att)
        
        return attachments
    
    def delete_attachment(self, attachment_id: str) -> Dict:
        """删除附件"""
        if attachment_id not in self.index["attachments"]:
            return {"success": False, "error": "附件不存在"}
        
        entry = self.index["attachments"][attachment_id]
        memory_id = entry["memory_id"]
        
        # 删除文件
        memory_dir = self.attachments_dir / memory_id
        files_to_delete = list(memory_dir.glob(f"{attachment_id}.*"))
        for f in files_to_delete:
            f.unlink()
        
        # 从索引移除
        del self.index["attachments"][attachment_id]
        if memory_id in self.index["by_memory"]:
            self.index["by_memory"][memory_id] = [
                a for a in self.index["by_memory"][memory_id] if a != attachment_id
            ]
        
        file_type = entry["file_type"]
        if file_type in self.index["by_type"]:
            self.index["by_type"][file_type] = [
                a for a in self.index["by_type"][file_type] if a != attachment_id
            ]
        
        self._save_index()
        
        return {"success": True, "attachment_id": attachment_id}
    
    def link_to_memory(
        self,
        attachment_id: str,
        related_memory_id: str,
        bidirectional: bool = False
    ) -> Dict:
        """将附件关联到另一个记忆"""
        metadata = self.get_attachment(attachment_id)
        if not metadata:
            return {"success": False, "error": "附件不存在"}
        
        if related_memory_id not in metadata.get("related_memory_ids", []):
            metadata.setdefault("related_memory_ids", []).append(related_memory_id)
            
            # 保存更新后的元数据
            memory_dir = Path(self.index["attachments"][attachment_id]["metadata_file"]).parent
            metadata_file = memory_dir / f"{attachment_id}.metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            # 更新索引
            self.index["attachments"][attachment_id] = {
                **self.index["attachments"][attachment_id],
                "related_memory_ids": metadata["related_memory_ids"]
            }
            self._save_index()
        
        if bidirectional:
            # 关联到另一个记忆（通常在另一个记忆的目录下创建一个链接文件）
            related_dir = self.attachments_dir / related_memory_id
            related_dir.mkdir(exist_ok=True)
            
            link_file = related_dir / f"{attachment_id}.link.json"
            with open(link_file, 'w') as f:
                json.dump({
                    "linked_from": related_memory_id,
                    "linked_to": attachment_id,
                    "created_at": datetime.now().isoformat()
                }, f)
        
        return {"success": True, "attachment_id": attachment_id, "related_memory_id": related_memory_id}
    
    def search_attachments(self, query: str, file_type: str = None) -> List[Dict]:
        """
        搜索附件
        
        Args:
            query: 搜索关键词（匹配描述和标签）
            file_type: 可选，限定文件类型
            
        Returns:
            匹配的附件列表
        """
        results = []
        
        attachment_ids = self.index["by_type"].get(file_type, []) if file_type else self.index["attachments"].keys()
        
        for att_id in attachment_ids:
            att = self.get_attachment(att_id)
            if not att:
                continue
            
            # 匹配描述
            if query.lower() in att.get("description", "").lower():
                results.append(att)
                continue
            
            # 匹配标签
            if any(query.lower() in tag.lower() for tag in att.get("tags", [])):
                results.append(att)
                continue
            
            # 匹配文件名
            if query.lower() in att.get("filename", "").lower():
                results.append(att)
        
        return results
    
    def get_stats(self) -> Dict:
        """获取附件统计"""
        total_size = 0
        type_counts = {}
        
        for att_id, entry in self.index["attachments"].items():
            att = self.get_attachment(att_id)
            if att:
                total_size += att.get("size_bytes", 0)
                ftype = entry["file_type"]
                type_counts[ftype] = type_counts.get(ftype, 0) + 1
        
        return {
            "total_attachments": len(self.index["attachments"]),
            "total_size_bytes": total_size,
            "total_size_display": self._format_size(total_size),
            "by_memory_count": len(self.index["by_memory"]),
            "by_type": type_counts,
            "attachments_dir": str(self.attachments_dir)
        }


# 全局实例
_attachment_store = None


def get_attachment_store() -> AttachmentStore:
    """获取全局附件存储实例"""
    global _attachment_store
    if _attachment_store is None:
        _attachment_store = AttachmentStore()
    return _attachment_store


# ============================================================
# 独立函数接口
# ============================================================

def add_attachment(
    memory_id: str,
    file_path: Union[str, Path],
    description: str = "",
    tags: List[str] = None
) -> Dict:
    """添加附件"""
    store = get_attachment_store()
    return store.add_attachment(memory_id, file_path, description, tags)


def get_attachment(attachment_id: str) -> Optional[Dict]:
    """获取附件"""
    store = get_attachment_store()
    return store.get_attachment(attachment_id)


def get_memory_attachments(memory_id: str) -> List[Dict]:
    """获取记忆的所有附件"""
    store = get_attachment_store()
    return store.get_memory_attachments(memory_id)


def delete_attachment(attachment_id: str) -> Dict:
    """删除附件"""
    store = get_attachment_store()
    return store.delete_attachment(attachment_id)


def link_attachment(attachment_id: str, related_memory_id: str, bidirectional: bool = False) -> Dict:
    """关联附件到另一个记忆"""
    store = get_attachment_store()
    return store.link_to_memory(attachment_id, related_memory_id, bidirectional)


def search_attachments(query: str, file_type: str = None) -> List[Dict]:
    """搜索附件"""
    store = get_attachment_store()
    return store.search_attachments(query, file_type)
