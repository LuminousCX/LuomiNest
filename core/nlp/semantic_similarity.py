"""
增强版语义相似度计算器
结合词汇向量、同义词、TF-IDF加权等多种方法
"""

from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from functools import lru_cache
import math
import re
from collections import defaultdict


@dataclass
class SimilarityResult:
    score: float
    method: str
    matched_terms: List[str]
    confidence: float


class SynonymDictionary:
    """同义词词典"""
    
    SYNONYMS = {
        "学习": ["读书", "进修", "研读", "学习", "求知", "学", "学习"],
        "工作": ["上班", "职业", "事业", "工作", "干活", "办公"],
        "编程": ["写代码", "开发", "编程", "程序设计", "coding", "程序开发"],
        "开心": ["高兴", "快乐", "愉快", "开心", "喜悦", "幸福", "欢乐"],
        "难过": ["伤心", "悲伤", "难过", "痛苦", "郁闷", "沮丧", "失落"],
        "生气": ["愤怒", "恼火", "生气", "不爽", "烦躁", "恼怒"],
        "喜欢": ["爱", "喜爱", "喜欢", "热爱", "中意"],
        "讨厌": ["厌恶", "讨厌", "不喜欢", "反感", "憎恶"],
        "帮助": ["帮忙", "协助", "帮助", "支援", "辅助"],
        "问题": ["疑问", "问题", "困惑", "难题"],
        "推荐": ["建议", "推荐", "介绍", "安利"],
        "时间": ["时候", "时间", "时刻"],
        "天气": ["气候", "天气", "气象"],
        "名字": ["姓名", "名字", "称呼", "名号"],
        "再见": ["拜拜", "再见", "告辞", "下次见"],
        "你好": ["您好", "你好", "嗨", "哈喽", "hello"],
        "谢谢": ["感谢", "谢谢", "多谢", "thanks"],
        "理解": ["明白", "理解", "懂", "了解", "清楚"],
        "不知道": ["不清楚", "不了解", "不知道", "不懂"],
        "怎么样": ["如何", "怎么样", "怎样", "咋样"],
        "为什么": ["为啥", "为什么", "原因", "何故"],
        "怎么": ["如何", "怎么", "怎样", "方法"],
        "什么": ["啥", "什么", "何"],
        "多少": ["几", "多少", "几何"],
        "哪里": ["哪", "哪里", "何处", "什么地方"],
        "谁": ["哪位", "谁", "何人"],
        "什么时候": ["何时", "什么时候", "哪天", "几点"],
        "电影": ["影片", "电影", "片子", "影视"],
        "音乐": ["歌曲", "音乐", "乐曲", "歌"],
        "游戏": ["游戏", "游玩", "玩"],
        "美食": ["食物", "美食", "吃的", "佳肴", "美味"],
        "旅游": ["旅行", "旅游", "出游", "游玩"],
        "健康": ["身体", "健康", "养生", "保健"],
        "运动": ["锻炼", "运动", "健身", "体育"],
        "钱": ["钱", "资金", "金钱", "费用", "钱款"],
        "朋友": ["好友", "朋友", "伙伴", "友人"],
        "家人": ["亲人", "家人", "家属", "家庭"],
        "爱": ["喜欢", "爱", "热爱", "喜爱"],
        "恨": ["讨厌", "恨", "厌恶", "憎恨"],
        "快": ["迅速", "快", "快速", "急速"],
        "慢": ["缓慢", "慢", "迟缓"],
        "好": ["棒", "好", "优秀", "不错", "很好", "好"],
        "坏": ["差", "坏", "不好", "糟糕"],
        "大": ["巨大", "大", "庞大", "大型"],
        "小": ["微小", "小", "细小", "小型"],
        "多": ["许多", "多", "大量", "众多"],
        "少": ["稀少", "少", "不多", "少量"],
        "新": ["新颖", "新", "最新", "崭新"],
        "旧": ["老旧", "旧", "陈旧", "过时"],
        "开始": ["启动", "开始", "着手", "开端"],
        "结束": ["完成", "结束", "完毕", "终结"],
        "打开": ["开启", "打开", "启动"],
        "关闭": ["关掉", "关闭", "停止", "关闭"],
        "搜索": ["查找", "搜索", "寻找", "检索"],
        "设置": ["配置", "设置", "设定", "配置"],
        "删除": ["移除", "删除", "清除", "去掉"],
        "添加": ["增加", "添加", "加入", "新增"],
        "修改": ["更改", "修改", "变更", "调整"],
        "查看": ["查看", "浏览", "查看", "看"],
        "播放": ["播放", "播放", "放", "播"],
        "暂停": ["暂停", "停止", "暂停"],
        "继续": ["继续", "接着", "继续", "延续"],
        "取消": ["撤销", "取消", "作废", "取消"],
        "确认": ["确定", "确认", "肯定", "确认"],
        "取消": ["取消", "取消", "撤销", "作废"],
        "登录": ["登入", "登录", "进入", "登录"],
        "登出": ["退出", "登出", "注销", "登出"],
        "注册": ["报名", "注册", "登记", "注册"],
        "下载": ["下载", "下载", "获取"],
        "上传": ["上传", "上传", "提交"],
        "分享": ["共享", "分享", "分享", "转发"],
        "保存": ["存储", "保存", "保存", "储存"],
        "复制": ["拷贝", "复制", "复制"],
        "粘贴": ["粘贴", "粘贴", "贴上"],
        "剪切": ["剪裁", "剪切", "剪切"],
        "撤销": ["撤回", "撤销", "取消", "撤销"],
        "重做": ["恢复", "重做", "重做"],
        "刷新": ["更新", "刷新", "刷新", "刷新"],
        "退出": ["离开", "退出", "退出", "退出"],
        "返回": ["后退", "返回", "返回", "返回"],
        "前进": ["向前", "前进", "前进"],
        "上一页": ["上一页", "上一页", "上一页"],
        "下一页": ["下一页", "下一页", "下一页"],
        "首页": ["主页", "首页", "首页", "首页"],
        "末页": ["最后一页", "末页", "末页"],
        "搜索": ["查找", "搜索", "寻找", "检索"],
        "筛选": ["过滤", "筛选", "筛选", "过滤"],
        "排序": ["排列", "排序", "排序", "排序"],
        "分组": ["分类", "分组", "分组", "分类"],
        "统计": ["分析", "统计", "统计", "统计"],
        "导出": ["输出", "导出", "导出", "输出"],
        "导入": ["输入", "导入", "导入", "输入"],
        "打印": ["打印", "打印", "打印", "打印"],
        "预览": ["预览", "预览", "预览", "预览"],
        "编辑": ["修改", "编辑", "编辑", "编辑"],
        "创建": ["新建", "创建", "创建", "创建"],
        "删除": ["移除", "删除", "删除", "删除"],
    }
    
    RELATED_WORDS = {
        "编程": ["代码", "程序", "开发", "软件", "工程", "算法", "数据结构", "函数", "变量", "类", "对象"],
        "学习": ["知识", "技能", "课程", "培训", "教育", "考试", "成绩", "学校", "老师", "学生"],
        "工作": ["职业", "公司", "同事", "老板", "工资", "加班", "项目", "任务", "会议", "报告"],
        "生活": ["日常", "习惯", "健康", "运动", "饮食", "睡眠", "家庭", "朋友", "娱乐", "休闲"],
        "情感": ["开心", "难过", "生气", "焦虑", "担心", "害怕", "兴奋", "平静", "紧张", "放松"],
        "科技": ["AI", "人工智能", "机器学习", "深度学习", "数据", "算法", "模型", "训练", "预测", "分析"],
        "美食": ["食物", "餐厅", "菜谱", "烹饪", "食材", "口味", "营养", "早餐", "午餐", "晚餐"],
        "旅游": ["景点", "酒店", "机票", "签证", "行程", "攻略", "度假", "出行", "目的地", "交通"],
        "娱乐": ["电影", "音乐", "游戏", "小说", "综艺", "直播", "动漫", "体育", "明星", "节目"],
        "健康": ["运动", "健身", "饮食", "睡眠", "心理", "医疗", "养生", "保健", "体检", "治疗"],
    }
    
    @classmethod
    def get_synonyms(cls, word: str) -> Set[str]:
        """获取同义词集合"""
        synonyms = {word}
        for key, values in cls.SYNONYMS.items():
            if word == key or word in values:
                synonyms.add(key)
                synonyms.update(values)
        return synonyms
    
    @classmethod
    def are_synonyms(cls, word1: str, word2: str) -> bool:
        """判断两个词是否是同义词"""
        if word1 == word2:
            return True
        return word2 in cls.get_synonyms(word1)
    
    @classmethod
    def get_related_words(cls, word: str) -> Set[str]:
        """获取相关词"""
        related = {word}
        for key, values in cls.RELATED_WORDS.items():
            if word == key or word in values:
                related.add(key)
                related.update(values)
        return related


class SemanticVectorGenerator:
    """语义向量生成器"""
    
    WORD_VECTORS = {
        "学习": {"学习": 1.0, "读书": 0.85, "课程": 0.75, "培训": 0.7, "教育": 0.65, "知识": 0.6, "技能": 0.55, "考试": 0.5, "学校": 0.45},
        "工作": {"工作": 1.0, "职业": 0.85, "上班": 0.8, "职场": 0.75, "事业": 0.7, "项目": 0.6, "公司": 0.55, "工资": 0.5, "加班": 0.45},
        "编程": {"编程": 1.0, "代码": 0.9, "程序": 0.85, "开发": 0.85, "python": 0.75, "java": 0.75, "javascript": 0.75, "函数": 0.65, "变量": 0.6},
        "开心": {"开心": 1.0, "高兴": 0.9, "快乐": 0.9, "兴奋": 0.75, "喜悦": 0.85, "幸福": 0.7, "愉快": 0.8, "欢乐": 0.75, "满足": 0.65},
        "难过": {"难过": 1.0, "伤心": 0.9, "悲伤": 0.9, "痛苦": 0.8, "郁闷": 0.75, "沮丧": 0.75, "失落": 0.7, "忧愁": 0.65, "哀伤": 0.6},
        "生气": {"生气": 1.0, "愤怒": 0.9, "恼火": 0.85, "不爽": 0.8, "讨厌": 0.7, "烦躁": 0.75, "恼怒": 0.85, "愤慨": 0.7, "恼恨": 0.65},
        "焦虑": {"焦虑": 1.0, "担心": 0.85, "紧张": 0.8, "害怕": 0.75, "恐惧": 0.7, "不安": 0.75, "忧虑": 0.8, "惶恐": 0.65, "忐忑": 0.7},
        "帮助": {"帮助": 1.0, "帮忙": 0.9, "协助": 0.85, "支援": 0.75, "辅助": 0.7, "支持": 0.65, "指导": 0.6, "解答": 0.55},
        "推荐": {"推荐": 1.0, "建议": 0.85, "介绍": 0.75, "安利": 0.8, "推荐": 0.95, "意见": 0.6, "参考": 0.55, "指南": 0.5},
        "问题": {"问题": 1.0, "疑问": 0.85, "困惑": 0.8, "难题": 0.75, "疑问": 0.85, "疑虑": 0.7, "疑惑": 0.75, "不解": 0.65},
        "时间": {"时间": 1.0, "时候": 0.85, "时刻": 0.8, "时段": 0.7, "时期": 0.65, "期间": 0.6, "光阴": 0.5, "岁月": 0.45},
        "天气": {"天气": 1.0, "气候": 0.85, "气象": 0.8, "气温": 0.75, "温度": 0.7, "晴天": 0.65, "雨天": 0.65, "阴天": 0.6},
        "电影": {"电影": 1.0, "影片": 0.9, "片子": 0.75, "影视": 0.8, "电影": 0.95, "剧场": 0.6, "影院": 0.65, "大片": 0.55},
        "音乐": {"音乐": 1.0, "歌曲": 0.9, "乐曲": 0.85, "歌": 0.8, "音乐": 0.95, "旋律": 0.7, "曲子": 0.65, "歌声": 0.6},
        "游戏": {"游戏": 1.0, "游玩": 0.8, "玩": 0.75, "游戏": 0.95, "电竞": 0.7, "网游": 0.65, "手游": 0.65, "主机": 0.55},
        "美食": {"美食": 1.0, "食物": 0.85, "吃的": 0.7, "佳肴": 0.8, "美味": 0.85, "料理": 0.75, "餐饮": 0.65, "菜肴": 0.7},
        "旅游": {"旅游": 1.0, "旅行": 0.9, "出游": 0.85, "游玩": 0.8, "度假": 0.85, "旅行": 0.9, "出行": 0.7, "观光": 0.65},
        "健康": {"健康": 1.0, "身体": 0.85, "养生": 0.8, "保健": 0.75, "健康": 0.95, "医疗": 0.6, "治疗": 0.55, "康复": 0.5},
        "运动": {"运动": 1.0, "锻炼": 0.9, "健身": 0.85, "体育": 0.8, "运动": 0.95, "训练": 0.7, "活动": 0.6, "竞技": 0.55},
        "科技": {"科技": 1.0, "技术": 0.85, "科学": 0.8, "科技": 0.95, "创新": 0.7, "研发": 0.65, "前沿": 0.55, "黑科技": 0.6},
        "AI": {"AI": 1.0, "人工智能": 0.95, "机器学习": 0.8, "深度学习": 0.75, "AI": 0.95, "智能": 0.7, "算法": 0.6, "模型": 0.55},
        "聊天": {"聊天": 1.0, "对话": 0.85, "交流": 0.8, "沟通": 0.75, "聊天": 0.95, "谈话": 0.7, "闲聊": 0.65, "倾诉": 0.6},
        "搜索": {"搜索": 1.0, "查找": 0.85, "寻找": 0.8, "检索": 0.75, "搜索": 0.95, "查询": 0.7, "搜寻": 0.65, "搜查": 0.55},
        "设置": {"设置": 1.0, "配置": 0.85, "设定": 0.8, "调整": 0.75, "设置": 0.95, "参数": 0.6, "选项": 0.55, "偏好": 0.5},
        "删除": {"删除": 1.0, "移除": 0.85, "清除": 0.8, "去掉": 0.75, "删除": 0.95, "消除": 0.6, "卸载": 0.55, "擦除": 0.5},
    }
    
    INTENT_VECTORS = {
        "greeting": {"你好": 1.0, "您好": 1.0, "嗨": 0.9, "哈喽": 0.9, "hello": 0.85, "hi": 0.85, "早上好": 0.8, "下午好": 0.8, "晚上好": 0.8},
        "farewell": {"再见": 1.0, "拜拜": 0.95, "bye": 0.9, "晚安": 0.85, "下次见": 0.8, "告辞": 0.7, "先走了": 0.65},
        "gratitude": {"谢谢": 1.0, "感谢": 0.95, "多谢": 0.9, "thanks": 0.85, "thank": 0.8, "谢谢你": 0.9, "非常感谢": 0.85},
        "ask_time": {"几点": 1.0, "时间": 0.85, "现在": 0.8, "今天": 0.75, "日期": 0.8, "星期": 0.75, "几号": 0.8},
        "ask_weather": {"天气": 1.0, "气温": 0.9, "温度": 0.85, "下雨": 0.8, "晴天": 0.8, "阴天": 0.75, "雪": 0.75, "风": 0.7},
        "ask_name": {"名字": 1.0, "叫什么": 0.95, "你是谁": 0.9, "自我介绍": 0.85, "姓名": 0.8},
        "set_name": {"我叫": 1.0, "我的名字": 0.95, "你可以叫我": 0.9, "我是": 0.85},
        "help": {"帮助": 1.0, "help": 0.95, "怎么用": 0.9, "使用方法": 0.85, "功能": 0.8, "教程": 0.75},
        "continuation": {"再来": 1.0, "继续": 0.95, "还有呢": 0.9, "然后呢": 0.85, "新的": 0.7, "另一个": 0.75},
        "clarification": {"什么意思": 1.0, "是什么": 0.9, "详细": 0.85, "解释": 0.8, "具体": 0.75, "展开": 0.7},
        "why_question": {"为什么": 1.0, "为啥": 0.95, "原因": 0.85, "怎么会": 0.8, "为何": 0.75},
        "how_to": {"怎么": 1.0, "如何": 0.95, "怎样": 0.9, "方法": 0.85, "步骤": 0.8, "教程": 0.75},
        "what_is": {"是什么": 1.0, "什么是": 0.95, "介绍": 0.85, "解释": 0.8, "定义": 0.75},
        "opinion": {"你觉得": 1.0, "你认为": 0.95, "怎么看": 0.9, "想法": 0.85, "观点": 0.8},
        "comparison": {"区别": 1.0, "比较": 0.9, "对比": 0.9, "差异": 0.85, "哪个好": 0.85, "不同": 0.75},
        "recommendation": {"推荐": 1.0, "建议": 0.9, "有什么好": 0.85, "介绍": 0.8, "安利": 0.75},
        "emotional_sad": {"难过": 1.0, "伤心": 0.95, "悲伤": 0.95, "痛苦": 0.9, "哭": 0.85, "不开心": 0.85, "郁闷": 0.8, "沮丧": 0.8},
        "emotional_happy": {"开心": 1.0, "高兴": 0.95, "快乐": 0.95, "兴奋": 0.85, "喜悦": 0.9, "幸福": 0.85, "太棒了": 0.8},
        "emotional_angry": {"生气": 1.0, "愤怒": 0.95, "恼火": 0.9, "不爽": 0.85, "讨厌": 0.8, "烦": 0.75},
        "emotional_anxious": {"焦虑": 1.0, "担心": 0.9, "紧张": 0.85, "害怕": 0.85, "恐惧": 0.8, "不安": 0.75},
        "feedback_positive": {"很好": 1.0, "不错": 0.95, "很棒": 0.95, "厉害": 0.9, "优秀": 0.85, "完美": 0.9},
        "feedback_negative": {"不好": 1.0, "不行": 0.95, "错误": 0.9, "不对": 0.9, "有问题": 0.85, "不满意": 0.8},
    }
    
    @classmethod
    def get_word_vector(cls, word: str) -> Dict[str, float]:
        """获取词向量"""
        if word in cls.WORD_VECTORS:
            return cls.WORD_VECTORS[word]
        return {}
    
    @classmethod
    def get_intent_vector(cls, intent: str) -> Dict[str, float]:
        """获取意图向量"""
        if intent in cls.INTENT_VECTORS:
            return cls.INTENT_VECTORS[intent]
        return {}


class TFIDFCalculator:
    """TF-IDF 计算器"""
    
    def __init__(self):
        self.document_freq = defaultdict(int)
        self.total_docs = 0
        self.term_freq_cache = {}
    
    def add_document(self, text: str):
        """添加文档"""
        terms = self._tokenize(text)
        unique_terms = set(terms)
        for term in unique_terms:
            self.document_freq[term] += 1
        self.total_docs += 1
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        text = re.sub(r'[，。！？；：""''（）【】\s]+', ' ', text.lower())
        words = [w for w in text.split() if len(w) > 1]
        return words
    
    @lru_cache(maxsize=1000)
    def _get_term_freq(self, text: str) -> Dict[str, float]:
        """计算词频"""
        if text in self.term_freq_cache:
            return self.term_freq_cache[text]
        
        terms = self._tokenize(text)
        if not terms:
            return {}
        
        freq = defaultdict(int)
        for term in terms:
            freq[term] += 1
        
        total = len(terms)
        tf = {term: count / total for term, count in freq.items()}
        self.term_freq_cache[text] = tf
        return tf
    
    def calculate_tfidf(self, text: str) -> Dict[str, float]:
        """计算 TF-IDF"""
        tf = self._get_term_freq(text)
        tfidf = {}
        
        for term, freq in tf.items():
            df = self.document_freq.get(term, 1)
            idf = math.log((self.total_docs + 1) / (df + 1)) + 1
            tfidf[term] = freq * idf
        
        return tfidf
    
    def get_important_terms(self, text: str, top_n: int = 5) -> List[Tuple[str, float]]:
        """获取重要词"""
        tfidf = self.calculate_tfidf(text)
        sorted_terms = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)
        return sorted_terms[:top_n]


class SemanticSimilarityCalculator:
    """增强版语义相似度计算器"""
    
    STOP_WORDS = {
        '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
        '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
        '自己', '这', '那', '里', '来', '他', '她', '它', '们', '这个', '那个', '什么',
        '怎么', '如何', '为什么', '哪', '哪里', '谁', '几', '多少', '能', '可以', '想',
        '要', '把', '被', '让', '给', '从', '向', '对', '与', '及', '或', '但', '而',
        '如果', '因为', '所以', '虽然', '但是', '然后', '接着', '于是', '因此', '否则',
    }
    
    def __init__(self):
        self.tfidf_calc = TFIDFCalculator()
        self.synonym_dict = SynonymDictionary()
        self.vector_gen = SemanticVectorGenerator()
    
    @lru_cache(maxsize=500)
    def _tokenize(self, text: str) -> Tuple[str, ...]:
        """分词（带缓存）"""
        text = re.sub(r'[，。！？；：""''（）【】\s]+', ' ', text.lower())
        words = [w for w in text.split() if w and len(w) > 0]
        return tuple(words)
    
    def calculate_similarity(
        self,
        text1: str,
        text2: str,
        methods: List[str] = None
    ) -> SimilarityResult:
        """计算两段文本的相似度"""
        if methods is None:
            methods = ['jaccard', 'semantic', 'synonym', 'tfidf']
        
        scores = []
        matched_terms = []
        
        if 'jaccard' in methods:
            score, terms = self._jaccard_similarity(text1, text2)
            scores.append(('jaccard', score, 0.25))
            matched_terms.extend(terms)
        
        if 'semantic' in methods:
            score, terms = self._semantic_similarity(text1, text2)
            scores.append(('semantic', score, 0.35))
            matched_terms.extend(terms)
        
        if 'synonym' in methods:
            score, terms = self._synonym_similarity(text1, text2)
            scores.append(('synonym', score, 0.2))
            matched_terms.extend(terms)
        
        if 'tfidf' in methods:
            score, terms = self._tfidf_similarity(text1, text2)
            scores.append(('tfidf', score, 0.2))
            matched_terms.extend(terms)
        
        if not scores:
            return SimilarityResult(0.0, 'none', [], 0.0)
        
        total_weight = sum(w for _, _, w in scores)
        weighted_score = sum(s * w for _, s, w in scores) / total_weight
        
        matched_terms = list(set(matched_terms))
        confidence = min(len(matched_terms) / 5.0, 1.0)
        
        best_method = max(scores, key=lambda x: x[1])[0]
        
        return SimilarityResult(
            score=round(weighted_score, 4),
            method=best_method,
            matched_terms=matched_terms[:10],
            confidence=round(confidence, 3)
        )
    
    def _jaccard_similarity(self, text1: str, text2: str) -> Tuple[float, List[str]]:
        """Jaccard 相似度"""
        words1 = set(self._tokenize(text1))
        words2 = set(self._tokenize(text2))
        
        words1 = words1 - self.STOP_WORDS
        words2 = words2 - self.STOP_WORDS
        
        if not words1 or not words2:
            return 0.0, []
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0, []
        
        score = len(intersection) / len(union)
        return score, list(intersection)
    
    def _semantic_similarity(self, text1: str, text2: str) -> Tuple[float, List[str]]:
        """语义相似度"""
        words1 = self._tokenize(text1)
        words2 = self._tokenize(text2)
        
        if not words1 or not words2:
            return 0.0, []
        
        total_score = 0.0
        matched = []
        
        for w1 in words1:
            if w1 in self.STOP_WORDS:
                continue
            vec1 = self.vector_gen.get_word_vector(w1)
            if not vec1:
                continue
            
            for w2 in words2:
                if w2 in self.STOP_WORDS:
                    continue
                if w2 in vec1:
                    score = vec1[w2]
                    total_score += score
                    if score > 0.5:
                        matched.append(f"{w1}~{w2}")
        
        max_possible = min(len([w for w in words1 if w not in self.STOP_WORDS]),
                          len([w for w in words2 if w not in self.STOP_WORDS]))
        
        if max_possible == 0:
            return 0.0, []
        
        return total_score / max_possible, matched
    
    def _synonym_similarity(self, text1: str, text2: str) -> Tuple[float, List[str]]:
        """同义词相似度"""
        words1 = set(self._tokenize(text1)) - self.STOP_WORDS
        words2 = set(self._tokenize(text2)) - self.STOP_WORDS
        
        if not words1 or not words2:
            return 0.0, []
        
        synonym_matches = 0
        matched = []
        
        for w1 in words1:
            for w2 in words2:
                if self.synonym_dict.are_synonyms(w1, w2):
                    synonym_matches += 1
                    matched.append(f"{w1}={w2}")
                    break
        
        max_possible = min(len(words1), len(words2))
        if max_possible == 0:
            return 0.0, []
        
        return synonym_matches / max_possible, matched
    
    def _tfidf_similarity(self, text1: str, text2: str) -> Tuple[float, List[str]]:
        """TF-IDF 相似度"""
        tfidf1 = self.tfidf_calc.calculate_tfidf(text1)
        tfidf2 = self.tfidf_calc.calculate_tfidf(text2)
        
        if not tfidf1 or not tfidf2:
            return 0.0, []
        
        common_terms = set(tfidf1.keys()) & set(tfidf2.keys())
        if not common_terms:
            return 0.0, []
        
        dot_product = sum(tfidf1[t] * tfidf2[t] for t in common_terms)
        norm1 = math.sqrt(sum(v ** 2 for v in tfidf1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in tfidf2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0, []
        
        score = dot_product / (norm1 * norm2)
        return score, list(common_terms)
    
    def calculate_intent_similarity(
        self,
        text: str,
        intent: str
    ) -> Tuple[float, List[str]]:
        """计算文本与意图的相似度"""
        intent_vector = self.vector_gen.get_intent_vector(intent)
        if not intent_vector:
            return 0.0, []
        
        words = self._tokenize(text)
        if not words:
            return 0.0, []
        
        total_score = 0.0
        matched = []
        
        for word in words:
            if word in intent_vector:
                score = intent_vector[word]
                total_score += score
                matched.append(word)
        
        if not matched:
            return 0.0, []
        
        avg_score = total_score / len(matched)
        return avg_score, matched
    
    def find_best_intent(
        self,
        text: str,
        intents: List[str],
        threshold: float = 0.3
    ) -> Tuple[Optional[str], float, List[str]]:
        """找到最佳匹配的意图"""
        best_intent = None
        best_score = 0.0
        best_matched = []
        
        for intent in intents:
            score, matched = self.calculate_intent_similarity(text, intent)
            if score > best_score:
                best_score = score
                best_intent = intent
                best_matched = matched
        
        if best_score < threshold:
            return None, 0.0, []
        
        return best_intent, best_score, best_matched
    
    def expand_query(self, query: str) -> List[str]:
        """扩展查询（添加同义词和相关词）"""
        words = self._tokenize(query)
        expanded = set([query])
        
        for word in words:
            if word in self.STOP_WORDS:
                continue
            
            synonyms = self.synonym_dict.get_synonyms(word)
            for syn in synonyms:
                if syn != word:
                    expanded.add(query.replace(word, syn))
            
            related = self.synonym_dict.get_related_words(word)
            for rel in related:
                if rel != word:
                    expanded.add(f"{query} {rel}")
        
        return list(expanded)[:10]


_semantic_calculator: Optional[SemanticSimilarityCalculator] = None


def get_semantic_calculator() -> SemanticSimilarityCalculator:
    """获取语义相似度计算器单例"""
    global _semantic_calculator
    if _semantic_calculator is None:
        _semantic_calculator = SemanticSimilarityCalculator()
    return _semantic_calculator
