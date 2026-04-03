"""
记忆抽取模块 - 规则过滤 + qwen3.5 深度抽取
"""
import re
import json
import time
import hashlib
import requests
from datetime import datetime
from core.memory_config import CONFIG

# Ollama 健康检查缓存
_ollama_last_check = None
_ollama_is_online = True

# 【P0修复】模块级去重集合（跨调用持久化）
_quick_seen_fingerprints: set = set()

def _fingerprint(text: str) -> str:
    """内容指纹：规范化后取hash，用于精确去重"""
    # 去除标点、空白，转小写
    normalized = re.sub(r'[\s，。、！？；：""''（）\[\]【】]', '', text.lower())
    return hashlib.md5(normalized.encode()).hexdigest()[:16]

# ==================== 噪音过滤规则 ====================

NOISE_PATTERNS = [
    # 问候语
    r"^(你好|您好|嗨|hi|hello|hey)[\s,.!?]*$",
    r"^(早上好|下午好|晚上好|早安|晚安)[\s,.!?]*$",
    
    # 简单确认
    r"^(好的|是的|嗯|OK|ok|好|行|可以|没问题)[\s,.!?]*$",
    r"^(收到|了解|明白|知道了)[\s,.!?]*$",
    
    # 纯emoji
    r"^[\s]*[😀-🙏🌀-🗿]+[\s]*$",
    r"^[👍👏🙏❤️❤😊😄🙂]+[\s]*$",
    
    # 纯标点
    r"^[，。、！？；：""''（）【】《》\s]+$",
    
    # 简单致谢
    r"^(谢谢|感谢|多谢|thx|thanks)[\s,.!?]*$",
]

def is_noise(text: str) -> bool:
    """判断文本是否为噪音"""
    if not text or len(text.strip()) < 2:
        return True
    
    text = text.strip()
    
    # 检查噪音模式
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    # 检查是否全为标点和空格
    if re.match(r'^[\s\W]+$', text):
        return True
    
    return False

# ==================== 快速抽取规则 ====================

FAST_EXTRACT_RULES = [
    # 偏好类
    (r"(?:我|用户).*(?:喜欢|prefer|倾向|倾向于)(.+)", "preference"),
    (r"(?:我|用户).*(?:讨厌|不喜欢|hate|dislike)(.+)", "preference"),
    (r"(?:我|用户).*(?:用|使用|using|use)(.+?)(?:而不是|instead of|不)(.+)", "preference"),
    (r"(?:我|用户).*(?:偏好|preference).*(:|是)(.+)", "preference"),
    
    # 决策类
    (r"(?:决定|decided|决策).*(?:用|使用|用)(.+)", "decision"),
    (r"(?:我们|我).*(?:决定|decided|选择|chose)(.+)", "decision"),
    (r"(?:用|使用)(.+?)(?:吧|吧|好了|的)", "decision"),
    
    # 事实类
    (r"(?:我|用户).*(?:住在|位于|在)(.+?)(?:市|省|县|区)", "fact"),
    (r"(?:我|用户).*(?:是|是一名|做)(.+?)(?:工程|开发|设计|产品|运营|市场)", "fact"),
    (r"(?:我|用户).*(?:工作|任职|就职)(?:于|在)(.+)", "fact"),
    
    # 截止日期类
    (r"截止.*?(?:是|到|在|为)(.+?[日周月年])", "task_state"),
    (r"deadline.*?(is|:|到|是)(.+)", "task_state"),
]

def quick_extract(text: str) -> list[dict]:
    """
    快速抽取 - 基于规则的高置信度抽取
    【P0修复】使用模块级fingerprint去重
    """
    if is_noise(text):
        return []
    
    results = []
    
    for pattern, mem_type in FAST_EXTRACT_RULES:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            content = match.group(0).strip()
            
            # 【P0修复】用fingerprint精确去重（跨调用持久化）
            fp = _fingerprint(content)
            if fp in _quick_seen_fingerprints:
                continue
            _quick_seen_fingerprints.add(fp)
            
            # 计算重要性
            importance = 0.5
            if "prefer" in content.lower() or "喜欢" in content:
                importance = 0.8
            if "decided" in content.lower() or "决定" in content:
                importance = 0.9
            if "deadline" in content.lower() or "截止" in content:
                importance = 0.95
            
            results.append({
                "content": content,
                "type": mem_type,
                "importance": importance,
                "source": "quick_extract",
                "tags": [],
            })
    
    return results

# ==================== 深度抽取 (qwen3.5) ====================

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

对话内容：
{transcript}
"""

def deep_extract(transcript: str) -> list[dict]:
    """
    深度抽取 - 使用 qwen3.5 分析整段对话
    【修复P4】Ollama 离线检查缓存（60秒内不重复检查）
    """
    global _ollama_last_check, _ollama_is_online
    
    if not transcript or len(transcript.strip()) < 10:
        return []
    
    # 检查是否全是噪音
    lines = transcript.split("\n")
    meaningful_lines = [l for l in lines if not is_noise(l)]
    if len(meaningful_lines) < 1:
        return []
    
    # 【修复P4-2】Ollama 离线检查（60秒缓存）
    import time
    now = time.time()
    if _ollama_last_check is None or (now - _ollama_last_check) > 60:
        try:
            test_response = requests.get(
                f"{CONFIG['ollama_url']}/api/tags",
                timeout=3
            )
            _ollama_is_online = (test_response.status_code == 200)
            _ollama_last_check = now
        except Exception:
            _ollama_is_online = False
            _ollama_last_check = now
    
    if not _ollama_is_online:
        print("[DeepExtract] Ollama offline (cached)")
        return []
    
    try:
        # 调用 qwen3.5
        response = requests.post(
            f"{CONFIG['ollama_url']}/api/generate",
            json={
                "model": CONFIG["llm_model"],
                "prompt": DEEP_EXTRACT_PROMPT.format(transcript=transcript),
                "stream": False,
                "format": "json",
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "")
            
            # 解析 JSON
            try:
                memories = json.loads(text)
                if isinstance(memories, dict) and "memories" in memories:
                    memories = memories["memories"]
                if not isinstance(memories, list):
                    return [
                        {
                            "type": m.get("type", "fact"),
                            "content": m.get("content", ""),
                            "importance": float(m.get("importance", 0.5)),
                            "tags": m.get("tags", []),
                            "source": "deep_extract",
                        }
                        for m in memories
                        if m.get("content")
                    ]
            except json.JSONDecodeError:
                # 尝试提取JSON部分
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except:
                        pass
    except Exception as e:
        print(f"[DeepExtract] error: {e}")
    
    return []

# ==================== 会话级抽取 ====================

def extract_from_messages(messages: list[dict]) -> list[dict]:
    """
    从消息列表中抽取记忆
    messages: [{"role": "user"/"assistant", "content": "...", "id": "..."}]
    【边界修复】添加输入校验和长度限制
    """
    all_memories = []
    
    # 1. 先做快速规则抽取
    for msg in messages:
        # 【边界修复】确保 content 是字符串
        content = str(msg.get("content", ""))
        if not content or len(content) < 3:
            continue
        
        quick_results = quick_extract(content)
        for r in quick_results:
            r["source_id"] = str(msg.get("id", ""))
            r["transcript"] = content[:200]  # 保留原始片段
            all_memories.append(r)
    
    # 2. 组成完整对话用于深度抽取
    if len(messages) > 2:
        # 【边界修复】限制每条消息长度和总数
        transcript_parts = []
        for m in messages[-6:]:
            msg_content = str(m.get("content", ""))[:100]
            role = '用户' if m.get('role') == 'user' else 'AI'
            transcript_parts.append(f"{role}: {msg_content}")
        
        # 【边界修复】transcript 总长度限制 1000 字符
        transcript = "\n".join(transcript_parts)[:1000]
        
        deep_results = deep_extract(transcript)
        for r in deep_results:
            r["source_id"] = "session"
            r["transcript"] = transcript[:200]
            all_memories.append(r)
    
    # 3. 【P0修复】去重（基于内容指纹）
    seen = set()
    unique_memories = []
    for m in all_memories:
        fp = _fingerprint(m["content"])
        if fp not in seen:
            seen.add(fp)
            unique_memories.append(m)
    
    return unique_memories
