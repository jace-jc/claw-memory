# Claw Memory - OpenClaw 记忆系统技能

> 本地优先的AI记忆系统，支持多通道RRF检索、知识图谱、时序追踪
> **版本：v2.8.0** - 聚焦记忆质量：去噪过滤+阈值强制化+矛盾检测+提取召回隔离

## 🎯 技能简介

Claw Memory 是一个为 OpenClaw AI Agent 设计的长期记忆系统，具有以下核心能力：

| 能力 | 描述 | 状态 |
|------|------|------|
| **意图分类** | 15种意图类型 | ✅ |
| **5通道RRF检索** | Vector+BM25+Importance+KG+Temporal | ✅ |
| **3跳推理** | 知识图谱多跳关系查询 | ✅ |
| **自动提取** | Mem0风格，本地运行 | ✅ |
| **4-Tier分层** | HOT/WARM/COLD/ARCHIVED | ✅ |
| **多部署方案** | 本地/云端/混合 | ✅ |
| **Cross-Encoder** | HuggingFace本地重排 | ✅ |
| **时序提取** | 30+种时间表达式 | ✅ |
| **Weibull衰减** | 智能遗忘模型，噪声自然消散 | ✅ v2.0 |
| **版本历史** | Git审计追踪，支持时点回溯 | ✅ v2.0 |
| **附件持久化** | 支持截图/代码/文档存储 | ✅ v2.0 |
| **并行通道搜索** | 5通道并行，延迟降低60% | ✅ v2.0 |
| **提取去噪** | 过滤心跳/系统提示词/噪音 | ✅ v2.9 NEW |
| **重要性阈值** | 强制化：<0.3不存主检索 | ✅ v2.9 NEW |
| **矛盾检测** | 改口时不删旧记忆，保留历史 | ✅ v2.9 NEW |
| **提取-召回隔离** | 双缓冲防幻觉循环 | ✅ v2.9 NEW |

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      CAPTURE (输入)                         │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 规则提取     │→│ 实时提取    │→│ 深度提取    │→│ 自动提取  │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└────────────────────────────┬──────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│                      STORE (存储)                            │
│                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │   HOT   │→│  WARM   │→│  COLD   │→│ARCHIVED│        │
│  │会话级    │  │向量级    │  │永久级    │  │归档级    │        │
│  │>0.9 imp │  │>0.7 imp │  │>0.5 imp │  │≤0.5 imp │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
└────────────────────────────┬──────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│                    RETRIEVE (检索)                           │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              RRF 5通道融合                            │   │
│  │  Vector(向量) + BM25(关键词) + Importance(重要性)   │   │
│  │  + KG(图谱) + Temporal(时序)                        │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────┬──────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│                    RERANK (重排)                            │
│                                                              │
│  Cross-Encoder (HuggingFace本地)                           │
│  ms-marco-MiniLM-L-6-v2 (~90MB)                          │
└─────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│              DECAY (衰减) 【NEW v2.0】                    │
│                                                              │
│  Weibull衰减模型：重要记忆久留，噪声自然消散               │
│  survival(t) = exp(-(t/λ)^k)                             │
│  尺度参数λ=30天，形状参数k=0.5                             │
└─────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│              ATTACHMENTS (附件) 【NEW v2.0】              │
│                                                              │
│  附件持久化：截图/代码/文档/语音/视频                       │
│  按memory_id归类，JSON元数据关联                           │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 本地模式（推荐）
ollama pull bge-m3
ollama pull qwen3.5:27b

# 可选：Cross-Encoder（提升精度）
# 自动下载，无需手动安装
```

### 2. 配置 OpenClaw

在 `openclaw.json` 中添加：

```json
{
  "plugins": {
    "entries": {
      "claw-memory": {
        "enabled": true,
        "config": {
          "embed_model": "bge-m3:latest",
          "llm_model": "qwen3.5:27b"
        }
      }
    }
  }
}
```

### 3. 使用技能

```
@bot memory_store 内容="用户的名字叫张三" 类型="fact" 重要性=0.9
@bot memory_search 查询="用户名字"
@bot memory_stats
```

## 📦 工具列表

### 存储工具

| 工具 | 描述 |
|------|------|
| `memory_store` | 存储新记忆 |
| `memory_recall` | 召回相关记忆 |

### 检索工具

| 工具 | 描述 |
|------|------|
| `memory_search` | 搜索记忆（支持重排） |
| `memory_search_rrf` | RRF融合搜索 |
| `memory_kg` | 知识图谱查询 |

### 管理工具

| 工具 | 描述 |
|------|------|
| `memory_forget` | 删除记忆 |
| `memory_stats` | 获取统计 |
| `memory_tier` | 层级管理 |
| `memory_temporal` | 时序追踪 |

### 提取工具

| 工具 | 描述 |
|------|------|
| `memory_extract_session` | 会话记忆提取 |
| `memory_auto_extract` | 自动事实提取 |
| `memory_temporal_extract` | 时序信息提取 |

## 📊 记忆类型

| 类型 | 描述 | 示例 |
|------|------|------|
| `fact` | 事实信息 | "用户的名字叫张三" |
| `preference` | 用户偏好 | "用户喜欢川菜" |
| `decision` | 决策记录 | "用户选择使用React" |
| `lesson` | 经验教训 | "用户从错误中学到..." |
| `entity` | 实体信息 | "用户的朋友小李" |
| `task_state` | 任务状态 | "用户的项目完成80%" |

## 🎯 意图分类

系统支持15种意图类型：

| 意图 | 示例查询 |
|------|---------|
| `fact` | "用户的工作是什么" |
| `preference` | "用户喜欢什么" |
| `negation` | "用户不喜欢吃什么" |
| `temporal` | "用户最近在做什么" |
| `multihop` | "用户朋友的朋友是谁" |
| `habit` | "用户的习惯是什么" |
| `skill` | "用户擅长什么" |
| `goal` | "用户的目标是什么" |
| `health` | "用户的健康如何" |
| `work` | "用户的职业是什么" |

## 🏠 多部署方案

### 方案对比

| 方案 | Embedding | Reranker | LLM | 适用场景 |
|------|-----------|----------|-----|---------|
| **A** | Jina API | Jina | GPT-4o | 生产环境 |
| **B** | Jina API | SiliconFlow | GPT-4o | 预算有限 |
| **C** | OpenAI | ❌ | GPT-4o | 简单使用 |
| **D** | Ollama本地 | ❌ | Ollama本地 | 隐私优先 |

### 方案D本地模型

| 模型 | 大小 | 内存需求 | 说明 |
|------|------|---------|------|
| bge-m3 | 1.2GB | ~2GB | 默认嵌入模型 |
| mxbai-embed-large | 670MB | ~1.5GB | 可选，更快 |
| qwen3.5:27b | 17GB | ~20GB | 默认LLM |
| qwen3:8b | 5GB | ~8GB | 可选，更快 |

### 自动检测

系统按以下优先级检测：

```
环境变量 MEMORY_SCHEME=A/B/C/D → 强制指定方案
JINA + OPENAI → 方案A
JINA + SILICONFLOW + OPENAI → 方案B
OPENAI → 方案C
无外部API → 方案D（默认）
```

## 🔧 分层存储

| 层级 | 重要性 | 存储位置 | TTL |
|------|--------|---------|-----|
| HOT | > 0.9 | SESSION-STATE.md | 24h |
| WARM | > 0.7 | LanceDB | 30d |
| COLD | > 0.5 | MEMORY.md + Git | 365d |
| ARCHIVED | ≤ 0.5 | 归档目录 | 90d |

## 📁 文件结构 (v2.8.0 - Package Structure)

```
claw-memory/
├── __init__.py           # Main exports + backward compat
├── SKILL.md              # This file
├── skill.yaml            # Skill configuration
│
├── core/                 # Core storage and schema
│   ├── __init__.py
│   └── schema.py         # PyArrow schema definitions
│   └── store.py          # LanceDB store (in lancedb_store.py)
│
├── retrieval/            # Search and retrieval
│   ├── __init__.py
│   ├── search.py         # Semantic search wrapper
│   ├── rrf.py            # RRF fusion search
│   ├── rerank.py         # Cross-encoder reranking
│   ├── dedup.py          # Two-stage deduplication
│   ├── cache.py          # Search caching
│   └── intent.py         # Intent classification
│
├── memory/               # Memory domain operations
│   ├── __init__.py
│   ├── kg.py             # Knowledge graph operations
│   ├── tier.py           # Tier management
│   ├── version.py        # Version history
│   ├── temporal.py       # Temporal tracking
│   └── forgetting.py      # Weibull decay/forgetting
│
├── api/                  # Tool API functions
│   ├── __init__.py
│   ├── main.py           # (from memory_main.py)
│   └── health.py         # Health check (broken circular dep)
│
├── extract/              # Memory extraction
│   ├── __init__.py
│   ├── extractor.py       # Main extraction logic
│   ├── chinese.py         # Chinese entity extraction
│   └── auto.py            # Auto extraction
│
├── infra/                # Infrastructure
│   ├── __init__.py
│   ├── backup.py          # Backup/restore
│   ├── transaction.py      # WAL protocol
│   ├── attachment.py      # Attachment storage
│   └── performance.py     # Performance monitoring
│
├── benchmark/            # Benchmark suite
│   ├── __init__.py
│   ├── suite.py           # Main benchmark
│   ├── runner.py          # Benchmark runner
│   ├── cases.py           # Test cases
│   └── improvements.py    # Improvement tests
│
├── tests/                # Test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_store.py
│   ├── test_search.py
│   └── test_temporal.py
│
└── [legacy flat files]   # Original files preserved for compat
    ├── lancedb_store.py   # LanceDB store
    ├── memory_main.py     # Main API
    ├── memory_config.py   # Configuration
    └── ...                # Other modules
```

**Backward Compatibility**: All old imports still work. New package structure provides organized access.

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行基准测试
python -m benchmark_suite

# 专业评审
python professional_review.py
```

## 📚 相关文档

| 文档 | 内容 |
|------|------|
| [README.md](README.md) | 完整项目说明 |
| [QUICKSTART.md](QUICKSTART.md) | 快速入门 |
| [API_REFERENCE.md](API_REFERENCE.md) | API参考 |

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 许可证

MIT License
