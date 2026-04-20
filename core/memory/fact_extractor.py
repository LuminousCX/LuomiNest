import re

class FactExtractor:
    def __init__(self):
        # 事实提取模式
        self.patterns = {
            "name": [
                r'我的名字叫(.*?)[，。！？]?',
                r'我叫(.*?)[，。！？]?',
                r'你可以叫我(.*?)[，。！？]?',
                r'我的名字是(.*?)[，。！？]?',
                r'我是(.*?)[，。！？]?'
            ],
            "system_name": [
                r'系统名字叫(.*?)[，。！？]?',
                r'你的名字叫(.*?)[，。！？]?',
                r'你改名叫(.*?)[，。！？]?',
                r'你现在改名叫(.*?)[，。！？]?',
                r'你的名字是(.*?)[，。！？]?'
            ],
            "hobby": [
                r'我喜欢(.*?)[，。！？]?',
                r'我的爱好是(.*?)[，。！？]?',
                r'我爱好(.*?)[，。！？]?'
            ],
            "age": [
                r'我今年(.*?)岁[，。！？]?',
                r'我(.*?)岁[，。！？]?',
                r'我的年龄是(.*?)岁[，。！？]?'
            ],
            "location": [
                r'我在(.*?)[，。！？]?',
                r'我住在(.*?)[，。！？]?',
                r'我来自(.*?)[，。！？]?'
            ]
        }
    
    def extract_facts(self, text):
        """提取事实信息"""
        facts = {}
        
        for fact_type, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    value = match.group(1).strip()
                    # 移除无关字符
                    value = re.sub(r'[，。！？]', '', value)
                    facts[fact_type] = value
                    break
        
        return facts
    
    def extract_name(self, text):
        """提取用户名字"""
        for pattern in self.patterns.get("name", []):
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'[，。！？]', '', name)
                return name
        return None
    
    def extract_system_name(self, text):
        """提取系统名字"""
        for pattern in self.patterns.get("system_name", []):
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'[，。！？]', '', name)
                return name
        return None