from typing import Tuple, Optional


class ContentSafetyFilter:
    DANGEROUS_KEYWORDS = {
        '杀人', '杀害', '谋杀', '刺杀', '暗杀', '屠杀', '灭口',
        '爆炸', '炸弹', '恐怖', '袭击', '攻击',
        '伤害', '殴打', '虐待', '酷刑',
        '自杀', '自残', '轻生', '寻死',
        '贩毒', '吸毒', '走私', '洗钱',
        '抢劫', '盗窃', '诈骗', '勒索',
        '纵火', '放火', '投毒', '下毒',
    }
    
    SELF_HARM_KEYWORDS = {'自杀', '自残', '轻生', '寻死'}
    
    ILLEGAL_KEYWORDS = {'贩毒', '吸毒', '走私', '洗钱', '抢劫', '盗窃', '诈骗', '勒索'}
    
    SENSITIVE_KEYWORDS = {'政治', '宗教', '种族', '歧视'}
    
    STRICT_BANNED = {
        '鸡巴', '骚逼', '操', '日你', '射精', '高潮了', '做爱视频',
        '操逼', '傻逼', '妈逼', '草泥马', '操你', '操他', '操她',
        '性交', '乱伦', '强奸', '迷奸', '轮奸', '强暴',
        '嫖娼', '卖淫', '召妓', '约炮', '一夜情',
        '手淫', '自慰', '撸管', '打飞机',
        '口交', '肛交', '群交', '性虐',
        '裸聊', '裸体', '脱衣', '艳照',
    }
    
    SENSITIVE_ANATOMY = {
        '阴蒂', '阴道', '阴茎', '乳房', '龟头', '处女膜', '勃起', '高潮',
        '性器官', '生殖器', '睾丸', '卵巢', '子宫', '前列腺',
        '月经', '遗精', '早泄', '阳痿', '性病', '艾滋病',
    }
    
    EROTIC_CONTEXT = {
        '好舒服', '爽', '插', '舔', '摸', '性交', '自慰', 'AV',
        '色情', '快感', '硬了', '湿了', '想要', '受不了',
    }
    
    EDU_KEYWORDS = {
        '是什么', '功能', '作用', '结构', '解剖', '生理', '生物', '医学',
        '健康', '科普', '知识', '怎么回事', '原因', '位置', '定义',
        'wiki', '百科', '症状', '治疗', '预防', '检查', '诊断',
    }
    
    SAFETY_MESSAGES = {
        'violence': "[WARNING] 我检测到您的内容涉及暴力或伤害。如果您正在经历困难时期，请寻求专业帮助。\n\n[EMERGENCY] 紧急求助电话：\n- 心理援助热线：400-161-9995\n- 报警电话：110\n- 急救电话：120",
        'self_harm': "[WARNING] 我检测到您可能正在经历困难。请记住，您并不孤单，有很多人愿意帮助您。\n\n[EMERGENCY] 24小时心理援助热线：400-161-9995\n[EMERGENCY] 北京心理危机研究与干预中心：010-82951332\n[EMERGENCY] 生命热线：400-821-1215",
        'illegal': "[WARNING] 我无法协助任何违法活动。如果您需要法律帮助，请咨询专业律师。",
        'sensitive': "[WARNING] 这个话题比较敏感，我建议您寻求更专业的信息来源。",
        'adult_content': "[WARNING] 我检测到您的内容涉及不当内容。如果您有健康或医学相关问题，建议咨询专业医生。",
        'educational_hint': "[INFO] 这是一个医学/健康相关问题，建议咨询专业医生获取准确信息。",
    }

    def _is_educational_query(self, text: str) -> bool:
        return any(kw in text.lower() for kw in self.EDU_KEYWORDS)

    def _contains_banned_advanced(self, text: str) -> Tuple[bool, Optional[str]]:
        if any(word in text for word in self.STRICT_BANNED):
            return True, self.SAFETY_MESSAGES['adult_content']
        
        for word in self.SENSITIVE_ANATOMY:
            if word in text:
                if self._is_educational_query(text):
                    return False, self.SAFETY_MESSAGES['educational_hint']
                if any(ctx in text for ctx in self.EROTIC_CONTEXT):
                    return True, self.SAFETY_MESSAGES['adult_content']
        
        return False, None

    def check_content(self, content: str) -> Tuple[bool, Optional[str]]:
        content_lower = content.lower()
        
        if any(kw in content_lower for kw in self.DANGEROUS_KEYWORDS):
            if any(kw in content_lower for kw in self.SELF_HARM_KEYWORDS):
                return False, self.SAFETY_MESSAGES['self_harm']
            return False, self.SAFETY_MESSAGES['violence']
        
        if any(kw in content_lower for kw in self.ILLEGAL_KEYWORDS):
            return False, self.SAFETY_MESSAGES['illegal']
        
        if any(kw in content_lower for kw in self.SENSITIVE_KEYWORDS):
            return False, self.SAFETY_MESSAGES['sensitive']
        
        is_banned, message = self._contains_banned_advanced(content)
        if is_banned:
            return False, message
        
        return True, None

    def is_safe(self, content: str) -> bool:
        is_safe, _ = self.check_content(content)
        return is_safe

    def get_safety_message(self, content: str) -> Optional[str]:
        _, message = self.check_content(content)
        return message


safety_filter = ContentSafetyFilter()
