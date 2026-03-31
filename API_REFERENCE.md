# Claw Memory API Reference

> Version: 2.8.0  
> Last Updated: 2026-03-31

## Quick Start

```python
from claw_memory import get_db

db = get_db()

# Store a memory
db.store({
    "content": "用户的名字叫张三",
    "type": "fact",
    "importance": 0.9
})

# Search memories
results = db.search("用户名字", limit=5)

# Get memory stats
stats = db.get_stats()
```

---

## Core API

### `db.store(memory: dict) -> bool`

Store a new memory.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `content` | string | ✅ | - | Memory content (1-10000 chars) |
| `type` | string | ❌ | "fact" | Type: fact/preference/decision/lesson/entity/task_state |
| `importance` | float | ❌ | 0.5 | Importance 0-1 |
| `scope` | string | ❌ | None | Scope hash for multi-tenancy |
| `metadata` | dict | ❌ | None | Extra metadata |

**Returns:** `bool` - True if stored successfully

**Example:**
```python
db.store({
    "content": "用户喜欢使用React框架",
    "type": "preference",
    "importance": 0.8,
    "metadata": {"source": "chat"}
})
```

---

### `db.search(query: str, limit: int = 5, use_rerank: bool = False) -> list`

Search memories by vector similarity.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | string | ✅ | - | Search query |
| `limit` | int | ❌ | 5 | Max results (1-100) |
| `use_rerank` | bool | ❌ | False | Use Cross-Encoder reranking |
| `min_importance` | float | ❌ | 0.0 | Minimum importance filter |

**Returns:** `list[dict]` - List of memory records with scores

---

### `db.search_rrf(query: str, limit: int = 5, k: int = 60, use_adaptive: bool = True) -> list`

Search using RRF (Reciprocal Rank Fusion) with 5 channels.

**Channels:**
1. **Vector** - Semantic similarity (weight: 0.40)
2. **BM25** - Keyword matching (weight: 0.25)
3. **Importance** - Stored importance score (weight: 0.20)
4. **KG** - Knowledge Graph relations (weight: 0.15)
5. **Temporal** - Time-based relevance (dynamic)

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | string | ✅ | - | Search query |
| `limit` | int | ❌ | 5 | Max results |
| `k` | int | ❌ | 60 | RRF parameter |
| `use_adaptive` | bool | ❌ | True | Use adaptive weights |

**Returns:** `list[dict]` - Fused and ranked results

---

### `db.search_cached(query: str, limit: int = 5, use_cache: bool = True, **kwargs) -> list`

Search with LRU cache.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | string | ✅ | - | Search query |
| `limit` | int | ❌ | 5 | Max results |
| `use_cache` | bool | ❌ | True | Enable caching |
| `ttl` | int | ❌ | 300 | Cache TTL in seconds |

---

### `db.recall(entity_name: str, relation_type: str = None, limit: int = 5) -> list`

Recall memories related to an entity using KG traversal.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `entity_name` | string | ✅ | - | Entity name |
| `relation_type` | string | ❌ | None | Filter by relation type |
| `limit` | int | ❌ | 5 | Max results |

**Returns:** `list[dict]` - Related memories

---

### `db.delete(memory_id: str) -> bool`

Delete a memory by ID.

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `memory_id` | string | ✅ | - | Memory UUID |

**Returns:** `bool` - True if deleted

---

### `db.get_stats() -> dict`

Get memory statistics.

**Returns:**
```python
{
    "total": 100,
    "by_type": {"fact": 50, "preference": 30, ...},
    "avg_importance": 0.65,
    "oldest_memory": "2026-01-15T10:30:00",
    "newest_memory": "2026-03-31T21:00:00"
}
```

---

### `db.get_health() -> dict`

Get system health status.

**Returns:**
```python
{
    "status": "healthy",  # healthy/degraded/unhealthy
    "total_memories": 100,
    "vector_db_status": "connected",
    "knowledge_graph_status": "11 nodes, 5 edges",
    "cache_hit_rate": 0.75,
    "issues": []
}
```

---

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `fact` | Factual information | "用户的名字叫张三" |
| `preference` | User preferences | "用户喜欢川菜" |
| `decision` | Decisions made | "用户选择使用React" |
| `lesson` | Lessons learned | "用户从错误中学到..." |
| `entity` | Entity information | "用户的朋友小李" |
| `task_state` | Task progress | "用户的项目完成80%" |

---

## Configuration

Memory configuration is in `memory_config.py`:

```python
CONFIG = {
    "db_path": "~/.openclaw/workspace/memory/memory.lanceDB",
    "vector_dims": 1024,
    "default_limit": 10,
    "max_limit": 100,
    "embedding_model": "bge-m3",
    "default_importance": 0.5,
    "min_importance_for_search": 0.3,
    "hot_ttl_hours": 24,
    "warm_ttl_days": 30,
    "cold_ttl_days": 365,
}
```

---

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| `MEMORY_NOT_FOUND` | Memory not found | Invalid memory_id |
| `STORE_FAILED` | Failed to store | Database write error |
| `SEARCH_FAILED` | Search failed | Query execution error |
| `ENCRYPTION_FAILED` | Encryption error | Crypto operation failed |
| `INVALID_TYPE` | Invalid memory type | Unknown type value |

---

## Examples

### Store and Search
```python
from claw_memory import get_db

db = get_db()

# Store
db.store({
    "content": "用户喜欢使用Python编程",
    "type": "preference",
    "importance": 0.9
})

# Search
results = db.search_rrf("用户会什么编程语言", limit=5)
for r in results:
    print(f"[{r.get('score', 0):.2f}] {r['content']}")
```

### Batch Operations
```python
from claw_memory import get_db

db = get_db()

# Batch store
memories = [
    {"content": "事实1", "type": "fact"},
    {"content": "事实2", "type": "fact"},
    {"content": "偏好1", "type": "preference"},
]

for mem in memories:
    db.store(mem)
```

### Temporal Search
```python
from claw_memory import get_db

db = get_db()

# Recent memories
results = db.search_rrf("用户最近在做什么", limit=5)

# Past preferences
results = db.search_rrf("用户以前喜欢什么", limit=5)
```
