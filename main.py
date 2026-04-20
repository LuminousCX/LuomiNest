"""
LumiNest 智能助手主入口
Author: LumiNest Team
Date: 2026-04-14
"""
import sys

from core.conversation.conversation_manager import ConversationManager
from core.smart_memory_manager import SmartMemoryManager
from core.knowledge.knowledge_manager import KnowledgeManager
from core.ai_personality import AIPersonalityManager
from core.constants import WELCOME_MESSAGE
from utils.config import config
from utils.logger import logger


class Application:
    """应用程序主类
    
    负责初始化系统组件和管理主循环
    """
    
    def __init__(self):
        """初始化应用程序"""
        self.memory_manager: SmartMemoryManager = None
        self.knowledge_manager: KnowledgeManager = None
        self.ai_personality_manager: AIPersonalityManager = None
        self.conversation_manager: ConversationManager = None

    def initialize(self) -> bool:
        """初始化系统组件
        
        Returns:
            bool: 初始化是否成功
        """
        print("初始化系统...")
        
        try:
            self.memory_manager = SmartMemoryManager(config.get("memory_path"))
            
            self.knowledge_manager = KnowledgeManager(
                config.get("knowledge_base_path"),
                config.get("vector_store_path")
            )
            
            self.ai_personality_manager = AIPersonalityManager("data")
            print(f"[OK] AI人格已加载: {self.ai_personality_manager.get_name()}")
            
            self.knowledge_manager.set_ai_personality_manager(self.ai_personality_manager)
            
            self.conversation_manager = ConversationManager(
                self.memory_manager,
                self.knowledge_manager,
                self.ai_personality_manager.get_name()
            )
            self.conversation_manager.ai_personality_manager = self.ai_personality_manager
            
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    def run(self) -> None:
        """运行主循环"""
        print(WELCOME_MESSAGE)
        
        ai_name = self.ai_personality_manager.get_name()
        print(f"[{ai_name}] 已启动，输入 /help 查看可用命令")
        print("=" * 50)
        
        while True:
            try:
                user_input = input("请输入你的问题：")
                if not user_input:
                    continue
                
                response = self.conversation_manager.process_input(user_input)
                self._handle_response(response, ai_name)
                print("=" * 50)
                
            except KeyboardInterrupt:
                print("\n再见！")
                break
            except Exception as e:
                logger.error(f"处理输入时出错: {e}")
                print("[系统] 抱歉，我遇到了一些问题，请稍后再试。")
                print("=" * 50)

    def _handle_response(self, response, ai_name: str) -> None:
        """处理响应输出
        
        Args:
            response: 响应内容
            ai_name: AI名称
        """
        if response is None:
            return
        
        if hasattr(response, '__iter__') and not isinstance(response, str):
            print(f"[{ai_name}] ", end='', flush=True)
            for chunk in response:
                print(chunk, end='', flush=True)
            print()
        else:
            print(f"[{ai_name}] {response}")


def main() -> None:
    """主入口函数"""
    app = Application()
    if app.initialize():
        app.run()


if __name__ == "__main__":
    main()
