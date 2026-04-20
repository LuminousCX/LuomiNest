import re

class NameExtractor:
    def __init__(self):
        # 名字提取模式
        self.name_patterns = [
            r'我的名字叫(.*?)[，。！？]?',
            r'我叫(.*?)[，。！？]?',
            r'你可以叫我(.*?)[，。！？]?',
            r'我的名字是(.*?)[，。！？]?',
            r'我是(.*?)[，。！？]?',
            r'系统名字叫(.*?)[，。！？]?',
            r'你的名字叫(.*?)[，。！？]?',
            r'你改名叫(.*?)[，。！？]?',
            r'你现在改名叫(.*?)[，。！？]?',
            r'你的名字是(.*?)[，。！？]?'
        ]
    
    def extract_user_name(self, text):
        """提取用户名字"""
        user_patterns = [
            r'我的名字叫(.*?)[，。！？]?',
            r'我叫(.*?)[，。！？]?',
            r'你可以叫我(.*?)[，。！？]?',
            r'我的名字是(.*?)[，。！？]?',
            r'我是(.*?)[，。！？]?'
        ]
        
        for pattern in user_patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                # 移除名字中的无关字符
                name = re.sub(r'[，。！？]', '', name)
                return name
        return None
    
    def extract_system_name(self, text):
        """提取系统名字"""
        system_patterns = [
            r'系统名字叫(.*?)[，。！？]?',
            r'你的名字叫(.*?)[，。！？]?',
            r'你改名叫(.*?)[，。！？]?',
            r'你现在改名叫(.*?)[，。！？]?',
            r'你的名字是(.*?)[，。！？]?'
        ]
        
        for pattern in system_patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                # 移除名字中的无关字符
                name = re.sub(r'[，。！？]', '', name)
                return name
        return None
    
    def extract_name(self, text):
        """提取名字（通用）"""
        for pattern in self.name_patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                # 移除名字中的无关字符
                name = re.sub(r'[，。！？]', '', name)
                return name
        return None