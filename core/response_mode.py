"""
响应模式管理器
支持专家模式和快速模式，根据不同模式调整AI的响应策略
"""

import json
import os
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


class ResponseMode(Enum):
    """响应模式枚举"""
    EXPERT = "expert"
    FAST = "fast"


@dataclass
class ModeConfig:
    """模式配置"""
    name: str
    display_name: str
    description: str
    temperature: float
    max_tokens: int
    thinking_delay_ms: int
    response_style: str
    detail_level: str
    system_prompt_suffix: str
    features: list = field(default_factory=list)


class ResponseModeManager:
    """响应模式管理器"""
    
    MODE_CONFIGS: Dict[ResponseMode, ModeConfig] = {
        ResponseMode.EXPERT: ModeConfig(
            name="expert",
            display_name="专家模式",
            description="深度思考，精准回答，详尽解释",
            temperature=0.5,
            max_tokens=2048,
            thinking_delay_ms=1500,
            response_style="detailed",
            detail_level="high",
            system_prompt_suffix="""
【专家模式要求】
- 深度分析问题，提供全面、专业的回答
- 回答结构清晰，使用分点、分段组织内容
- 提供具体例子、数据或案例支持观点
- 考虑多种可能性，分析利弊
- 使用专业术语并适当解释
- 回答要有深度和广度
- 必要时提供延伸阅读建议
- 确保回答准确、严谨、有逻辑性""",
            features=[
                "深度分析",
                "专业术语",
                "案例支持",
                "多角度思考",
                "延伸建议"
            ]
        ),
        ResponseMode.FAST: ModeConfig(
            name="fast",
            display_name="快速模式",
            description="快速响应，简洁高效，直击要点",
            temperature=0.8,
            max_tokens=512,
            thinking_delay_ms=300,
            response_style="concise",
            detail_level="low",
            system_prompt_suffix="""
【快速模式要求】
- 快速理解问题核心，直接给出答案
- 回答简洁明了，避免冗余内容
- 使用简短的句子和段落
- 突出关键信息，省略不必要的细节
- 适合日常快速咨询场景
- 保持友好但高效""",
            features=[
                "快速响应",
                "简洁明了",
                "直击要点",
                "高效沟通"
            ]
        )
    }
    
    DEFAULT_MODE = ResponseMode.FAST
    
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.mode_file = os.path.join(storage_path, "response_mode.json")
        self.current_mode = self._load_mode()
        self.mode_history = []
        
    def _load_mode(self) -> ResponseMode:
        """加载保存的模式"""
        if os.path.exists(self.mode_file):
            try:
                with open(self.mode_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    mode_str = data.get('current_mode', self.DEFAULT_MODE.value)
                    return ResponseMode(mode_str)
            except Exception as e:
                print(f"[WARNING] 加载响应模式失败: {e}")
        return self.DEFAULT_MODE
    
    def _save_mode(self):
        """保存当前模式"""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            data = {
                'current_mode': self.current_mode.value,
                'mode_name': self.get_current_config().display_name
            }
            with open(self.mode_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARNING] 保存响应模式失败: {e}")
    
    def set_mode(self, mode: ResponseMode) -> Dict[str, Any]:
        """设置响应模式"""
        old_mode = self.current_mode
        self.current_mode = mode
        self._save_mode()
        
        self.mode_history.append({
            'from': old_mode.value,
            'to': mode.value,
        })
        
        config = self.get_current_config()
        return {
            'success': True,
            'previous_mode': old_mode.value,
            'current_mode': mode.value,
            'display_name': config.display_name,
            'description': config.description,
            'features': config.features
        }
    
    def get_current_mode(self) -> ResponseMode:
        """获取当前模式"""
        return self.current_mode
    
    def get_current_config(self) -> ModeConfig:
        """获取当前模式配置"""
        return self.MODE_CONFIGS[self.current_mode]
    
    def get_mode_config(self, mode: ResponseMode) -> ModeConfig:
        """获取指定模式的配置"""
        return self.MODE_CONFIGS[mode]
    
    def get_all_modes(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模式信息"""
        result = {}
        for mode, config in self.MODE_CONFIGS.items():
            result[mode.value] = {
                'name': config.name,
                'display_name': config.display_name,
                'description': config.description,
                'features': config.features,
                'temperature': config.temperature,
                'max_tokens': config.max_tokens,
                'thinking_delay_ms': config.thinking_delay_ms
            }
        return result
    
    def get_system_prompt_suffix(self) -> str:
        """获取当前模式的系统提示词后缀"""
        return self.get_current_config().system_prompt_suffix
    
    def get_temperature(self) -> float:
        """获取当前模式的温度参数"""
        return self.get_current_config().temperature
    
    def get_max_tokens(self) -> int:
        return self.get_current_config().max_tokens
    
    def get_thinking_delay(self) -> int:
        """获取思考延迟时间（毫秒）"""
        return self.get_current_config().thinking_delay_ms
    
    def toggle_mode(self) -> Dict[str, Any]:
        """切换模式"""
        if self.current_mode == ResponseMode.EXPERT:
            return self.set_mode(ResponseMode.FAST)
        else:
            return self.set_mode(ResponseMode.EXPERT)
    
    def is_expert_mode(self) -> bool:
        """是否为专家模式"""
        return self.current_mode == ResponseMode.EXPERT
    
    def is_fast_mode(self) -> bool:
        """是否为快速模式"""
        return self.current_mode == ResponseMode.FAST
    
    def get_mode_summary(self) -> str:
        """获取模式摘要（用于上下文注入）"""
        config = self.get_current_config()
        return f"""【当前响应模式：{config.display_name}】
{config.description}
特点：{', '.join(config.features)}
"""
    
    def get_full_system_prompt(self, base_prompt: str) -> str:
        """获取完整的系统提示词"""
        return base_prompt + "\n" + self.get_system_prompt_suffix()


_mode_manager: Optional[ResponseModeManager] = None


def get_response_mode_manager(storage_path: str = "data") -> ResponseModeManager:
    """获取响应模式管理器单例"""
    global _mode_manager
    if _mode_manager is None:
        _mode_manager = ResponseModeManager(storage_path)
    return _mode_manager
