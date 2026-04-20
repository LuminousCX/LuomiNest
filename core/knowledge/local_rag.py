import json
import os
import re
from functools import lru_cache
from typing import List, Dict, Tuple

class LocalRAG:
    def __init__(self, knowledge_base_path):
        self.knowledge_base_path = knowledge_base_path
        self.knowledge_base = self.load_knowledge_base()
        self._build_search_index()  # 构建搜索索引
    
    def _build_search_index(self):
        """构建搜索索引，提高搜索速度"""
        self.keyword_index = {}  # 关键词倒排索引
        for idx, item in enumerate(self.knowledge_base):
            question = item.get('question', '')
            keywords = self._extract_keywords_fast(question)
            for keyword in keywords:
                if keyword not in self.keyword_index:
                    self.keyword_index[keyword] = []
                self.keyword_index[keyword].append(idx)
    
    def load_knowledge_base(self):
        """加载知识库"""
        if os.path.exists(self.knowledge_base_path):
            try:
                with open(self.knowledge_base_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 检查数据格式，如果是字符串数组，转换为对象数组
                    if isinstance(data, list):
                        formatted_data = []
                        for i, item in enumerate(data):
                            if isinstance(item, str):
                                # 将字符串转换为对象格式
                                formatted_data.append({
                                    "id": i + 1,
                                    "question": item,
                                    "answer": item
                                })
                            else:
                                formatted_data.append(item)
                        return formatted_data
                    return data
            except Exception:
                return []
        return []
    
    def save_knowledge_base(self):
        """保存知识库"""
        with open(self.knowledge_base_path, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
        # 重新构建索引
        self._build_search_index()
    
    def add_knowledge(self, question, answer):
        """添加知识"""
        knowledge = {
            "id": len(self.knowledge_base) + 1,
            "question": question,
            "answer": answer
        }
        self.knowledge_base.append(knowledge)
        self.save_knowledge_base()
        return knowledge
    
    @lru_cache(maxsize=1000)  # 添加缓存
    def _extract_keywords_fast(self, text: str) -> tuple:
        """快速提取关键词（带缓存）"""
        # 移除标点符号
        text = re.sub(r'[，。！？；："\'（）【】]', ' ', text.lower())
        # 分词（简单的空格分词）
        keywords = text.split()
        # 过滤停用词
        stop_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        return tuple(word for word in keywords if word not in stop_words and len(word) > 1)
    
    def search_knowledge(self, query, threshold=0.3):  # 降低阈值，提高召回率
        """搜索知识（优化版）"""
        query_keywords = self._extract_keywords_fast(query)
        if not query_keywords:
            return []
        
        # 使用倒排索引快速查找
        candidate_indices = set()
        for keyword in query_keywords:
            if keyword in self.keyword_index:
                candidate_indices.update(self.keyword_index[keyword])
        
        # 如果索引中没有找到，回退到全量搜索
        if not candidate_indices:
            return self._search_knowledge_fallback(query, threshold)
        
        # 计算相似度
        results = []
        for idx in candidate_indices:
            if idx < len(self.knowledge_base):
                item = self.knowledge_base[idx]
                score = self._calculate_similarity_fast(query_keywords, item.get('question', ''))
                if score >= threshold:
                    results.append((item, score))
        
        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in results[:5]]
    
    def _search_knowledge_fallback(self, query, threshold):
        """回退搜索方法"""
        results = []
        for item in self.knowledge_base:
            score = self._calculate_similarity_fast(
                self._extract_keywords_fast(query),
                item.get('question', '')
            )
            if score >= threshold:
                results.append((item, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in results[:5]]
    
    def _calculate_similarity_fast(self, query_keywords: tuple, text: str) -> float:
        """快速计算相似度"""
        text_keywords = self._extract_keywords_fast(text)
        if not query_keywords or not text_keywords:
            return 0.0
        
        # 计算共同关键词
        common_keywords = set(query_keywords) & set(text_keywords)
        if not common_keywords:
            return 0.0
        
        # Jaccard相似度
        return len(common_keywords) / (len(query_keywords) + len(text_keywords) - len(common_keywords))
    
    def get_knowledge_count(self):
        """获取知识数量"""
        return len(self.knowledge_base)
    
    def clear_knowledge_base(self):
        """清空知识库"""
        self.knowledge_base = []
        self.save_knowledge_base()
        # 清空缓存
        self._extract_keywords_fast.cache_clear()