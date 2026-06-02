import asyncio
from app.engines.memory import get_memory_engine
from app.runtime.provider.llm.adapter import llm_adapter

async def test_memory_update():
    agent_id = "f39f2452-0f2e-466b-9fce-cef688be55a3"
    engine = get_memory_engine(agent_id)
    
    # 先查看当前记忆状态
    print("=== 初始记忆状态 ===")
    data = engine.load_data()
    print(f"Profile name: {data.profile.name}")
    print(f"Fact count: {len(data.facts)}")
    for i, fact in enumerate(data.facts):
        print(f"  {i+1}. [{fact.category}] {fact.content}")
    
    # 模拟一条用户消息
    messages = [
        {"role": "user", "content": "我想去公园散步"},
        {"role": "assistant", "content": "好的，公园里空气清新，很适合散步。"},
    ]
    
    # 更新记忆
    print("\n=== 更新记忆 ===")
    try:
        # 更新profile
        profile_result = await engine.update_profile_from_message("我想去公园散步", llm_adapter)
        print(f"Profile更新结果: {profile_result}")
        
        # 添加日常记录
        engine.append_daily("[用户] 我想去公园散步\n[助手] 好的，公园里空气清新，很适合散步。")
        print("日常记录已添加")
        
        # 蒸馏对话
        distill_result = await engine.distill_conversation(messages, llm_adapter)
        print(f"蒸馏结果: {distill_result}")
        
    except Exception as e:
        print(f"更新记忆时出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 重新加载并查看更新后的状态
    print("\n=== 更新后的记忆状态 ===")
    # 强制重新加载（清除缓存）
    engine._cache = None
    data = engine.load_data()
    print(f"Profile name: {data.profile.name}")
    print(f"Fact count: {len(data.facts)}")
    for i, fact in enumerate(data.facts):
        print(f"  {i+1}. [{fact.category}] {fact.content}")
    
    # 检查memory.json文件
    print("\n=== 检查文件内容 ===")
    import json
    from pathlib import Path
    from app.core.config import settings
    memory_path = Path(settings.DATA_DIR) / "memory" / "agents" / agent_id / "memory.json"
    with open(memory_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    print(f"文件中的Fact数量: {len(raw_data.get('facts', []))}")
    print(f"最后更新时间: {raw_data.get('last_updated')}")

if __name__ == "__main__":
    asyncio.run(test_memory_update())