"""
Claw Memory 提示词模板
"""

# 深度抽取提示词
DEEP_EXTRACT_PROMPT = """你是一个记忆抽取系统。从给定对话中提取值得保存的信息。

记忆类型：
- fact: 客观事实（工作、位置、身份等）
- preference: 偏好和倾向（喜欢/讨厌什么）
- decision: 决策和结论（决定用什么、做什么）
- lesson: 经验和教训（从错误中学到的）
- entity: 实体信息（人名、公司、产品等）
- task_state: 任务状态（进行中/已完成/截止日期）

输出格式（JSON数组）：
[
  {{
    "type": "preference",
    "content": "用户喜欢用Tailwind而不是vanilla CSS",
    "importance": 0.9,
    "tags": ["frontend", "css"]
  }}
]

规则：
1. 只提取有长期价值的信息
2. importance 0.0-1.0，越高越重要
3. 如果对话无有用信息，返回空数组 []
4. 内容要简洁，30字以内
5. 每个记忆只包含一个独立事实

对话内容：
{transcript}
"""

# 会话总结提示词
SESSION_SUMMARY_PROMPT = """你是一个会话总结系统。请总结以下对话的要点。

总结维度：
1. 用户的主要需求/问题
2. 做出的决定
3. 用户透露的偏好或事实
4. 待办事项
5. 需要记忆的重要上下文

输出格式（JSON）：
{{
  "summary": "一句话总结",
  "decisions": ["决定1", "决定2"],
  "preferences": ["偏好1"],
  "facts": ["事实1"],
  "todos": ["待办1"],
  "context": "需要记住的上下文"
}}

对话内容：
{transcript}
"""

# 记忆合并提示词
MEMORY_MERGE_PROMPT = """你是一个记忆管理系统。以下是关于同一主题的多条记忆，请合并为一条。

合并规则：
1. 保留最准确的信息
2. 如果矛盾，保留最新的
3. importance 取最大值
4. 合并 tags

输入记忆：
{memories}

输出格式（JSON）：
{{
  "type": "preference",
  "content": "合并后的内容",
  "importance": 0.9,
  "tags": ["tag1", "tag2"]
}}
"""
