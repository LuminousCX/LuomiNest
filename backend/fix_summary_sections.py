
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.engines.memory import get_memory_engine


async def distill_agent_memory(agent_id: str):
    """触发AI蒸馏来填充所有5个总结维度"""
    engine = get_memory_engine(agent_id)
    
    print(f"正在为Agent {agent_id} 触发AI蒸馏...")
    
    # 创建模拟对话来触发蒸馏
    # 包含用户的偏好信息
    messages = [
        {"role": "user", "content": "我不希望每次回复中包含我的名字"},
        {"role": "user", "content": "我喜欢简洁的回复风格"},
        {"role": "user", "content": "请用中文回复我"},
    ]
    
    result = await engine.distill_conversation(messages)
    
    if result:
        print("✅ AI蒸馏完成！")
        # 重新加载数据
        data = engine.load_data()
        
        print("\n更新后的总结维度:")
        sections = {
            "用户画像": data.summaries.user_profile.summary,
            "偏好设置": data.summaries.preferences.summary,
            "兴趣目标": data.summaries.interests.summary,
            "近期状态": data.summaries.recent_state.summary,
            "事件时间线": data.summaries.timeline.summary,
        }
        
        for name, content in sections.items():
            print(f"\n--- {name} ---")
            if content:
                lines = content.split('\n')[:3]  # 只显示前3行
                for line in lines:
                    print(line)
                if len(content.split('\n')) > 3:
                    print("...")
            else:
                print("  (空)")
    else:
        print("❌ AI蒸馏没有产生新结果")


def manual_fix_preferences(agent_id: str):
    """手动修复偏好设置维度"""
    engine = get_memory_engine(agent_id)
    data = engine.load_data()
    
    print("\n正在手动修复偏好设置...")
    
    # 从兴趣目标中提取偏好相关内容
    interests_summary = data.summaries.interests.summary
    
    # 识别偏好相关的内容
    preference_items = []
    if interests_summary:
        lines = interests_summary.split('\n')
        for line in lines:
            # 识别偏好相关的内容
            if any(keyword in line for keyword in ["不希望", "不喜欢", "喜欢", "风格", "回复"]):
                preference_items.append(line)
    
    # 如果找到偏好内容，移动到偏好设置
    if preference_items:
        print(f"找到 {len(preference_items)} 条偏好相关内容:")
        for item in preference_items:
            print(f"  - {item}")
        
        # 更新偏好设置
        data.summaries.preferences.summary = '\n'.join(preference_items)
        data.summaries.preferences.updated_at = data.summaries.interests.updated_at
        
        # 从兴趣目标中移除这些内容
        new_interests_lines = []
        if interests_summary:
            for line in interests_summary.split('\n'):
                if line not in preference_items:
                    new_interests_lines.append(line)
        data.summaries.interests.summary = '\n'.join(new_interests_lines)
        
        engine.save_data(data)
        print("\n✅ 偏好设置已修复！")
    else:
        print("没有找到需要移动的偏好内容")


if __name__ == "__main__":
    # 糯米Agent的ID
    agent_id = "dc738fcf-ec47-4f24-b431-f47727627a55"
    
    print("=" * 60)
    print("修复糯米Agent的偏好设置维度")
    print("=" * 60)
    
    # 先尝试手动修复
    manual_fix_preferences(agent_id)
    
    # 然后触发AI蒸馏来完善
    asyncio.run(distill_agent_memory(agent_id))
    
    print("\n" + "=" * 60)
    print("修复完成")
    print("=" * 60)
