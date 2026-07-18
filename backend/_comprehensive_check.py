"""全面检查开发模式和发行模式的数据迁移状态"""
import sqlite3
import os
import json

def check_db(db_path, label):
    """检查单个 DB 的数据完整性"""
    result = {"label": label, "path": db_path, "exists": os.path.exists(db_path)}
    if not os.path.exists(db_path):
        return result
    
    result["size"] = os.path.getsize(db_path)
    conn = sqlite3.connect(db_path)
    
    # 核心表计数
    tables = {}
    for t in ['providers', 'provider_credentials', 'agents', 'conversations',
              'platform_instances', 'scheduled_tasks', 'config_items',
              'groups', 'usage_records', 'workflow_sessions']:
        try:
            tables[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except:
            tables[t] = -1
    result["tables"] = tables
    
    # providers 详情
    try:
        rows = conn.execute("SELECT id, name, vendor, is_default, enabled FROM providers ORDER BY sort_order").fetchall()
        result["providers"] = [{"id": r[0], "name": r[1], "vendor": r[2], "default": bool(r[3]), "enabled": bool(r[4])} for r in rows]
    except:
        result["providers"] = []
    
    # agents 详情
    try:
        rows = conn.execute("SELECT id, name FROM agents").fetchall()
        result["agents"] = [{"id": r[0], "name": r[1]} for r in rows]
    except:
        result["agents"] = []
    
    # conversations 详情
    try:
        visible = conn.execute("SELECT COUNT(*) FROM conversations WHERE is_hidden=0").fetchone()[0]
        hidden = conn.execute("SELECT COUNT(*) FROM conversations WHERE is_hidden=1").fetchone()[0]
        result["conversations_detail"] = {"visible": visible, "hidden": hidden, "total": visible + hidden}
    except:
        result["conversations_detail"] = {}
    
    # config_items 中的关键配置
    try:
        rows = conn.execute("SELECT key, value FROM config_items").fetchall()
        important_keys = ['main_agent.config', 'model_config', 'llm.fallback_chain', 'llm.default_provider']
        result["important_configs"] = {r[0]: r[1][:80] for r in rows if r[0] in important_keys}
    except:
        result["important_configs"] = {}
    
    conn.close()
    return result

def check_memory_dir(dir_path, label):
    """检查 memory 目录"""
    result = {"label": label, "path": dir_path, "exists": os.path.exists(dir_path)}
    if not os.path.exists(dir_path):
        return result
    
    files = []
    for root, dirs, fnames in os.walk(dir_path):
        for f in fnames:
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, dir_path)
            files.append({"path": rel, "size": os.path.getsize(fp)})
    result["files"] = files
    result["file_count"] = len(files)
    return result

def check_store_dir(dir_path, label):
    """检查 store 目录（JSON 原始数据）"""
    result = {"label": label, "path": dir_path, "exists": os.path.exists(dir_path)}
    if not os.path.exists(dir_path):
        return result
    
    files = []
    for f in os.listdir(dir_path):
        fp = os.path.join(dir_path, f)
        if os.path.isfile(fp):
            files.append({"name": f, "size": os.path.getsize(fp)})
    result["files"] = files
    return result

def print_report(result):
    """打印检查结果"""
    print(f"\n{'='*70}")
    print(f"  {result['label']}")
    print(f"  路径: {result['path']}")
    print(f"{'='*70}")
    
    if not result.get("exists"):
        print("  ❌ 不存在!")
        return
    
    if "size" in result:
        print(f"  大小: {result['size']} bytes")
    
    if "tables" in result:
        print(f"\n  --- 数据库表 ---")
        for t, c in result["tables"].items():
            status = "✅" if c > 0 else ("⚠️" if c == 0 else "❌")
            print(f"    {status} {t}: {c}")
    
    if "providers" in result:
        print(f"\n  --- Providers ({len(result['providers'])}) ---")
        for p in result["providers"]:
            default_mark = " [默认]" if p["default"] else ""
            enabled_mark = "✅" if p["enabled"] else "❌"
            print(f"    {enabled_mark} {p['name']} ({p['vendor']}){default_mark}")
    
    if "agents" in result:
        print(f"\n  --- Agents ({len(result['agents'])}) ---")
        for a in result["agents"]:
            print(f"    {a['id']}: {a['name']}")
    
    if "conversations_detail" in result:
        d = result["conversations_detail"]
        if d:
            print(f"\n  --- Conversations ---")
            print(f"    可见: {d.get('visible', 0)}, 隐藏: {d.get('hidden', 0)}, 总计: {d.get('total', 0)}")
    
    if "important_configs" in result:
        print(f"\n  --- 关键配置 ---")
        for k, v in result["important_configs"].items():
            print(f"    {k}: {v[:60]}...")
    
    if "file_count" in result:
        print(f"\n  --- Memory 文件 ({result['file_count']}) ---")
        for f in result.get("files", [])[:10]:
            print(f"    {f['path']} ({f['size']}B)")
        if result["file_count"] > 10:
            print(f"    ... 还有 {result['file_count'] - 10} 个文件")
    
    if "files" in result and "file_count" not in result:
        print(f"\n  --- Store 文件 ---")
        for f in result["files"]:
            print(f"    {f['name']} ({f['size']}B)")


# ============================================================
# 检查开发模式数据: backend/data/
# ============================================================
dev_base = r'D:\Projects\Project\LuomiNest\backend\data'

print("\n" + "🔧"*35)
print("  开发模式数据检查 (backend/data/)")
print("🔧"*35)

dev_db = check_db(os.path.join(dev_base, 'luominest.db'), '开发模式 DB')
print_report(dev_db)

dev_memory = check_memory_dir(os.path.join(dev_base, 'memory'), '开发模式 Memory')
print_report(dev_memory)

dev_store = check_store_dir(os.path.join(dev_base, 'store'), '开发模式 Store (JSON)')
print_report(dev_store)

# ============================================================
# 检查发行模式数据: %APPDATA%/luominest-desktop/Data/backend/
# ============================================================
prod_base = os.path.expandvars(r'%APPDATA%\luominest-desktop\Data\backend')

print("\n" + "📦"*35)
print("  发行模式数据检查 (%APPDATA%/luominest-desktop/Data/backend/)")
print("📦"*35)

prod_db = check_db(os.path.join(prod_base, 'luominest.db'), '发行模式 DB')
print_report(prod_db)

prod_memory = check_memory_dir(os.path.join(prod_base, 'memory'), '发行模式 Memory')
print_report(prod_memory)

prod_store = check_store_dir(os.path.join(prod_base, 'store'), '发行模式 Store (JSON)')
print_report(prod_store)

# ============================================================
# 检查 frontend/out/Data/backend/ (可能的 dev-build 位置)
# ============================================================
out_base = r'D:\Projects\Project\LuomiNest\frontend\out\Data\backend'

print("\n" + "🔨"*35)
print("  Dev-Build 数据检查 (frontend/out/Data/backend/)")
print("🔨"*35)

out_db = check_db(os.path.join(out_base, 'luominest.db'), 'Dev-Build DB')
print_report(out_db)

# ============================================================
# 对比总结
# ============================================================
print("\n" + "="*70)
print("  📊 数据迁移对比总结")
print("="*70)

dev_tables = dev_db.get("tables", {})
prod_tables = prod_db.get("tables", {})
out_tables = out_db.get("tables", {})

print(f"\n  {'表名':<25} {'开发模式':>10} {'发行模式':>10} {'Dev-Build':>10}")
print(f"  {'-'*55}")
for t in ['providers', 'provider_credentials', 'agents', 'conversations',
           'platform_instances', 'scheduled_tasks', 'config_items']:
    d = dev_tables.get(t, 'N/A')
    p = prod_tables.get(t, 'N/A')
    o = out_tables.get(t, 'N/A')
    match = "✅" if d == p and d != 'N/A' and d > 0 else "❌"
    print(f"  {match} {t:<23} {d:>10} {p:>10} {o:>10}")

# 检查数据隔离
print(f"\n  --- 数据隔离检查 ---")
dev_path = dev_db.get("path", "")
prod_path = prod_db.get("path", "")
same = os.path.normpath(dev_path) == os.path.normpath(prod_path) if dev_path and prod_path else False
print(f"    开发/发行 DB 是否相同: {'⚠️ 是 (未隔离!)' if same else '✅ 否 (已隔离)'}")
print(f"    开发 DB: {dev_path}")
print(f"    发行 DB: {prod_path}")
