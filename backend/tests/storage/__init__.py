"""Phase 7 存储层测试包。

测试文件（独立运行，无需 pytest）：
- test_repositories.py      — Repository CRUD + AES 加密 + 原子增
- test_migration.py         — JSON→SQLite 迁移幂等性 + 空库 + 有数据迁移
- test_facade_compat.py     — Facade 单例方法签名兼容 + CRUD round-trip
- test_adapter_lazy_load.py — adapter P0 懒加载 + model_config DB 解耦

运行方式：python -m tests.storage.test_<name>  或  python tests/storage/test_<name>.py
"""
