"""Minecraft 模组轻量级本地测试模拟客户端 (LuomiNest Minecraft Mod Mock Simulator).

无需运行沉重的 Java Minecraft 服务端或安装游戏客户端，即可在本地秒级试验：
1. 模拟 Minecraft 客户端 Mod 通过 WebSocket 连接 LuomiNest (ws://127.0.0.1:8081)
2. 持续上报角色物理环境遥测 (telemetry: 坐标、生命值、饱食度、注视方块、周围敌对生物)
3. 发送模拟游戏第一人称截图 (screenshot: base64 数据)
4. 发送玩家聊天 (chat)，触发 LuomiNest 主 Agent / DeepSeek 决策规划
5. 接收并响应大模型下发的具身动作 (action: navigate, mine_block, attack, place_block 等)

运行方法:
    .venv/Scripts/python scripts/mc_mod_mock.py [--host 127.0.0.1] [--port 8081]
"""

import argparse
import asyncio
import json
import time

# 极小 1x1 像素有效 PNG Base64，用于模拟游戏画面
SAMPLE_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


async def run_simulator(host: str, port: int, player_name: str = "Steve") -> None:
    import websockets

    uri = f"ws://{host}:{port}"
    print(f"==================================================")
    print(f"🎮 LuomiNest Minecraft Mod 模拟客户端已启动")
    print(f"🔗 正在连接平台适配器: {uri}")
    print(f"👤 模拟玩家: {player_name}")
    print(f"==================================================")

    retry_count = 0
    while True:
        try:
            async with websockets.connect(uri) as ws:
                print(f"✅ 成功接入 LuomiNest Minecraft 适配器 WebSocket 端点！")

                # 1. 发送初始遥测状态 (telemetry)
                initial_telemetry = {
                    "type": "telemetry",
                    "player": player_name,
                    "dimension": "minecraft:overworld",
                    "position": [128.5, 64.0, -256.0],
                    "rotation": [90.0, 15.0],
                    "health": 20,
                    "hunger": 18,
                    "equipment": {
                        "mainhand": "minecraft:iron_sword",
                        "offhand": "minecraft:shield",
                    },
                    "inventory": [
                        {"item": "minecraft:bread", "count": 16},
                        {"item": "minecraft:torch", "count": 32},
                        {"item": "minecraft:iron_pickaxe", "count": 1},
                        {"item": "minecraft:cobblestone", "count": 64},
                    ],
                    "looking_at": "minecraft:diamond_ore",
                    "nearby_entities": [
                        {"type": "minecraft:zombie", "distance": 4.5, "position": [132.0, 64.0, -256.0]},
                        {"type": "minecraft:cow", "distance": 12.0, "position": [120.0, 64.0, -240.0]},
                    ],
                    "timestamp": time.time(),
                }
                await ws.send(json.dumps(initial_telemetry))
                print(f"📡 [上报遥测] 坐标: {initial_telemetry['position']}, 生命: 20/20, 注视: 钻石矿, 附近: 僵尸 (4.5格)")

                # 2. 发送初始第一人称游戏截图
                screenshot_pkt = {
                    "type": "screenshot",
                    "player": player_name,
                    "image_base64": SAMPLE_PNG_BASE64,
                    "prompt": "我眼前发现了钻石矿，但在距离4格的地方有一只僵尸正在靠近，请根据当前环境提供操作建议并指挥角色行动！",
                    "timestamp": time.time(),
                }
                await ws.send(json.dumps(screenshot_pkt))
                print(f"📸 [发送截图] 第一人称游戏画面已发送，附带提示词: '{screenshot_pkt['prompt'][:40]}...'")

                # 3. 循环监听来自 LuomiNest / DeepSeek 的动作指令与聊天
                while True:
                    raw_msg = await ws.recv()
                    data = json.loads(raw_msg)
                    msg_type = data.get("type", "")

                    if msg_type == "action":
                        action = data.get("action", "")
                        params = data.get("params", {})
                        action_id = data.get("action_id", "")
                        print(f"\n⚡ [收到 LLM 具身动作指令] -> {action.upper()}")
                        print(f"   参数: {json.dumps(params, ensure_ascii=False)}")

                        # 模拟在游戏引擎内执行该动作并返回结果
                        response_pkt = {
                            "type": "action_response",
                            "action_id": action_id,
                            "action": action,
                            "success": True,
                            "output": f"模组执行成功: {action} (参数已应用)",
                            "timestamp": time.time(),
                        }
                        await ws.send(json.dumps(response_pkt))
                        print(f"   ↳ 回执已发送: 动作已在虚拟世界执行完成")

                    elif msg_type == "chat" or "message" in data:
                        chat_content = data.get("message") or data.get("content") or ""
                        print(f"\n💬 [收到游戏聊天回复] -> {chat_content}")

                    else:
                        print(f"📩 [收到其他数据包]: {data}")

        except ConnectionRefusedError:
            retry_count += 1
            if retry_count % 5 == 1:
                print(f"⏳ 等待 LuomiNest Minecraft 适配器启动 (重试中: {uri})...")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"⚠️ 连接中断: {e}，2秒后自动重连...")
            await asyncio.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="LuomiNest Minecraft Mod 模拟客户端")
    parser.add_argument("--host", default="127.0.0.1", help="适配器 WebSocket 主机地址 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8081, help="适配器 WebSocket 端口 (默认 8081)")
    parser.add_argument("--player", default="Steve", help="模拟玩家名称 (默认 Steve)")
    args = parser.parse_args()

    asyncio.run(run_simulator(args.host, args.port, args.player))


if __name__ == "__main__":
    main()
