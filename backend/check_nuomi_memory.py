
import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.engines.memory import get_memory_engine
from app.infrastructure.database.json_store import agents_store


def main():
    print("=" * 60)
    print("查找糯米Agent...")
    print("=" * 60)
    
    # 列出所有Agent
    agents = agents_store.all()
    nuomi_agent = None
    print(f"\n找到 {len(agents)} 个Agent:")
    for agent in agents:
        agent_id = agent.get("id")
        name = agent.get("name", "未知")
        print(f"  - ID: {agent_id}, 名称: {name}")
        if "糯米" in name or "nuomi" in name.lower():
            nuomi_agent = agent
    
    if not nuomi_agent:
        print("\n⚠️  未找到名为'糯米'的Agent，尝试查找所有Agent的记忆...")
        memory_root = Path(settings.DATA_DIR) / "memory" / "agents"
        if memory_root.exists():
            for d in sorted(memory_root.iterdir()):
                if d.is_dir() and (d / "memory.json").exists():
                    print(f"\n发现记忆文件夹: {d.name}")
    else:
        print(f"\n✅ 找到糯米Agent: {nuomi_agent.get('name')} (ID: {nuomi_agent.get('id')})")
    
    agent_id = nuomi_agent.get("id") if nuomi_agent else None
    
    if agent_id:
        print(f"\n{'=' * 60}")
        print(f"糯米Agent的记忆总结 (ID: {agent_id})")
        print('=' * 60)
        
        engine = get_memory_engine(agent_id)
        data = engine.load_data()
        
        # 打印用户档案
        print(f"\n📋 用户档案:")
        print(f"   名字: {data.profile.name}")
        print(f"   更新时间: {data.profile.updated_at}")
        
        # 打印事实
        print(f"\n📊 记忆事实 ({len(data.facts)} 条):")
        if data.facts:
            for fact in data.facts[:10]:  # 只显示前10条
                print(f"   [{fact.category}] (置信度: {fact.confidence:.2f}): {fact.content}")
                if fact.source_error:
                    print(f"     ⚠️  避免: {fact.source_error}")
            if len(data.facts) > 10:
                print(f"   ... 还有 {len(data.facts) - 10} 条事实")
        
        # 打印AI总结 - 显示所有5个维度，即使为空
        print(f"\n✨ AI总结 (共5个维度):")
        sections = {
            "用户画像": data.summaries.user_profile,
            "偏好设置": data.summaries.preferences,
            "兴趣目标": data.summaries.interests,
            "近期状态": data.summaries.recent_state,
            "事件时间线": data.summaries.timeline,
        }
        
        for name, section in sections.items():
            print(f"\n--- {name} ---")
            if section.summary:
                print(section.summary)
            else:
                print("  (空)")
        
        # 打印近期对话
        dailies = engine.list_dailies()
        print(f"\n📅 近期对话 ({len(dailies)} 天):")
        for date in dailies[-3:]:  # 最近3天
            content = engine.load_daily(date)
            print(f"\n  {date}:")
            lines = content.split('\n')
            for line in lines[:5]:  # 每天最多5行
                if line.strip():
                    print(f"    {line}")
        
        # 打印知识记忆
        knowledge = engine.load_knowledge()
        if knowledge.strip():
            print(f"\n📚 知识记忆:")
            print(knowledge)
        
        print(f"\n{'=' * 60}")
        print("分析结果:")
        print('=' * 60)
        empty_sections = [name for name, section in sections.items() if not section.summary]
        if empty_sections:
            print(f"\n⚠️  发现 {len(empty_sections)} 个空的总结维度:")
            for name in empty_sections:
                print(f"   - {name}")
            print("\n建议: 需要重新触发AI蒸馏来填充这些维度。")
        else:
            print("\n✅ 所有5个总结维度都有内容")
        
        print(f"\n{'=' * 60}")
        print("完成")
        print('=' * 60)


if __name__ == "__main__":
    main()

