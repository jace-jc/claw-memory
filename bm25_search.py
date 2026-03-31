"""
BM25搜索引擎 - 支持中英文混合分词
使用字符级n-gram处理中文，保留英文单词边界
"""
import math
import re
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("ClawMemory.BM25")


class BM25Search:
    """
    BM25搜索引擎
    
    分词策略：
    - 英文：按单词边界分割
    - 中文：字符级n-gram (2-3字符) + 简单词汇匹配
    """
    
    def __init__(self, corpus: List[Dict[str, Any]] = None, k1: float = 1.5, b: float = 0.75):
        """
        Args:
            corpus: 语料库
            k1: BM25参数 (通常1.2-2.0)
            b: BM25参数 (通常0.75)
        """
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avgdl = 0
        self.doc_freqs = {}  # term -> doc frequency
        self.idf = {}
        self.doc_len = []    # doc length (in tokens)
        
        if corpus:
            self.build_index(corpus)
    
    def _is_chinese(self, char: str) -> bool:
        """判断是否为中文字符"""
        return '\u4e00' <= char <= '\u9fff'
    
    def _tokenize_chinese(self, text: str) -> List[str]:
        """
        中文分词 - 使用字符级n-gram
        
        策略：
        - 2-gram: 捕获常见词组合
        - 3-gram: 捕获长词
        """
        tokens = []
        text = text.lower()
        
        # 预处理：提取英文单词和数字
        english_words = re.findall(r'[a-z0-9]+', text)
        
        # 提取中文字符序列
        chinese_chars = []
        for char in text:
            if self._is_chinese(char):
                chinese_chars.append(char)
            else:
                if chinese_chars:
                    # 对连续中文字符进行n-gram切分
                    char_seq = ''.join(chinese_chars)
                    # 2-gram
                    for i in range(len(char_seq) - 1):
                        tokens.append(char_seq[i:i+2])
                    # 3-gram (长序列时)
                    if len(char_seq) > 2:
                        for i in range(len(char_seq) - 2):
                            tokens.append(char_seq[i:i+3])
                    chinese_chars = []
        
        # 处理最后的中文字符序列
        if chinese_chars:
            char_seq = ''.join(chinese_chars)
            for i in range(len(char_seq) - 1):
                tokens.append(char_seq[i:i+2])
            if len(char_seq) > 2:
                for i in range(len(char_seq) - 2):
                    tokens.append(char_seq[i:i+3])
        
        # 添加英文单词
        tokens.extend(english_words)
        
        return tokens
    
    def _tokenize_english(self, text: str) -> List[str]:
        """英文分词"""
        text = text.lower()
        return re.findall(r'\b[a-z0-9]+\b', text)
    
    def _tokenize(self, text: str) -> List[str]:
        """
        混合分词 - 自动识别语言
        """
        if not text:
            return []
        
        # 判断是否包含中文
        has_chinese = any(self._is_chinese(c) for c in text)
        
        if has_chinese:
            return self._tokenize_chinese(text)
        else:
            return self._tokenize_english(text)
    
    def build_index(self, corpus: List[Dict[str, Any]]):
        """
        构建BM25索引
        
        Args:
            corpus: [{"id": "xxx", "content": "文本"}, ...]
        """
        self._corpus = corpus  # 存储语料库引用
        self.corpus_size = len(corpus)
        self.doc_freqs = defaultdict(int)
        self.doc_len = []
        
        # 统计词频
        for doc in corpus:
            content = doc.get("content", "")
            tokens = self._tokenize(content)
            self.doc_len.append(len(tokens))
            
            # 统计文档频率 (去重)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1
        
        # 计算平均文档长度
        self.avgdl = sum(self.doc_len) / self.corpus_size if self.corpus_size > 0 else 0
        
        # 计算IDF
        self._calculate_idf()
        
        logger.info(f"BM25索引构建完成: {self.corpus_size}文档, {len(self.doc_freqs)}词项")
    
    def _calculate_idf(self):
        """计算IDF值"""
        for term, freq in self.doc_freqs.items():
            # BM25 IDF 公式: log((N - n + 0.5) / (n + 0.5) + 1)
            idf = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1)
            self.idf[term] = max(idf, 0)
    
    def get_scores(self, query: str) -> List[float]:
        """
        获取查询对所有文档的BM25分数
        
        Args:
            query: 查询字符串
            
        Returns:
            每个文档的BM25分数列表
        """
        query_terms = self._tokenize(query)
        scores = []
        
        # 统计查询词频
        query_tf = Counter(query_terms)
        
        for i, doc in enumerate(self._corpus):
            doc_tokens = self._tokenize(doc.get("content", ""))
            doc_tf = Counter(doc_tokens)
            
            score = 0.0
            for term, qtf in query_tf.items():
                if term in doc_tf:
                    tf = doc_tf[term]
                    idf = self.idf.get(term, 0)
                    
                    # BM25公式
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                    score += idf * numerator / denominator
            
            scores.append(score)
        
        return scores
    
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        搜索最相关的文档
        
        Args:
            query: 查询字符串
            top_k: 返回前k个结果
            
        Returns:
            [{"id": "xxx", "score": 0.95, "content": "..."}, ...]
        """
        scores = self.get_scores(query)
        
        # 按分数排序
        doc_scores = [
            (i, scores[i]) 
            for i in range(len(scores))
            if scores[i] > 0
        ]
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 返回top_k
        results = []
        for i, score in doc_scores[:top_k]:
            if i < len(self._corpus):
                results.append({
                    "id": self._corpus[i].get("id", str(i)),
                    "score": score,
                    "content": self._corpus[i].get("content", ""),
                    "type": self._corpus[i].get("type", "unknown")
                })
        
        return results
    
    def set_corpus(self, corpus: List[Dict[str, Any]]):
        """设置语料库（用于search时）"""
        self._corpus = corpus
        if corpus:
            self.build_index(corpus)


# 全局实例缓存
_bm25_cache: Optional[BM25Search] = None
_last_mem_count = 0


def get_bm25_search(memories: List[Dict[str, Any]], force_rebuild: bool = False) -> BM25Search:
    """
    获取BM25搜索引擎实例
    
    Args:
        memories: 记忆列表
        force_rebuild: 是否强制重建索引
        
    Returns:
        BM25Search实例
    """
    global _bm25_cache, _last_mem_count
    
    mem_count = len(memories)
    
    # 如果记忆数量变化或强制重建，重新构建
    if _bm25_cache is None or force_rebuild or mem_count != _last_mem_count:
        logger.info(f"构建BM25索引: {mem_count}条记忆")
        _bm25_cache = BM25Search(memories)
        _last_mem_count = mem_count
    
    return _bm25_cache


def bm25_search(query: str, memories: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    便捷BM25搜索函数
    """
    bm25 = get_bm25_search(memories)
    bm25.set_corpus(memories)
    return bm25.search(query, top_k)
