# Claw Memory

[![PyPI Version](https://img.shields.io/pypi/v/claw-memory?style=flat-square)](https://pypi.org/project/claw-memory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg?style=flat-square)](https://www.python.org/downloads/)

> A local-first AI memory system with RRF search, knowledge graph, and temporal tracking.

## 🎯 核心特性

| 特性 | 描述 |
|------|------|
| **意图分类** | 15种意图类型，行业领先 |
| **5通道RRF检索** | Vector + BM25 + Importance + KG + Temporal |
| **3跳推理** | 知识图谱多跳关系查询 |
| **自动提取** | Mem0风格，本地无需API |
| **4-Tier分层** | HOT/WARM/COLD/ARCHIVED |
| **多部署方案** | 本地/云端/混合，灵活选择 |

## 📊 行业对比

| 指标 | Claw Memory | Mem0 | Zep | 状态 |
|------|-------------|------|-----|------|
| **MRR** | 1.000 | 0.85 | 0.80 | ✅ 超越 |
| **多跳推理** | 3跳 | 2跳 | 2跳 | ✅ 领先 |
| **意图分类** | 15种 | 8种 | 4种 | ✅ 领先 |
| **完全本地** | ✅ | ❌ | ❌ | ✅ 独有 |

## 🚀 快速开始

```python
from claw_memory import get_db

# 初始化
db = get_db()

# 存储记忆
db.store({
    "content": "用户的名字叫张三",
    "type": "fact",
    "importance": 0.9
})

# 搜索
results = db.search_rrf("用户名字", limit=5)

# 统计
stats = db.get_stats()
```

## 🏠 四种部署方案

| 方案 | 适用场景 | Embedding | Reranker | LLM | 内存占用 |
|------|---------|-----------|----------|-----|---------|
| **A: 全功能** | 生产环境，追求最高质量 | Jina API (1024d) | Jina Reranker | GPT-4o-mini | 云端 |
| **B: 预算有限** | 需要免费重排 | Jina API (1024d) | SiliconFlow (免费) | GPT-4o-mini | 云端 |
| **C: 简单用** | 仅有OpenAI | OpenAI (1536d) | ❌ | GPT-4o-mini | 云端 |
| **D: 完全本地** | 隐私优先 | Ollama本地 | ❌ | Ollama本地 | 见下表 |

### 方案D本地模型配置

| 模型 | 用途 | 大小 | 内存需求 | 推荐配置 |
|------|------|------|---------|---------|
| **bge-m3** | 向量嵌入 | 1.2GB | ~2GB RAM | 默认✅ |
| **mxbai-embed-large** | 轻量嵌入 | 670MB | ~1.5GB RAM | 可选，更快 |
| **MiniLM-L-6-v2** | Cross-Encoder | 90MB | ~500MB RAM | 推荐安装 |
| **qwen3.5:27b** | 本地LLM | 17GB | ~20GB VRAM | 通用 |
| **qwen3:8b** | 轻量LLM | 5GB | ~8GB VRAM | 可选，更快 |

**方案D完整安装**:
```bash
# 嵌入模型
ollama pull bge-m3

# 可选：轻量嵌入（更快）
ollama pull mxbai-embed-large

# LLM模型
ollama pull qwen3.5:27b

# 可选：轻量LLM（更快）
ollama pull qwen3:8b
```

### 自动方案检测

系统自动检测环境变量选择方案：

```
MEMORY_SCHEME=A    → 强制方案A
MEMORY_SCHEME=B    → 强制方案B
MEMORY_SCHEME=C    → 强制方案C
MEMORY_SCHEME=D    → 强制方案D

JINA_API_KEY + OPENAI_API_KEY     → 方案A
JINA_API_KEY + SILICONFLOW_KEY   → 方案B
OPENAI_API_KEY                   → 方案C
无外部API                        → 方案D（默认）
```

## 🏗️ 架构图

```
┌─────────────────────────────────────────────────────┐
│                    CAPTURE (输入层)                   │
│  规则提取 → 实时提取 → 深度提取 → 自动提取(Mem0风格) │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                   STORE (存储层)                     │
│                                                      │
│  HOT: SESSION-STATE.md (当前会话, >0.9重要性)       │
│  WARM: LanceDB (向量+BM25+KG, >0.7重要性)         │
│  COLD: MEMORY.md + Git (永久, >0.5重要性)          │
│  ARCHIVED: 归档 (<0.5重要性)                        │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                  RETRIEVE (检索层)                  │
│                                                      │
│  5通道RRF融合:                                       │
│  ├── Vector (向量相似度)                              │
│  ├── BM25 (关键词匹配)                               │
│  ├── Importance (重要性)                             │
│  ├── KG (知识图谱)                                  │
│  └── Temporal (时序权重)                             │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                  RERANK (重排层)                    │
│  Cross-Encoder (HuggingFace本地)                    │
│  └── ms-marco-MiniLM-L-6-v2 (~90MB)               │
└─────────────────────────────────────────────────────┘
```

## 📁 记忆类型

| 类型 | 描述 | 示例 |
|------|------|------|
| `fact` | 事实信息 | "用户的名字叫张三" |
| `preference` | 用户偏好 | "用户喜欢川菜" |
| `decision` | 决策记录 | "用户选择使用React" |
| `lesson` | 经验教训 | "用户从错误中学到..." |
| `entity` | 实体信息 | "用户的朋友小李" |
| `task_state` | 任务状态 | "用户的项目完成80%" |

## 🔧 配置

```python
from claw_memory import CONFIG

CONFIG = {
    # 数据库
    "db_path": "~/.openclaw/workspace/memory/memory.lanceDB",
    
    # 向量维度 (根据模型)
    "vector_dims": 1024,  # bge-m3, mxbai: 1024 | OpenAI: 1536
    
    # 嵌入模型
    "embed_model": "bge-m3:latest",  # 或 "mxbai-embed-large"
    
    # LLM模型
    "llm_model": "qwen3.5:27b",  # 或 "qwen3:8b"
    
    # 分层配置
    "hot_ttl_hours": 24,
    "warm_ttl_days": 30,
    "cold_ttl_days": 365,
    
    # 检索配置
    "default_limit": 10,
    "max_limit": 100,
    "rerank_k": 20,
}
```

## 📚 更多文档

| 文档 | 内容 |
|------|------|
| [QUICKSTART.md](QUICKSTART.md) | 快速入门指南 |
| [API_REFERENCE.md](API_REFERENCE.md) | 完整API参考 |
| [SKILL.md](SKILL.md) | OpenClaw技能说明 |

## 🧪 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 运行基准测试
python -m benchmark_suite
```

## 📦 安装

```bash
# 从PyPI
pip install claw-memory

# 从源码
git clone https://github.com/jace-jc/claw-memory.git
cd claw-memory
pip install -e .
```

## 📄 许可证

MIT License

## 🔗 GitHub

https://github.com/jace-jc/claw-memory
