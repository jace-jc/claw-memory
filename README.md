# Claw Memory

A local-first AI memory system with RRF search, knowledge graph, and temporal tracking.

## Features

- **RRF 5-Channel Fusion**: Vector + BM25 + Importance + Knowledge Graph + Temporal
- **Cross-Encoder Reranking**: Semantic-level result refinement
- **Knowledge Graph**: Entity disambiguation and transitive reasoning
- **Temporal Tracking**: Time-aware memory decay and prioritization
- **E2E Encryption**: Zero-knowledge storage encryption
- **Adaptive Weights**: Learning from user feedback

## Installation

```bash
# From source
pip install .

# With embedding support
pip install .[embedding-ollama]
pip install .[embedding-openai]
```

## Quick Start

```python
from claw_memory import get_db

# Initialize
db = get_db()

# Store a memory
db.store({
    "content": "用户的名字叫张三",
    "type": "fact",
    "importance": 0.9
})

# Search
results = db.search_rrf("用户名字", limit=5)

# Get stats
stats = db.get_stats()
```

## Architecture

```
┌─────────────────────────────────────────┐
│           CAPTURE (Input)                │
│  rules → real-time extract → deep extract │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           STORE (Hot/Warm/Cold)          │
│  SESSION-STATE → LanceDB → Markdown    │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           RETRIEVE (RRF 5-Channel)      │
│  Vector + BM25 + Importance + KG + Time │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           RERANK (Cross-Encoder)        │
└─────────────────────────────────────────┘
```

## Documentation

See [API_REFERENCE.md](API_REFERENCE.md) for detailed API documentation.

## License

MIT
