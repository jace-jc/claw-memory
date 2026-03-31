# Claw Memory

[![PyPI Version](https://img.shields.io/pypi/v/claw-memory?style=flat-square)](https://pypi.org/project/claw-memory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg?style=flat-square)](https://www.python.org/downloads/)

> A local-first AI memory system with RRF search, knowledge graph, and temporal tracking.

## Features

- **RRF 5-Channel Fusion**: Vector + BM25 + Importance + Knowledge Graph + Temporal
- **Cross-Encoder Reranking**: Semantic-level result refinement
- **Knowledge Graph**: Entity disambiguation and transitive reasoning
- **Temporal Tracking**: Time-aware memory decay and prioritization
- **E2E Encryption**: Zero-knowledge storage encryption
- **Adaptive Weights**: Learning from user feedback

## Benchmarks

| Metric | Claw Memory | Mem0 LOCOMO | Gap |
|--------|-------------|-------------|-----|
| **MRR** | 0.792 | 0.669 | +18.4% ✅| |

See [Benchmark Results](./benchmark_results/) for detailed analysis.

## Installation

```bash
pip install claw-memory
```

Or from source:

```bash
git clone https://github.com/jace-jc/claw-memory.git
cd claw-memory
pip install .
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
│  Vector + BM25 + Importance + KG + Time  │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           RERANK (Cross-Encoder)        │
└─────────────────────────────────────────┘
```

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `fact` | Factual information | "用户的名字叫张三" |
| `preference` | User preferences | "用户喜欢川菜" |
| `decision` | Decisions made | "用户选择使用React" |
| `lesson` | Lessons learned | "用户从错误中学到..." |
| `entity` | Entity information | "用户的朋友小李" |
| `task_state` | Task progress | "用户的项目完成80%" |

## Configuration

```python
from claw_memory import CONFIG

# Default configuration
CONFIG = {
    "db_path": "~/.openclaw/workspace/memory/memory.lanceDB",
    "vector_dims": 1024,
    "default_limit": 10,
    "max_limit": 100,
    "embedding_model": "bge-m3",
    "default_importance": 0.5,
}
```

## API Reference

See [API_REFERENCE.md](API_REFERENCE.md) for detailed API documentation.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run benchmark
python -m benchmark_suite
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## GitHub

https://github.com/jace-jc/claw-memory
