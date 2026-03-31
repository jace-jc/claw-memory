# CLAW MEMORY - 小爪记忆系统

> 本地优先的 AI 记忆系统 · 零 API 成本 · 混合触发 · 自动生命周期管理

## 核心理念

1. **本地优先** — 全部使用 Ollama (bge-m3 + qwen3.5)，零 API 成本
2. **宁缺毋滥** — 质量 > 数量，激进修剪
3. **真实第一** — Transcript-first，防止记忆幻觉
4. **自动运转** — 不需要人工维护
5. **可追溯** — 所有记忆有来源，能回查原始对话

## 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                     捕获层 (CAPTURE)                          │
│  用户消息 → 规则过滤 → 实时抽取 → 深度抽取(会话结束)           │
│    ↓                                                         │
│  type: fact | preference | decision | lesson | entity         │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                     存储层 (STORAGE)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │  HOT RAM │→│ WARM     │→│  COLD    │                 │
│  │ SESSION- │  │ LanceDB  │  │ Markdown │                 │
│  │ STATE.md │  │ Vectors  │  │ Archive  │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                     检索层 (RETRIEVAL)                        │
│  混合检索(Vector+BM25) → 重排 → 过滤 → 返回                  │
└──────────────────────────────────────────────────────────────┘
```

## 触发规则

### 何时存储

| 信号 | 示例 | 行为 |
|------|------|------|
| 用户给出事实 | "我住在上海" | 立即存 fact |
| 用户给出偏好 | "我喜欢用 Tailwind" | 立即存 preference |
| 用户做出决策 | "我们决定用 React" | 立即存 decision |
| 用户纠正 AI | "不是这样的，应该是..." | 立即存 + 更新 |
| 用户设置截止 | "截止日期是周五" | 立即存 task_state |
| 任务完成 | 项目/子任务完成 | 会话结束时深度抽取 |

### 何时跳过存储

- 问候语（"你好"、"嗨"）
- 简单确认（"好的"、"是的"）
- 纯 emoji 消息
- 闲聊（无信息量）

### 何时召回

- Session start（自动）
- 用户提问且需要上下文（自动）
- 处理新任务时（自动）

## 工具接口

### memory_store

存储新记忆（自动触发）

```python
memory_store(
    content="用户偏好 Tailwind 而不是 vanilla CSS",
    type="preference",
    importance=0.9,
    tags=["frontend", "css"],
    scope="user"  # 范围: global|user|project|agent|session|channel
)
```

### memory_search

语义搜索记忆（支持Cross-Encoder重排和多范围隔离）

```python
memory_search(
    query="用户对前端框架的偏好",
    limit=5,
    types=["preference", "decision"],
    min_score=0.3,           # 最低重要性分数
    scope="user",             # 范围过滤: global|user|project|agent|session|channel
    use_rerank=True          # 是否使用Cross-Encoder重排
)
```

### memory_recall

召回相关记忆（自动注入上下文）

```python
memory_recall(
    query="项目状态",
    auto_inject=True,  # 自动注入到上下文
    similarity_threshold=0.6  # 最低相似度阈值
)
```

### memory_forget

删除记忆

```python
memory_forget(
    query="错误的记忆内容"  # 或 memory_id="xxx"
)
```

### memory_tier

查看或管理层级

```python
memory_tier(action="view", tier="ALL")  # view|stats|auto_tier
```

### memory_stats

统计数据

```python
memory_stats()  # 返回数量、大小、最近活动等
```

## 数据结构

```typescript
interface Memory {
  id: string;              // UUID
  type: 'fact' | 'preference' | 'decision' | 'lesson' | 'entity' | 'task_state';
  content: string;        // 原始内容
  summary?: string;       // 摘要（COLD降级时生成）
  importance: number;     // 0.0-1.0
  source: string;         // 原始消息ID
  transcript?: string;    // 原始对话片段
  
  tags: string[];
  scope: 'global' | 'user' | 'project' | 'agent' | 'session' | 'channel';  // 【增强】多范围隔离
  scope_id?: string;
  
  created_at: string;     // ISO 8601
  updated_at: string;
  last_accessed?: string;
  access_count: number;
  
  // 演进链
  revision_chain?: string[];
  superseded_by?: string;
}
```

## 新增功能 (v1.5)

### P3性能优化 - 缓存层

**搜索结果缓存** - LRU + TTL：
```python
memory_cache(action='stats')  # 查看缓存状态
memory_cache(action='clear')  # 清空缓存
```

**带缓存的搜索**：
```python
db.search_cached(query, limit=5)      # 带缓存的向量搜索
db.search_rrf_cached(query, limit=5) # 带缓存的RRF搜索
```

### P2时序追踪 - 记忆版本管理

**时间范围追踪**：
- `valid_from`: 记忆创建时间
- `valid_until`: 记忆失效时间
- `superseded_by`: 被哪个记忆替代

**API**：
```python
memory_temporal(action='history', memory_id='xxx')  # 获取版本历史
memory_temporal(action='as_of')                     # 查询当前有效记忆
memory_temporal(action='changes', days=7)         # 最近变更
memory_temporal(action='timeline')                 # 偏好时间线
memory_temporal(action='prune')                     # 清理过期历史
```

### P1实体消歧

**LLM驱动的实体消歧** - 判断实体是否已存在并自动合并：

| 功能 | 说明 |
|-----|------|
| 精确匹配 | 完全相同的实体名 |
| 子串匹配 | "清华大学"和"清华" |
| LLM判断 | 语义相似性判断 |

```python
memory_disambiguate(
    entity_name="Shopify",
    entity_type="company",
    context="用户在这家公司工作"
)
```

**返回结果**：
- `merged`: 合并到已存在实体
- `existing`: 已存在（精确匹配）
- `new`: 新建实体

### RRF融合搜索 (P0优化)

**LLM驱动的实体消歧** - 判断实体是否已存在并自动合并：

| 功能 | 说明 |
|-----|------|
| 精确匹配 | 完全相同的实体名 |
| 子串匹配 | "清华大学"和"清华" |
| LLM判断 | 语义相似性判断 |

```python
memory_disambiguate(
    entity_name="Shopify",
    entity_type="company",
    context="用户在这家公司工作"
)
```

**返回结果**：
- `merged`: 合并到已存在实体
- `existing`: 已存在（精确匹配）
- `new`: 新建实体

### RRF融合搜索 (P0优化)

**4通道RRF融合** - Reciprocal Rank Fusion，综合多个搜索通道的结果：

| 通道 | 说明 | 权重 |
|-----|------|------|
| Vector | 语义向量相似度 | 0.3 |
| BM25 | 关键词匹配 | 0.25 |
| Importance | 重要性分数 | 0.25 |
| KG | 知识图谱关联 | 0.2 |

**使用方式**：
```python
memory_search_rrf(
    query="用户偏好",
    limit=5,
    k=60  # RRF参数，越小越激进
)
```

### Cross-Encoder 重排

使用 qwen3.5 对向量搜索结果进行二次精排，提升相关性：

```python
memory_search(
    query="用户偏好",
    use_rerank=True  # 启用Cross-Encoder重排
)
```

**原理**：
- 向量搜索：快速召回候选集
- Cross-Encoder：对每个候选计算 query-content 相关性分数
- 综合评分 = 向量相似度×0.3 + Cross-Encoder×0.7

### 多范围隔离

支持细粒度的数据隔离：

| Scope | 说明 |
|-------|------|
| global | 全局共享记忆 |
| user | 用户级记忆 |
| project | 项目级记忆 |
| agent | Agent专属记忆 |
| session | 当前会话记忆 |
| channel | 频道/群组记忆 |

```python
# 存储到指定范围
memory_store(content="项目配置", scope="project")

# 只搜索指定范围
memory_search(query="配置", scope="project")

# 只召回指定范围
memory_recall(query="配置", scope="agent")
```

## 生命周期

```
会话进行中 ─────────────────────────────────────────────────
                    ↓
              实时抽取（高置信度）
                    ↓
会话结束 ─────────────────────────────────────────────────
                    ↓
              深度抽取（qwen3.5）
                    ↓
    ┌─────────────┼─────────────┐
    ↓             ↓             ↓
  HOT→WARM     WARM→COLD    清理
  (24h后)      (30天后)     (<0.3删除)
```

## 文件结构

```
claw-memory/
├── SKILL.md              # 本文档
├── skill.yaml            # 元数据
├── README.md             # 快速开始
├── memory_main.py        # 入口 + CLI
├── memory_config.py      # 配置
├── memory_extract.py     # 抽取（规则 + LLM）
├── memory_session.py     # HOT层 (SESSION-STATE.md)
├── memory_tier.py       # 层级管理 + TTL晋升
├── lancedb_store.py      # WARM层 (LanceDB)
└── ollama_embed.py       # Ollama嵌入
```

## 安装依赖

```bash
pip install lancedb pyarrow requests numpy
```

## 配置项

在 `~/.openclaw/openclaw.json` 中：

```json
{
  "plugins": {
    "entries": {
      "claw-memory": {
        "enabled": true,
        "config": {
          "hot_ttl_hours": 24,
          "warm_ttl_days": 30,
          "min_importance": 0.3,
          "auto_recall": true,
          "auto_capture": true,
          "ollama_url": "http://localhost:11434",
          "embed_model": "bge-m3:latest",
          "llm_model": "qwen3.5:27b"
        }
      }
    }
  }
}
```

## CLI 用法

```bash
# 存储记忆
python memory_main.py store "用户喜欢用 Tailwind CSS"

# 搜索记忆
python memory_main.py search "用户的 CSS 偏好"

# 召回记忆
python memory_main.py recall "前端框架"

# 查看层级
python memory_main.py tier ALL

# 统计
python memory_main.py stats

# 自动整理（建议定时执行）
python memory_main.py auto_tier
```

## 依赖

- Ollama (bge-m3, qwen3.5)
- LanceDB (pip install lancedb)
- PyArrow (pip install pyarrow)
- 本地存储 (Markdown文件)

## 快速开始

1. 确保 Ollama 运行中：`ollama serve`
2. 拉取模型：`ollama pull bge-m3:latest && ollama pull qwen3.5:27b`
3. 安装依赖：`pip install lancedb pyarrow requests numpy`
4. 重启 OpenClaw

## 定时任务配置

### 自动整理（建议每天执行）

**方式1: 使用 cron**
```bash
# 每天凌晨2点自动整理
crontab -e
# 添加行：
0 2 * * * /Users/claw/.openclaw/skills/claw-memory/scripts/auto_tier.sh >> /tmp/claw-memory-cron.log 2>&1
```

**方式2: OpenClaw cron（推荐）**
在 `openclaw.json` 中配置 cron 任务：
```json
{
  "crons": {
    "memory-auto-tier": {
      "command": "python /Users/claw/.openclaw/skills/claw-memory/memory_main.py auto_tier",
      "schedule": "0 2 * * *"
    }
  }
}
```

### 定时任务会执行：
1. HOT → WARM 晋升（检查24h超时）
2. WARM → COLD 归档（检查30天超时）
3. 低重要性记忆自动清理

## 版本历史

- v1.0.0 (2026-03-31): 初始版本
- v1.0.1 (2026-03-31): 修复 LanceDB schema 和 _update_access bug
- v1.0.2 (2026-03-31): 修复 quick_extract 重复匹配，添加 cron 集成
- v1.1.0 (2026-03-31): 新增 Cross-Encoder 重排、多范围隔离
- v1.2.0 (2026-03-31): 新增知识图谱、自动实体关系关联、健康度仪表盘
- v1.3.0 (2026-03-31): **P0** RRF融合搜索（4通道：Vector+BM25+Importance+KG）
- v1.4.0 (2026-03-31): **P1** 实体消歧（LLM判断+自动合并）
- v1.5.0 (2026-03-31): **P2** 时序追踪 + **P3** 性能优化（缓存层）
- v1.6.0 (2026-03-31): 专业评审优化（Cross-Encoder替换、Benchmark、NetworkX图谱）
- v1.7.0 (2026-03-31): 技术完善（Weibull遗忘、健康仪表盘）
- **v1.8.0 (2026-03-31): P0问题修复**
  - ✅ 修复全表内存加载（改用head()采样）
  - ✅ 统一API响应格式（api_response辅助函数）
  - ✅ 修复中文BM25分词
  - ✅ Benchmark系统建立完成

- **v1.9.0 (2026-03-31): P1问题修复**
  - ✅ 创建requirements.txt依赖清单
  - ✅ 创建memory_backup.py备份导出模块
  - ✅ 添加_logger日志系统
  - ✅ 替换print为标准日志

- **v2.0.0 (2026-03-31): P2/P3功能完成**
  - ✅ P2时序追踪完整API（history/as_of/timeline/changes/prune）
  - ✅ P3搜索缓存（LRU+TTL+预取机制）
  - ✅ 统一api_response响应格式
  - ✅ 常见查询预取（16个预设查询）

- **v2.1.0 (2026-03-31): 自适应RRF权重**
  - ✅ AdaptiveRRF权重管理器
  - ✅ 基于用户点击反馈自动调整通道权重
  - ✅ memory_adaptive API（weights/click/stats/reset）
  - ✅ 加权RRF融合公式

- **v2.2.0 (2026-03-31): 隐私合规**
  - ✅ AES加密敏感数据（transcript、content）
  - ✅ GDPR数据导出（export）
  - ✅ GDPR数据删除（delete/delete_all）
  - ✅ 数据匿名化（anonymize）
  - ✅ 隐私审计日志

- **v2.3.0 (2026-03-31): 高级功能**
  - ✅ 多向量提供者（Ollama/OpenAI/本地备用）
  - ✅ 主备自动切换机制
  - ✅ SimpleHash最后备用（始终可用）
  - ✅ 传递推理（path路径查找）
  - ✅ 共同邻居查询（common）
  - ✅ 关系推理（infer）
  - ✅ 多租户隔离（scope强制隔离）

- **v2.5.0 (2026-03-31): Phase1优化**
  - ✅ KG通道修复（集成find_path/infer_relations）
  - ✅ Benchmark评测套件（12项测试）
  - ✅ LOCOMO基准对标（MRR=0.542 vs 目标0.669）

- **v2.6.0 (2026-03-31): Phase2 E2E加密**
  - ✅ 端到端加密架构（零知识加密）
  - ✅ AES-GCM级别加密
  - ✅ 新记录自动加密存储
  - ✅ 读取时自动解密

- **v2.8.0 (2026-03-31): MRR突破0.792 ✅**
  - ✅ Temporal通道5通道RRF融合
  - ✅ 并行通道搜索（ThreadPoolExecutor）
  - ✅ README扩展+Badges
  - ✅ CHANGELOG.md
  - ✅ MRR=0.792 > 目标0.669 🎯

## 作者

小爪 (Claw Memory System)
