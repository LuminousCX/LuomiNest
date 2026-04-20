"""
AI人格配置管理器
存储和管理AI的名字、性格、说话风格、情绪状态等
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

class MoodState(Enum):
    """情绪状态枚举"""
    HAPPY = "happy"
    CALM = "calm"
    EXCITED = "excited"
    THOUGHTFUL = "thoughtful"
    CARING = "caring"
    NEUTRAL = "neutral"

class AIPersonalityManager:
    """AI人格配置管理器"""
    
    DEFAULT_PERSONALITY = {
        "identity": {
            "name": "汐汐",
            "full_name": "Luminous辰汐",
            "role": "智能助手",
            "creator": "LumiNest团队",
            "version": "1.0",
        },
        "personality": {
            "core_traits": ["温柔", "耐心", "细心", "友善", "聪明"],
            "communication_style": "详细有条理",
            "formality": "casual",
            "empathy_level": "high",
            "humor_style": "gentle",
        },
        "speaking_style": {
            "greeting_patterns": [
                "你好呀！",
                "嗨！很高兴见到你！",
                "你好！有什么我可以帮你的吗？",
            ],
            "thinking_expressions": [
                "让我想想...",
                "嗯，这个问题很有趣...",
                "让我来帮你分析一下...",
            ],
            "closing_patterns": [
                "还有其他问题吗？",
                "希望能帮到你！",
                "随时可以问我哦！",
            ],
            "encouragement": [
                "你做得很好！",
                "加油！",
                "相信你可以的！",
            ],
            "apology_patterns": [
                "抱歉，我可能没理解你的意思...",
                "不好意思，让我重新回答...",
            ],
        },
        "knowledge_areas": [
            "学习规划", "生活建议", "编程技术", 
            "健康养生", "旅游攻略", "美食推荐"
        ],
        "limitations": [
            "无法访问实时网络信息",
            "无法执行实际操作",
            "无法记住所有对话细节"
        ],
        "mood": {
            "current_state": "calm",
            "intensity": 0.7,
            "last_updated": None,
        },
        "memory_highlights": [],
        "special_instructions": [
            "回答要详细、有条理",
            "提供具体建议和例子",
            "保持友善和耐心",
            "根据用户需求调整回答风格"
        ]
    }
    
    PERSONALITY_PRESETS = {
        "default": {
            "core_traits": ["温柔", "耐心", "细心", "友善", "聪明"],
            "communication_style": "详细有条理",
            "formality": "casual",
        },
        "professional": {
            "core_traits": ["专业", "严谨", "高效", "可靠"],
            "communication_style": "简洁专业",
            "formality": "formal",
        },
        "friendly": {
            "core_traits": ["活泼", "幽默", "热情", "开朗"],
            "communication_style": "轻松活泼",
            "formality": "casual",
        },
        "teacher": {
            "core_traits": ["耐心", "细致", "严谨", "鼓励"],
            "communication_style": "循循善诱",
            "formality": "semi-formal",
        },
        "companion": {
            "core_traits": ["温暖", "体贴", "理解", "陪伴"],
            "communication_style": "温柔细腻",
            "formality": "casual",
        }
    }
    
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.personality_file = os.path.join(storage_path, "ai_personality.json")
        self.personality = self._load_personality()
        self.mood_history = []
        self._mode_manager = None
    
    def _get_mode_manager(self):
        """延迟加载模式管理器"""
        if self._mode_manager is None:
            from core.response_mode import get_response_mode_manager
            self._mode_manager = get_response_mode_manager(self.storage_path)
        return self._mode_manager
        
    def _load_personality(self) -> Dict:
        """加载AI人格配置"""
        if os.path.exists(self.personality_file):
            try:
                with open(self.personality_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    merged = self._merge_with_default(loaded)
                    return merged
            except Exception as e:
                print(f"[WARNING] 加载AI人格配置失败: {e}")
        return self.DEFAULT_PERSONALITY.copy()
    
    def _merge_with_default(self, loaded: Dict) -> Dict:
        """合并加载的数据与默认值"""
        merged = self.DEFAULT_PERSONALITY.copy()
        for key, value in loaded.items():
            if key in merged:
                if isinstance(value, dict) and isinstance(merged[key], dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
        return merged
    
    def _save_personality(self):
        """保存AI人格配置"""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            with open(self.personality_file, 'w', encoding='utf-8') as f:
                json.dump(self.personality, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARNING] 保存AI人格配置失败: {e}")
    
    def get_system_prompt(self) -> str:
        """获取AI人格的系统提示词（用于API调用）"""
        identity = self.personality['identity']
        personality = self.personality['personality']
        style = self.personality['speaking_style']
        mood = self.personality['mood']
        
        traits_str = "、".join(personality['core_traits'])
        
        prompt = f"""【AI身份设定】
名字：{identity['name']}（{identity['full_name']}）
角色：{identity['role']}
创建者：{identity['creator']}

【性格特点】
核心特质：{traits_str}
沟通风格：{personality['communication_style']}
同理心等级：{personality['empathy_level']}
幽默风格：{personality['humor_style']}

【说话习惯】
问候语风格：{style['greeting_patterns'][0]}
思考时会说：{style['thinking_expressions'][0]}
结束语风格：{style['closing_patterns'][0]}

【当前情绪状态】
情绪：{mood['current_state']}
强度：{mood['intensity']}

【回答要求】
"""
        for instruction in self.personality['special_instructions']:
            prompt += f"- {instruction}\n"
        
        mode_manager = self._get_mode_manager()
        mode_config = mode_manager.get_current_config()
        prompt += f"\n【当前响应模式：{mode_config.display_name}】\n"
        prompt += mode_config.system_prompt_suffix
        
        return prompt
    
    def get_name(self) -> str:
        """获取AI名字"""
        return self.personality['identity']['name']
    
    def get_full_name(self) -> str:
        """获取AI全名"""
        return self.personality['identity']['full_name']
    
    def get_role(self) -> str:
        """获取AI角色"""
        return self.personality['identity']['role']
    
    def get_greeting(self) -> str:
        """获取问候语"""
        import random
        return random.choice(self.personality['speaking_style']['greeting_patterns'])
    
    def get_thinking_expression(self) -> str:
        """获取思考表达"""
        import random
        return random.choice(self.personality['speaking_style']['thinking_expressions'])
    
    def get_closing(self) -> str:
        """获取结束语"""
        import random
        return random.choice(self.personality['speaking_style']['closing_patterns'])
    
    def set_name(self, name: str):
        """设置AI名字"""
        self.personality['identity']['name'] = name
        self._save_personality()
    
    def set_mood(self, mood: str, intensity: float = 0.7):
        """设置情绪状态"""
        if mood in [m.value for m in MoodState]:
            self.personality['mood']['current_state'] = mood
            self.personality['mood']['intensity'] = intensity
            self.personality['mood']['last_updated'] = datetime.now().isoformat()
            self._save_personality()
    
    def apply_preset(self, preset_name: str):
        """应用预设人格"""
        if preset_name in self.PERSONALITY_PRESETS:
            preset = self.PERSONALITY_PRESETS[preset_name]
            self.personality['personality'].update(preset)
            self._save_personality()
    
    def add_trait(self, trait: str):
        """添加性格特点"""
        if trait not in self.personality['personality']['core_traits']:
            self.personality['personality']['core_traits'].append(trait)
            self._save_personality()
    
    def remove_trait(self, trait: str):
        """移除性格特点"""
        if trait in self.personality['personality']['core_traits']:
            self.personality['personality']['core_traits'].remove(trait)
            self._save_personality()
    
    def add_greeting_pattern(self, pattern: str):
        """添加问候语模式"""
        if pattern not in self.personality['speaking_style']['greeting_patterns']:
            self.personality['speaking_style']['greeting_patterns'].append(pattern)
            self._save_personality()
    
    def add_special_instruction(self, instruction: str):
        """添加特殊指令"""
        if instruction not in self.personality['special_instructions']:
            self.personality['special_instructions'].append(instruction)
            self._save_personality()
    
    def add_memory_highlight(self, highlight: str):
        """添加记忆亮点"""
        if highlight not in self.personality['memory_highlights']:
            self.personality['memory_highlights'].append(highlight)
            self._save_personality()
    
    def get_memory_highlights(self) -> List[str]:
        """获取记忆亮点"""
        return self.personality.get('memory_highlights', [])
    
    def set_communication_style(self, style: str):
        """设置沟通风格"""
        self.personality['personality']['communication_style'] = style
        self._save_personality()
    
    def set_formality(self, formality: str):
        """设置正式程度"""
        if formality in ['casual', 'semi-formal', 'formal']:
            self.personality['personality']['formality'] = formality
            self._save_personality()
    
    def reset_to_default(self):
        """重置为默认人格"""
        self.personality = self.DEFAULT_PERSONALITY.copy()
        self._save_personality()
    
    def get_full_personality(self) -> Dict:
        """获取完整人格配置"""
        return self.personality.copy()
    
    def get_available_presets(self) -> List[str]:
        """获取可用的预设列表"""
        return list(self.PERSONALITY_PRESETS.keys())
    
    def get_current_mode(self) -> str:
        """获取当前响应模式"""
        mode_manager = self._get_mode_manager()
        return mode_manager.get_current_mode().value
    
    def set_response_mode(self, mode: str) -> Dict[str, Any]:
        """设置响应模式
        
        Args:
            mode: 'expert' 或 'fast'
        """
        from core.response_mode import ResponseMode
        mode_manager = self._get_mode_manager()
        try:
            mode_enum = ResponseMode(mode)
            return mode_manager.set_mode(mode_enum)
        except ValueError:
            return {'success': False, 'error': f'无效的模式: {mode}'}
    
    def toggle_response_mode(self) -> Dict[str, Any]:
        """切换响应模式"""
        mode_manager = self._get_mode_manager()
        return mode_manager.toggle_mode()
    
    def get_mode_info(self) -> Dict[str, Any]:
        """获取当前模式信息"""
        mode_manager = self._get_mode_manager()
        config = mode_manager.get_current_config()
        return {
            'mode': mode_manager.get_current_mode().value,
            'display_name': config.display_name,
            'description': config.description,
            'features': config.features,
            'temperature': config.temperature,
            'max_tokens': config.max_tokens,
            'thinking_delay_ms': config.thinking_delay_ms
        }
