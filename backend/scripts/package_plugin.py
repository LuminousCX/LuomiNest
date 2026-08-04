"""CxPlugin 打包脚本 — 将单个插件目录打包为符合规范的 zip。

依据 docs/development/plugin-system.md 规范：
- zip 解压后必须为平铺结构（manifest.json 与 main.py 直接在根目录）
- 不可有多余嵌套目录
- 必须包含 manifest.json
- 入口文件（main.py 或 manifest.entry 指定的文件）必须存在

用法:
    # 在 backend/ 目录下执行
    python -m scripts.package_plugin cxp-pdf-reader               # 打包 plugins/cxp-pdf-reader
    python -m scripts.package_plugin weather-query --output dist   # 自定义输出目录
    python -m scripts.package_plugin cxp-pdf-reader --version 1.0.0 --tag  # 加版本号到文件名
    python -m scripts.package_plugin --path /abs/path/to/plugin    # 通过绝对路径打包
    python -m scripts.package_plugin cxp-pdf-reader --dry-run      # 仅预览将打包的文件

输出:
    默认: backend/dist/{plugin_id}-v{version}.zip
    --tag 模式: backend/dist/{plugin_id}-v{version}.zip（与默认相同，便于 GitHub Release 引用）
    --output 指定目录时仍以 {plugin_id}-v{version}.zip 命名

安全:
    - 不打包 __pycache__/、.pyc、.DS_Store、*.tmp、data/ 子目录（运行时数据）
    - 不打包 .git/ 子目录
    - 强制包含 manifest.json 与入口文件
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Iterable

# backend/ 根目录（脚本位于 backend/scripts/package_plugin.py）
BACKEND_ROOT = Path(__file__).resolve().parent.parent
# 默认插件根目录（dev 模式）
DEFAULT_PLUGIN_ROOT = BACKEND_ROOT / "plugins"

# 必须包含的清单文件
MANIFEST_FILENAME = "manifest.json"

# 默认排除规则（路径前缀匹配，相对插件目录）
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "data",  # 运行时数据目录，不应打包
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

EXCLUDE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".tmp",
    ".bak",
    ".swp",
    ".log",
}

EXCLUDE_FILENAMES = {
    ".DS_Store",
    "Thumbs.db",
    ".gitignore",
    ".gitkeep",
}


def resolve_plugin_dir(plugin_id_or_path: str, plugin_root: Path) -> Path:
    """根据 plugin_id 或绝对/相对路径解析插件目录。

    - 若传入路径存在（绝对或相对），直接使用
    - 否则视为 plugin_id，从 plugin_root 下查找
    """
    candidate = Path(plugin_id_or_path)
    if candidate.is_absolute() and candidate.is_dir():
        return candidate

    # 相对路径：先尝试相对当前工作目录，再尝试相对 plugin_root
    if candidate.is_dir():
        return candidate.resolve()

    # 视为 plugin_id
    as_id = plugin_root / plugin_id_or_path
    if as_id.is_dir():
        return as_id.resolve()
    raise FileNotFoundError(
        f"插件目录不存在: {plugin_id_or_path}（尝试在 {plugin_root} 下查找也失败）"
    )


def load_manifest(plugin_dir: Path) -> dict:
    """读取并校验 manifest.json。"""
    manifest_path = plugin_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"插件目录缺少 {MANIFEST_FILENAME}: {plugin_dir}")
    try:
        with manifest_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"manifest.json 解析失败: {manifest_path} - {e}") from e


def validate_manifest(manifest: dict, plugin_dir: Path) -> tuple[str, str]:
    """校验 manifest 必填字段，返回 (plugin_id, version)。

    同时检查入口文件是否存在。
    """
    plugin_id = str(manifest.get("id", "")).strip()
    if not plugin_id:
        raise ValueError("manifest.json 缺少必填字段: id")
    if not manifest.get("name"):
        raise ValueError("manifest.json 缺少必填字段: name")
    version = str(manifest.get("version", "")).strip()
    if not version:
        raise ValueError("manifest.json 缺少必填字段: version")

    entry_field = str(manifest.get("entry", "main")).strip()
    entry_file = plugin_dir / f"{entry_field}.py"
    if not entry_file.is_file():
        raise FileNotFoundError(
            f"入口文件不存在: {entry_file}（manifest.entry={entry_field!r}）"
        )
    return plugin_id, version


def iter_pack_files(plugin_dir: Path) -> Iterable[Path]:
    """遍历插件目录，返回应打包的文件列表。

    应用排除规则：__pycache__/data 子目录、.pyc/.tmp 等后缀、.DS_Store 等文件名。
    """
    for path in plugin_dir.rglob("*"):
        if not path.is_file():
            continue

        rel = path.relative_to(plugin_dir)
        parts = rel.parts

        # 排除特定子目录（任一段匹配即可）
        if any(part in EXCLUDE_DIRS for part in parts):
            continue

        # 排除特定后缀
        if path.suffix in EXCLUDE_FILE_SUFFIXES:
            continue

        # 排除特定文件名
        if path.name in EXCLUDE_FILENAMES:
            continue

        yield path


def build_zip(
    plugin_dir: Path,
    output_path: Path,
    dry_run: bool = False,
) -> tuple[Path, list[Path]]:
    """将插件目录打包为 zip（平铺结构）。

    Args:
        plugin_dir: 插件源目录
        output_path: 输出 zip 路径
        dry_run: True 时仅返回将要打包的文件列表，不写入 zip

    Returns:
        (output_path, packed_files)
    """
    packed_files: list[Path] = []
    for src in iter_pack_files(plugin_dir):
        packed_files.append(src)

    if dry_run:
        return output_path, packed_files

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in packed_files:
            arcname = src.relative_to(plugin_dir).as_posix()
            zf.write(src, arcname)

    return output_path, packed_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="将单个 CxPlugin 插件目录打包为符合规范的 zip（平铺结构）"
    )
    parser.add_argument(
        "plugin",
        help="插件 ID（如 cxp-pdf-reader）或插件目录的绝对/相对路径",
    )
    parser.add_argument(
        "--plugin-root",
        type=str,
        default=str(DEFAULT_PLUGIN_ROOT),
        help=f"插件根目录（默认: {DEFAULT_PLUGIN_ROOT}）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="dist",
        help="输出目录（默认: backend/dist/）；最终文件名为 {plugin_id}-v{version}.zip",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="以 GitHub Release tag 风格命名文件（{plugin_id}-v{version}.zip，与默认相同）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览将打包的文件列表，不写入 zip",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="覆盖输出文件名中的版本号（不改 manifest）",
    )
    args = parser.parse_args()

    plugin_root = Path(args.plugin_root).resolve()
    if not plugin_root.is_dir():
        print(f"[Error] 插件根目录不存在: {plugin_root}", file=sys.stderr)
        return 1

    try:
        plugin_dir = resolve_plugin_dir(args.plugin, plugin_root)
    except FileNotFoundError as e:
        print(f"[Error] {e}", file=sys.stderr)
        return 1

    print(f"[Info] 插件目录: {plugin_dir}")

    try:
        manifest = load_manifest(plugin_dir)
        plugin_id, manifest_version = validate_manifest(manifest, plugin_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"[Error] {e}", file=sys.stderr)
        return 1

    version = args.version or manifest_version
    print(f"[Info] 插件 id={plugin_id} version={version}（manifest v{manifest_version}）")

    # 输出路径
    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = BACKEND_ROOT / output_dir
    output_dir = output_dir.resolve()

    zip_name = f"{plugin_id}-v{version}.zip"
    output_path = output_dir / zip_name

    try:
        result_path, packed_files = build_zip(plugin_dir, output_path, dry_run=args.dry_run)
    except Exception as e:
        print(f"[Error] 打包失败: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"[Dry-run] 将打包 {len(packed_files)} 个文件到 {output_path}:")
        for src in packed_files:
            arcname = src.relative_to(plugin_dir).as_posix()
            print(f"  - {arcname}")
        return 0

    print(f"[OK] 打包完成: {result_path}")
    print(f"[Info] 共 {len(packed_files)} 个文件，{result_path.stat().st_size} bytes")
    print()
    print("包含的文件:")
    for src in packed_files:
        arcname = src.relative_to(plugin_dir).as_posix()
        print(f"  - {arcname}")

    print()
    print("下一步:")
    print(f"  1. 创建 GitHub Release: gh release create v{version} --title v{version} {result_path}")
    print(f"  2. 提交 PR 到 LuomiNest-cxp-registry/index.json 添加条目")
    return 0


if __name__ == "__main__":
    sys.exit(main())
