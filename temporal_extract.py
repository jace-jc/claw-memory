"""
时序信息提取模块 - Temporal Information Extraction

从文本中提取时间信息，支持：
- 相对时间: "昨天"、"上周"、"上个月"、"去年"
- 绝对时间: "2024年1月"、"周一"、"3月5日"
- 特殊时间: "今天"、"明天"、"昨晚"、"下周"

输出结构:
    {
        "text": "原始匹配文本",
        "type": "relative|absolute|special",
        "category": "last_week|next_week|...|date|weekday|...",
        "temporal": {
            "relative": "last_week | next_week | ...",
            "absolute": "2024-01-15 | next_monday | ..."
        },
        "timestamp_range": {"start": ISO, "end": ISO},
        "event": "提取的事件（除时间词外的核心内容）"
    }
"""
import re
from datetime import datetime, timedelta
from typing import Optional


# ============================================================
# 核心提取器类
# ============================================================

class TemporalExtractor:
    """
    时序信息提取器
    
    支持中文时间表达式的完整提取，支持相对和绝对时间。
    """
    
    # 相对时间模式
    RELATIVE_PATTERNS = [
        # 昨天/前天/大前天
        (r'大前天', 'big_before_yesterday', lambda m: -3),
        (r'前天', 'before_yesterday', lambda m: -2),
        (r'昨天', 'yesterday', lambda m: -1),
        # 今天/今晚/今早
        (r'今早|今晨|今天|今日|今晚?', 'today', lambda m: 0),
        # 明天/后天/大后天
        (r'后天', 'day_after_tomorrow', lambda m: 2),
        (r'大后天', 'big_day_after_tomorrow', lambda m: 3),
        (r'明天|明日', 'tomorrow', lambda m: 1),
        # 上周/上上周
        (r'上上周|上周|上上星期', 'last_week', lambda m: -7),
        # 本周/这周
        (r'本周|这周|这个星期|本星期', 'this_week', lambda m: 0),
        # 下周/下下周
        (r'下下周|下周|下下星期', 'next_week', lambda m: 7),
        # 上个月/下个月
        (r'上上个月', 'last_month', lambda m: -2),
        (r'上个月|上月', 'last_month', lambda m: -1),
        (r'本月|这个月|本月', 'this_month', lambda m: 0),
        (r'下下个月', 'next_month', lambda m: 2),
        (r'下个月|下月', 'next_month', lambda m: 1),
        # 去年/明年
        (r'前年', 'year_before_last', lambda m: -2),
        (r'去年|上年', 'last_year', lambda m: -1),
        (r'今年|本年', 'this_year', lambda m: 0),
        (r'明年|来年', 'next_year', lambda m: 1),
        (r'后年', 'year_after_next', lambda m: 2),
        # 刚才/刚才/片刻前
        (r'刚才|方才|片刻前', 'just_now', lambda m: 0),
        # 早晚
        (r'今早|今晨|早上|上午', 'today_morning', lambda m: 0),
        (r'今晚|夜里|今晚', 'tonight', lambda m: 0),
        (r'中午', 'noon', lambda m: 0),
        (r'下午|午后', 'afternoon', lambda m: 0),
    ]
    
    # 绝对日期模式
    ABSOLUTE_DATE_PATTERNS = [
        # YYYY年MM月DD日
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日?', 'date_ymd', 3),
        (r'(\d{4})年(\d{1,2})月', 'date_ym', 2),
        (r'(\d{4})年', 'date_y', 1),
        # MM月DD日
        (r'(\d{1,2})月(\d{1,2})日?', 'date_md', 2),
        # 农历日期
        (r'正月初一', 'lunar_new_year', 0),
        (r'正月十五', 'lunar_15', 0),
        # 周末/工作日
        (r'周末|星期六|周六', 'saturday', 0),
        (r'星期日|周日|星期天', 'sunday', 0),
        (r'周一|星期一', 'monday', 0),
        (r'周二|星期二', 'tuesday', 0),
        (r'周三|星期三', 'wednesday', 0),
        (r'周四|星期四', 'thursday', 0),
        (r'周五|星期五', 'friday', 0),
    ]
    
    def __init__(self, reference_date: datetime = None):
        """
        Args:
            reference_date: 参考时间（默认为当前时间）
        """
        self.ref = reference_date or datetime.now()
    
    def extract(self, text: str) -> list[dict]:
        """
        从文本中提取所有时间信息
        
        Args:
            text: 输入文本
            
        Returns:
            时间信息列表，每个元素包含:
            {
                "text": "匹配文本",
                "type": "relative|absolute|special",
                "category": "时间类别",
                "temporal": {"relative": ..., "absolute": ...},
                "timestamp_range": {"start": ISO, "end": ISO},
                "event": "提取的事件"
            }
        """
        results = []
        
        # 提取相对时间
        for pattern, category, _ in self.RELATIVE_PATTERNS:
            for match in re.finditer(pattern, text):
                item = self._build_relative_result(match, category, text)
                if item:
                    results.append(item)
        
        # 提取绝对日期
        for pattern, category, _ in self.ABSOLUTE_DATE_PATTERNS:
            for match in re.finditer(pattern, text):
                item = self._build_absolute_result(match, category, text)
                if item:
                    results.append(item)
        
        # 按文本位置排序
        results.sort(key=lambda x: x["start_pos"])
        return results
    
    def extract_one(self, text: str) -> Optional[dict]:
        """提取第一个时间信息"""
        results = self.extract(text)
        return results[0] if results else None
    
    def _build_relative_result(self, match: re.Match, category: str, original_text: str) -> dict:
        """构建相对时间结果"""
        matched_text = match.group()
        start_pos = match.start()
        end_pos = match.end()
        
        now = self.ref
        day_offset = 0
        
        # 计算时间偏移
        for pattern, cat, offset_fn in self.RELATIVE_PATTERNS:
            if cat == category:
                day_offset = offset_fn(match)
                break
        
        # 计算绝对日期
        if category.endswith('_year'):
            year_offset = day_offset
            abs_date = now.replace(year=now.year + year_offset, month=1, day=1)
            range_start = abs_date
            range_end = abs_date.replace(month=12, day=31)
        elif category.endswith('_month'):
            month_offset = day_offset
            # 简单按30天计算月份偏移
            abs_date = now + timedelta(days=month_offset * 30)
            range_start = abs_date.replace(day=1)
            # 月末
            if abs_date.month == 12:
                range_end = abs_date.replace(month=12, day=31)
            else:
                range_end = abs_date.replace(month=abs_date.month + 1, day=1) - timedelta(days=1)
        elif 'week' in category or category in ('monday','tuesday','wednesday','thursday','friday','saturday','sunday'):
            range_start, range_end = self._get_week_range(category, day_offset)
        elif category in ('today', 'yesterday', 'tomorrow', 'before_yesterday', 'day_after_tomorrow',
                          'big_before_yesterday', 'big_day_after_tomorrow'):
            days = {'today': 0, 'yesterday': -1, 'tomorrow': 1,
                    'before_yesterday': -2, 'day_after_tomorrow': 2,
                    'big_before_yesterday': -3, 'big_day_after_tomorrow': 3}
            d = days.get(category, 0) + day_offset
            range_start = (now + timedelta(days=d)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            range_end = (now + timedelta(days=d)).replace(
                hour=23, minute=59, second=59, microsecond=999999)
        elif 'morning' in category or 'noon' in category or 'afternoon' in category or 'tonight' in category:
            base_date = (now + timedelta(days=day_offset)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            if 'morning' in category or '早' in matched_text or '晨' in matched_text:
                range_start = base_date.replace(hour=6)
                range_end = base_date.replace(hour=11)
            elif 'noon' in category or '中午' in matched_text:
                range_start = base_date.replace(hour=11)
                range_end = base_date.replace(hour=13)
            elif 'afternoon' in category or '下午' in matched_text:
                range_start = base_date.replace(hour=13)
                range_end = base_date.replace(hour=18)
            elif 'tonight' in category or '晚' in matched_text:
                range_start = base_date.replace(hour=18)
                range_end = base_date.replace(hour=23, minute=59, second=59)
            else:
                range_end = base_date.replace(hour=23, minute=59, second=59)
        else:
            base = now + timedelta(days=day_offset)
            range_start = base.replace(hour=0, minute=0, second=0, microsecond=0)
            range_end = base.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # 提取事件（去掉时间词后的内容）
        event = self._extract_event(original_text, start_pos, end_pos)
        
        return {
            "text": matched_text,
            "type": "relative",
            "category": category,
            "temporal": {
                "relative": category,
                "absolute": range_start.strftime("%Y-%m-%d")
            },
            "timestamp_range": {
                "start": range_start.isoformat(),
                "end": range_end.isoformat()
            },
            "event": event,
            "start_pos": start_pos,
            "end_pos": end_pos
        }
    
    def _build_absolute_result(self, match: re.Match, category: str, original_text: str) -> dict:
        """构建绝对时间结果"""
        matched_text = match.group()
        start_pos = match.start()
        end_pos = match.end()
        
        now = self.ref
        weekday_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        if category in weekday_map:
            # 周几 → 计算最近的该星期
            target_wd = weekday_map[category]
            days_ahead = (target_wd - now.weekday()) % 7
            if days_ahead == 0 and now.hour > 12:
                days_ahead = 7  # 已经过了今天的中午，算下周
            elif days_ahead == 0 and now.hour <= 12:
                days_ahead = 0  # 今天
            target_date = now + timedelta(days=days_ahead)
            range_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            range_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            absolute = category
        elif category == 'date_ymd':
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            try:
                target = now.replace(year=year, month=month, day=day)
                range_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
                range_end = target.replace(hour=23, minute=59, second=59, microsecond=999999)
                absolute = target.strftime("%Y-%m-%d")
            except ValueError:
                return None
        elif category == 'date_ym':
            year = int(match.group(1))
            month = int(match.group(2))
            try:
                target = now.replace(year=year, month=month, day=1)
                if month == 12:
                    range_end = target.replace(month=12, day=31)
                else:
                    range_end = target.replace(month=month + 1, day=1) - timedelta(days=1)
                range_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
                range_end = range_end.replace(hour=23, minute=59, second=59)
                absolute = target.strftime("%Y-%m")
            except ValueError:
                return None
        elif category == 'date_md':
            month = int(match.group(1))
            day = int(match.group(2))
            try:
                target = now.replace(month=month, day=day)
                range_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
                range_end = target.replace(hour=23, minute=59, second=59, microsecond=999999)
                absolute = target.strftime("%m-%d")
            except ValueError:
                return None
        elif category == 'date_y':
            year = int(match.group(1))
            range_start = now.replace(year=year, month=1, day=1, hour=0, minute=0, second=0)
            range_end = now.replace(year=year, month=12, day=31, hour=23, minute=59, second=59)
            absolute = str(year)
        else:
            range_start = now
            range_end = now
            absolute = matched_text
        
        event = self._extract_event(original_text, start_pos, end_pos)
        
        return {
            "text": matched_text,
            "type": "absolute",
            "category": category,
            "temporal": {
                "relative": None,
                "absolute": absolute
            },
            "timestamp_range": {
                "start": range_start.isoformat(),
                "end": range_end.isoformat()
            },
            "event": event,
            "start_pos": start_pos,
            "end_pos": end_pos
        }
    
    def _extract_event(self, text: str, start_pos: int, end_pos: int) -> str:
        """提取时间词关联的事件（周围上下文）"""
        # 取时间词前后各20个字符作为上下文
        ctx_start = max(0, start_pos - 20)
        ctx_end = min(len(text), end_pos + 20)
        context = text[ctx_start:ctx_end].strip()
        
        # 去掉时间词本身，提取剩余内容作为事件
        before = text[ctx_start:start_pos].strip()
        after = text[end_pos:ctx_end].strip()
        
        # 简单清理：去掉常见连接词
        for connector in ['，', '。', '、', '的', '了', '在', '是', '和', ' ', '就', '又']:
            before = before.rstrip(connector)
            after = after.lstrip(connector)
        
        event_parts = []
        if before:
            event_parts.append(before[-10:] if len(before) > 10 else before)
        if after:
            event_parts.append(after[:10] if len(after) > 10 else after)
        
        return ' '.join(event_parts) if event_parts else context[:20]
    
    def _get_week_range(self, category: str, day_offset: int) -> tuple:
        """计算周范围"""
        now = self.ref
        # 本周一
        days_since_monday = now.weekday()
        this_monday = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        
        if 'last' in category:
            start = this_monday + timedelta(weeks=1, days=day_offset)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        elif 'next' in category:
            start = this_monday + timedelta(weeks=1, days=day_offset)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        else:  # this_week
            start = this_monday
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        return start, end


# ============================================================
# 便捷函数
# ============================================================

def extract_temporal(text: str, reference_date: datetime = None) -> list[dict]:
    """
    从文本中提取所有时间信息（便捷函数）
    
    Args:
        text: 输入文本
        reference_date: 参考时间（默认当前时间）
        
    Returns:
        时间信息列表
    """
    extractor = TemporalExtractor(reference_date)
    return extractor.extract(text)


def extract_temporal_one(text: str, reference_date: datetime = None) -> Optional[dict]:
    """提取第一个时间信息（便捷函数）"""
    extractor = TemporalExtractor(reference_date)
    return extractor.extract_one(text)


def temporal_to_timestamp(temporal_info: dict) -> dict:
    """
    将时间信息转换为可存储的格式
    
    Returns:
        {"start_ts": 毫秒时间戳, "end_ts": 毫秒时间戳, "as_of": ISO字符串}
    """
    start = temporal_info.get("timestamp_range", {}).get("start", "")
    end = temporal_info.get("timestamp_range", {}).get("end", "")
    
    result = {
        "start_ts": None,
        "end_ts": None,
        "as_of": start
    }
    
    if start:
        try:
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            result["start_ts"] = int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            pass
    
    if end:
        try:
            dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            result["end_ts"] = int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            pass
    
    return result
