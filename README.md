# Claw Memory

> **本地优先的AI记忆系统** — 让AI真正"记住"你
> 
> 🎯 质量优先 | 🏠 完全本地 | ⚡ 语义检索

## ✨ 核心特性

| 特性 | 描述 | 效果 |
|:----:|------|:----:|
| **8规则去噪** | 自动过滤系统提示/心跳/噪音 | 垃圾记忆-77% |
| **自适应检索** | 智能判断何时触发记忆 | 节省60%计算 |
| **Weibull衰减** | 重要记忆久留，噪声自然消散 | 自动整理 |
| **5通道RRF** | Vector+BM25+KG+Temporal+Importance | 召回率↑40% |
| **两阶段去重** | 向量预过滤+LLM语义决策 | 重复记忆-90% |
| **Recall Guard** | 防止幻觉循环放大 | 假记忆↓95% |

## 🚀 快速开始

### 最低配置（8GB内存即可）

```bash
# 1. 安装Ollama
# 2. 下载轻量模型
ollama pull bge-m3          # 嵌入：1.2GB
ollama pull qwen3:8b        # LLM：5GB（推荐，非27B）

# 3. 使用
from claw_memory import get_db
db = get_db()
db.store({"content": "用户喜欢川菜", "type": "preference"})
results = db.search("用户喜欢吃什么")
```

### 云端API（更高质量）

支持任意OpenAI兼容API：
- Kimi Coding / 火山方舟 / 硅基流动 / Jina AI
- 自动检测，无需修改代码

## 📊 基准测试

| 测试项 | 结果 |
|--------|------|
| 去噪过滤 | 6/6 ✅ |
| 自适应检索 | 9/9 ✅ |
| 记忆召回@5 | 50% |
| 质量测试 | 22/22 ✅ |

## 🏠 为什么选Claw Memory？

| 对比 | Claw Memory | 其他方案 |
|------|-------------|----------|
| 隐私 | ✅ 完全本地 | ❌ 云端存储 |
| 去噪 | ✅ 8规则过滤 | ❌ 无过滤 |
| 幻觉防护 | ✅ Recall Guard | ❌ 易循环放大 |
| 资源占用 | ✅ 7GB最低 | ❌ 20GB+ |
| 中文优化 | ✅ bge-m3 | ⚠️ 一般 |

## 🏗️ 部署方案

### 云端API（推荐OpenAI兼容协议）

| 提供商 | Embedding | 协议 | 特点 |
|--------|-----------|------|------|
| **Kimi Coding** | bge-m3 | OpenAI兼容 | 中文优化，1024维 |
| **火山方舟** | 豆包系列 | OpenAI兼容 | 国内稳定，多种模型 |
| **硅基流动** | BAAI/bge | OpenAI兼容 | 免费额度，性价比高 |
| **Jina AI** | jina-embeddings | OpenAI兼容 | 专业嵌入，质量高 |

### 本地模型（轻量优先）

| 模型 | 大小 | 内存 | 用途 | 推荐度 |
|------|:----:|:----:|------|:------:|
| **bge-m3** | 1.2GB | ~2GB | 嵌入（默认） | ⭐⭐⭐⭐⭐ |
| **mxbai-embed-large** | 670MB | ~1.5GB | 嵌入（更快） | ⭐⭐⭐⭐ |
| **MiniLM-L6-v2** | 90MB | ~500MB | Cross-Encoder | ⭐⭐⭐⭐⭐ |
| **qwen3:8b** | 5GB | ~8GB | LLM（推荐） | ⭐⭐⭐⭐ |
| qwen3.5:27b | 17GB | ~20GB | LLM（高配可选） | ⭐⭐ |

## 📦 安装

```bash
pip install claw-memory
```

## 🔗 链接

- [GitHub](https://github.com/jace-jc/claw-memory)
- [CHANGELOG](CHANGELOG.md)
- [技能文档](SKILL.md)
