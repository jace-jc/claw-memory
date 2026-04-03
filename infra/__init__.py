"""
Infra package: Infrastructure utilities
Phase 4: re-exports from original locations
"""
from infra.memory_backup import (
    memory_backup, quick_backup, incremental_backup, auto_backup_schedule,
    _create_backup, _list_backups, _restore_backup, _delete_backup,
    _export_json, _import_json
)
from infra.wal_protocol import WALProtocol
from infra.attachment_store import (
    AttachmentStore, AttachmentMetadata, get_attachment_store,
    add_attachment, get_attachment, get_memory_attachments,
    delete_attachment, link_attachment, search_attachments
)
from infra.performance import get_monitor, record_performance, PerformanceMonitor

__all__ = [
    # Backup
    "memory_backup",
    "quick_backup",
    "incremental_backup",
    "auto_backup_schedule",
    "_create_backup",
    "_list_backups",
    "_restore_backup",
    "_delete_backup",
    "_export_json",
    "_import_json",
    # WAL
    "WALProtocol",
    # Attachment
    "AttachmentStore",
    "AttachmentMetadata",
    "get_attachment_store",
    "add_attachment",
    "get_attachment",
    "get_memory_attachments",
    "delete_attachment",
    "link_attachment",
    "search_attachments",
    # Performance
    "get_monitor",
    "record_performance",
    "PerformanceMonitor",
]
