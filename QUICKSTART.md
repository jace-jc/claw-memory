# Claw Memory 快速入门

> 5分钟上手 AI 记忆系统

## 安装

```bash
pip install claw-memory
```

## 基本使用

### 1. 初始化

```python
from claw_memory import get_db

db = get_db()
```

### 2. 存储记忆

```python
# 存储简单事实
db.store({
    "content": "用户的名字叫张三",
    "type": "fact",
    "importance": 0.9
})

# 存储偏好
db.store({
    "content": "用户喜欢川菜和火锅",
    "type": "preference",
    "importance": 0.8
})

# 存储决策
db.store({
    "content": "用户决定使用React框架",
    "type": "decision",
    "importance": 0.7
})
```

### 3. 搜索记忆

```python
# RRF智能搜索（推荐）
results = db.search_rrf("用户叫什么名字", limit=5)

# 基本搜索
results = db.search("张三")
```

### 4. 查看统计

```python
stats = db.stats()
print(f"总记忆数: {stats['total_memories']}")
```

## 意图搜索示例

系统能自动理解不同类型的查询：

```python
# 否定查询
results = db.search_rrf("用户不喜欢什么食物")

# 时序查询
results = db.search_rrf("用户最近在做什么项目")

# 多跳推理
results = db.search_rrf("用户朋友喜欢什么")

# 模糊查询
results = db.search_rrf("用户的hangzhou联系方式")
```

## 遗忘机制

记忆会自动基于时间和重要性衰减：

```python
# 查看遗忘曲线
from claw_memory import memory_forgetting
curves = memory_forgetting("decay_curve")
```

## 自动备份

```python
from claw_memory import start_auto_backup

# 每天自动备份
scheduler = start_auto_backup(interval_hours=24)
```

## 用户画像

```python
from claw_memory import build_user_profile

# 获取用户所有记忆
memories = db.get_all()
profile = build_user_profile(memories)

print(f"用户兴趣: {profile.interests}")
print(f"技能: {profile.skills}")
```

## 常见问题

### Q: 搜索结果不准确？
A: 尝试提高 importance 值（0.7-1.0），重要记忆会被优先召回

### Q: 如何加速搜索？
A: 系统已使用并行通道搜索，延迟约1秒。如需更快可减少 limit

### Q: 记忆安全吗？
A: 支持 E2E 加密，密钥仅本地存储

## 完整API

见 [API_REFERENCE.md](API_REFERENCE.md)
