import re

class KeywordExtractor:
    def __init__(self):
        # 停用词列表
        self.stop_words = set([
            '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'
        ])
    
    def extract_keywords(self, text):
        """提取关键词"""
        # 移除标点符号
        text = re.sub(r'[，。！？；："\'（）【】]', ' ', text)
        # 分词（简单的空格分词）
        words = text.split()
        # 过滤停用词和短词
        keywords = [word for word in words if word not in self.stop_words and len(word) > 1]
        return keywords
    
    def extract_keywords_with_weight(self, text):
        """提取关键词并计算权重"""
        keywords = self.extract_keywords(text)
        # 计算词频
        word_freq = {}
        for word in keywords:
            word_freq[word] = word_freq.get(word, 0) + 1
        # 计算权重
        total = len(keywords)
        keyword_weights = {word: freq / total for word, freq in word_freq.items()}
        # 按权重排序
        sorted_keywords = sorted(keyword_weights.items(), key=lambda x: x[1], reverse=True)
        return sorted_keywords
    
    def get_top_keywords(self, text, top_n=5):
        """获取 top N 关键词"""
        sorted_keywords = self.extract_keywords_with_weight(text)
        return [item[0] for item in sorted_keywords[:top_n]]