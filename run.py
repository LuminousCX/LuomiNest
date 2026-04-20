"""LuomiNest 启动入口。

支持两种运行模式：
1. Web API 模式（默认）：启动 FastAPI 服务
2. CLI 模式：命令行交互

使用方式：
    python run.py              # 启动 Web API 服务
    python run.py --cli        # 启动命令行交互模式
    python run.py --port 8000  # 指定端口启动
"""

from __future__ import annotations

import argparse
import sys


def run_api_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """启动 FastAPI Web API 服务。"""
    import uvicorn

    uvicorn.run(
        "src.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


def run_cli_mode() -> None:
    """启动命令行交互模式。"""
    from src.api.deps import init_services
    from src.service.agent_service import AgentService
    from src.service.chat_service import ChatService
    from src.utils.logger import get_logger

    logger = get_logger()
    services = init_services()
    agent_service: AgentService = services["agent_service"]
    chat_service: ChatService = services["chat_service"]

    current_agent = agent_service.get_current_agent()
    print(f"\n{'='*50}")
    print(f"  LuomiNest CLI 模式")
    print(f"  当前 Agent: {current_agent.name}")
    print(f"  输入 /help 查看帮助，/quit 退出")
    print(f"{'='*50}\n")

    if current_agent.greeting:
        print(f"[{current_agent.name}]: {current_agent.greeting}\n")

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input == "/quit" or user_input == "/exit":
            if current_agent.farewell:
                print(f"\n[{current_agent.name}]: {current_agent.farewell}")
            print("再见！")
            break

        if user_input == "/help":
            print("可用命令：")
            print("  /help    - 显示帮助")
            print("  /quit    - 退出程序")
            print("  /agents  - 列出所有 Agent")
            print("  /switch  - 切换 Agent")
            print("  /mode    - 切换模式 (expert/fast)")
            continue

        if user_input == "/agents":
            agents = agent_service.get_all_agents()
            for a in agents:
                marker = " * " if a.id == current_agent.id else "   "
                print(f"{marker}{a.name} ({a.type.value}) - {a.description}")
            continue

        if user_input.startswith("/switch "):
            name = user_input[8:].strip()
            agents = agent_service.get_all_agents()
            target = next((a for a in agents if a.name == name), None)
            if target:
                current_agent = agent_service.switch_agent(target.id)
                print(f"已切换到: {current_agent.name}")
            else:
                print(f"未找到 Agent: {name}")
            continue

        if user_input.startswith("/mode "):
            mode_str = user_input[6:].strip()
            if mode_str in ("expert", "fast"):
                print(f"模式已切换为: {mode_str}")
            else:
                print("可用模式: expert, fast")
            continue

        import asyncio
        from src.model.conversation import ResponseMode
        from src.schema.chat_schema import ChatRequest

        request = ChatRequest(
            content=user_input,
            mode=ResponseMode.FAST,
            stream=False,
        )

        try:
            response = asyncio.run(chat_service.chat(request))
            print(f"\n[{current_agent.name}]: {response.content}\n")
        except Exception as e:
            logger.error(f"对话失败: {e}")
            print(f"\n[错误]: {e}\n")


def main() -> None:
    """主入口函数。"""
    parser = argparse.ArgumentParser(description="LuomiNest AI Agent 桌面应用")
    parser.add_argument("--cli", action="store_true", help="启动命令行交互模式")
    parser.add_argument("--host", default="127.0.0.1", help="API 服务监听地址")
    parser.add_argument("--port", type=int, default=8000, help="API 服务监听端口")
    args = parser.parse_args()

    if args.cli:
        run_cli_mode()
    else:
        run_api_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
