"""清理非主 Agent 的历史记忆数据。

记忆系统现在仅对主 Agent（luominest_main_agent）生效，
联系人 Agent 不再读写记忆。本脚本用于一次性清理已存在的
联系人 Agent 记忆目录，释放磁盘空间并避免遗留数据。

用法：
    cd backend
    python -m scripts.cleanup_contact_memory          # 预览（dry-run）
    python -m scripts.cleanup_contact_memory --apply  # 实际执行删除
"""
import argparse
import shutil
from pathlib import Path

# 主 Agent 唯一标识（与 context_service.MAIN_AGENT_ID 保持一致）
MAIN_AGENT_ID = "luominest_main_agent"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
AGENTS_MEMORY_DIR = DATA_DIR / "memory" / "agents"


def list_agent_dirs() -> list[Path]:
    if not AGENTS_MEMORY_DIR.exists():
        return []
    return [p for p in AGENTS_MEMORY_DIR.iterdir() if p.is_dir()]


def main() -> None:
    parser = argparse.ArgumentParser(description="清理非主 Agent 的历史记忆数据")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际执行删除（默认仅预览）",
    )
    args = parser.parse_args()

    if not AGENTS_MEMORY_DIR.exists():
        print(f"[Skip] 记忆目录不存在: {AGENTS_MEMORY_DIR}")
        return

    agent_dirs = list_agent_dirs()
    if not agent_dirs:
        print(f"[Skip] 记忆目录为空: {AGENTS_MEMORY_DIR}")
        return

    print(f"记忆目录: {AGENTS_MEMORY_DIR}")
    print(f"发现 {len(agent_dirs)} 个 agent 目录\n")

    kept = 0
    removed = 0

    for agent_dir in agent_dirs:
        name = agent_dir.name
        if name == MAIN_AGENT_ID:
            print(f"[Keep] {name}  (主 Agent)")
            kept += 1
            continue

        size = sum(f.stat().st_size for f in agent_dir.rglob("*") if f.is_file())
        size_kb = size / 1024
        if args.apply:
            shutil.rmtree(agent_dir)
            print(f"[Removed] {name}  ({size_kb:.1f} KB)")
            removed += 1
        else:
            print(f"[Will Remove] {name}  ({size_kb:.1f} KB)")
            removed += 1

    print(f"\n总计: 保留 {kept} 个，{'删除' if args.apply else '待删除'} {removed} 个")
    if not args.apply and removed > 0:
        print("\n这是预览模式。确认无误后，运行：")
        print(f"  python -m scripts.cleanup_contact_memory --apply")


if __name__ == "__main__":
    main()
