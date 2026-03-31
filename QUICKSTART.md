# Claw Memory 快速入门

## 🚀 5分钟快速开始

### Step 1: 安装模型

```bash
# 安装嵌入模型
ollama pull bge-m3

# 安装LLM模型
ollama pull qwen3.5:27b
```

### Step 2: 存储记忆

```python
from claw_memory import memory_store

# 存储事实
memory_store(
    content="用户的名字叫张三，是一名软件工程师",
    type="fact",
    importance=0.9
)

# 存储偏好
memory_store(
    content="用户喜欢川菜，讨厌加班",
    type="preference",
    importance=0.8
)

# 存储决策
memory_store(
    content="用户决定使用React开发前端",
    type="decision",
    importance=0.9
)
```

### Step 3: 搜索记忆

```python
from claw_memory import memory_search_rrf

# RRF融合搜索
results = memory_search_rrf(
    query="用户的工作是什么",
    limit=5
)

for r in results:
    print(f"{r['content']} (score: {r['score']:.3f})")
```

### Step 4: 查看统计

```python
from claw_memory import memory_stats

stats = memory_stats()
print(f"总记忆数: {stats['total_memories']}")
print(f"记忆类型分布: {stats['by_type']}")
```

## 📝 常用命令

### 存储记忆

```
memory_store content="内容" type="fact|preference|decision|lesson" importance=0.5-1.0
```

### 搜索记忆

```
memory_search query="查询内容" limit=10
memory_search_rrf query="查询内容" k=60
```

### 知识图谱

```
memory_kg action="search|network|stats" entity="实体名" depth=2
```

### 层级管理

```
memory_tier action="stats|auto_tier"
```

### 时序提取

```
memory_temporal_extract text="用户上周感冒了"
```

## 🏠 多部署方案选择

### 方案D: 完全本地（推荐）

适合：隐私优先、追求完全控制

```bash
ollama pull bge-m3
ollama pull qwen3.5:27b
```

内存需求：~22GB

### 方案C: 简单用（OpenAI）

适合：仅有OpenAI API

```bash
export OPENAI_API_KEY="sk-xxx"
```

### 方案B: 预算有限

适合：需要重排但想省钱

```bash
export JINA_API_KEY="xxx"
export SILICONFLOW_API_KEY="xxx"
export OPENAI_API_KEY="xxx"
```

### 方案A: 全功能

适合：追求最高质量

```bash
export JINA_API_KEY="xxx"
export OPENAI_API_KEY="xxx"
```

## 🔧 常见问题

### Q: 向量模型用什么？

**推荐**: `bge-m3` - 通用嵌入模型，精度高

**可选**: `mxbai-embed-large` - 更轻量，速度快

### Q: LLM模型用什么？

**推荐**: `qwen3.5:27b` - 中文理解强，精度高

**可选**: `qwen3:8b` - 更轻量，速度快

### Q: Cross-Encoder是必须的吗？

**否**。Cross-Encoder用于提升搜索精度，但不是必须的。系统在没有Cross-Encoder时也能正常工作。

### Q: 如何选择部署方案？

| 场景 | 推荐方案 |
|------|---------|
| 隐私优先 | D (完全本地) |
| 仅有OpenAI | C (简单用) |
| 预算有限 | B (免费重排) |
| 追求质量 | A (全功能) |

## 📊 性能参考

| 操作 | 方案D本地 | 方案C云端 |
|------|----------|----------|
| 存储 | ~50ms/条 | ~100ms/条 |
| 搜索 | ~100ms | ~200ms |
| 嵌入生成 | ~200ms | ~50ms |

## 🧪 验证安装

```bash
# 运行测试
pytest

# 查看统计
python -c "from claw_memory import memory_stats; print(memory_stats())"
```

## 下一步

- 阅读 [API_REFERENCE.md](API_REFERENCE.md) 了解更多API
- 阅读 [SKILL.md](SKILL.md) 了解完整功能
- 阅读 [README.md](README.md) 了解架构设计
