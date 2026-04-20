"""
火山方舟流式聊天服务
支持专家模式和快速模式
"""

import os
import time
from typing import Generator, List, Dict, Optional

HAS_API = False
client = None

try:
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    HAS_API = True
    
    API_KEY = os.getenv("API_KEY", "")
    MODEL_ID = os.getenv("MODEL_ID", "")
    
    if API_KEY:
        client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v1",
            api_key=API_KEY
        )
        print(f"[OK] OpenAI 客户端初始化成功")
    else:
        print("[WARN] 未找到 API_KEY")
        
except ImportError:
    print("[WARN] OpenAI 库未安装")


class StreamChatService:
    """流式聊天服务"""
    
    def __init__(self, api_key: str = "", model_id: str = ""):
        self.api_key = api_key or API_KEY
        self.model_id = model_id or MODEL_ID
        self.client = client
        self._mode_manager = None
    
    def _get_mode_manager(self):
        """延迟加载模式管理器"""
        if self._mode_manager is None:
            from core.response_mode import get_response_mode_manager
            self._mode_manager = get_response_mode_manager()
        return self._mode_manager
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        use_mode_settings: bool = True
    ) -> Generator[str, None, None]:
        """流式聊天
        
        Args:
            messages: 消息列表
            temperature: 温度参数（None时使用模式设置）
            max_tokens: 最大token数（None时使用模式设置）
            use_mode_settings: 是否使用模式设置
        """
        if not HAS_API or not self.client:
            yield "[ERROR] API 服务不可用"
            return
        
        if use_mode_settings:
            mode_manager = self._get_mode_manager()
            if temperature is None:
                temperature = mode_manager.get_temperature()
            if max_tokens is None:
                max_tokens = mode_manager.get_max_tokens()
            
            thinking_delay = mode_manager.get_thinking_delay()
            if thinking_delay > 0:
                time.sleep(thinking_delay / 1000.0)
        
        if temperature is None:
            temperature = 0.7
        if max_tokens is None:
            max_tokens = 1024
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            yield f"[ERROR] API 调用失败: {str(e)}"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        use_mode_settings: bool = True
    ) -> str:
        """非流式聊天"""
        result = ""
        for chunk in self.chat_stream(messages, temperature, max_tokens, use_mode_settings):
            result += chunk
        return result
    
    def chat_with_mode(
        self,
        messages: List[Dict[str, str]],
        mode: str = None
    ) -> Generator[str, None, None]:
        """使用指定模式进行聊天
        
        Args:
            messages: 消息列表
            mode: 模式名称 ('expert' 或 'fast')
        """
        if mode:
            from core.response_mode import ResponseMode
            try:
                mode_enum = ResponseMode(mode)
                mode_manager = self._get_mode_manager()
                config = mode_manager.get_mode_config(mode_enum)
                
                thinking_delay = config.thinking_delay_ms
                if thinking_delay > 0:
                    time.sleep(thinking_delay / 1000.0)
                
                yield from self.chat_stream(
                    messages,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    use_mode_settings=False
                )
            except ValueError:
                yield from self.chat_stream(messages, use_mode_settings=True)
        else:
            yield from self.chat_stream(messages, use_mode_settings=True)
    
    def is_ready(self) -> bool:
        """检查服务是否可用"""
        return HAS_API and self.client is not None
    
    def get_current_mode_info(self) -> Dict[str, any]:
        """获取当前模式信息"""
        mode_manager = self._get_mode_manager()
        config = mode_manager.get_current_config()
        return {
            'mode': mode_manager.get_current_mode().value,
            'display_name': config.display_name,
            'description': config.description,
            'temperature': config.temperature,
            'max_tokens': config.max_tokens
        }


_service: Optional[StreamChatService] = None


def get_stream_chat_service(api_key: str = "", model_id: str = "") -> StreamChatService:
    """获取流式聊天服务单例"""
    global _service
    if _service is None:
        _service = StreamChatService(api_key, model_id)
    return _service
