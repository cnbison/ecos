"""pytest 共享 fixtures + sys.path 配置.

让 tests/ 下的测试能 import ecos/ web/ 等顶层包.
"""
import sys
from pathlib import Path

# 项目根目录加入 sys.path (pytest rootdir 行为)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# 共享 fixtures
import pytest


# ─── DB 隔离 (v0.98.5, 防御性自检 [8] 同类模式收口) ──────────────────────────
#
# 根因: get_db() / get_dual_agent_store() / get_lca_store() / belief._get_db()
#   等默认路径
#   硬编码 "web/ecos.db" (生产库), 本地 pytest 直写生产库 → test_* 学生
#   污染 (2026-09-07 清理过一轮, 见 CHANGELOG v0.98.5)。
# 修法: 生产代码统一支持 ECOS_DB_PATH 环境变量; 本 fixture 对**每个测试**
#   设置独立 tmp DB + 重置相关单例缓存, 双保险。
# 例外: 显式传非默认路径的调用不受影响 (如 DualAgentStore(db_path=...))。


@pytest.fixture(autouse=True)
def isolated_ecos_db(tmp_path, monkeypatch):
    """每个测试自动使用独立临时 DB, 防止污染 web/ecos.db 生产库."""
    import os

    # 尊重已有隔离: 部分 module 级 fixture (test_teacher_api 等) 自设
    # ECOS_DB_PATH 指向专用 temp DB — 非生产路径时不覆盖
    current = os.environ.get("ECOS_DB_PATH")
    if current and current != "web/ecos.db":
        yield current
        return

    tmp_db = str(tmp_path / "ecos_test.db")
    monkeypatch.setenv("ECOS_DB_PATH", tmp_db)

    # 重置持久化单例缓存 (上一测试创建的实例指向已删除的 tmp DB)
    import ecos.persistence.db as db_mod
    import ecos.persistence.dual_agent_store as store_mod
    import ecos.persistence.lca_store as lca_store_mod

    monkeypatch.setattr(db_mod, "_db_instance", None)
    monkeypatch.setattr(store_mod, "_store", None)
    monkeypatch.setattr(lca_store_mod, "_store", None)

    # web 层单例缓存 (belief / lca / dual_agent) — 容错: 模块未必被 import
    try:
        import web.api.belief as belief_mod

        monkeypatch.setattr(belief_mod, "_db", None)
        monkeypatch.setattr(belief_mod, "_web_event_log", None)
        monkeypatch.setattr(belief_mod, "_evidence_engine", None)
        belief_mod._STUDENT_STATES.clear()
    except ImportError:
        pass
    try:
        import web.api.lca as lca_mod

        monkeypatch.setattr(lca_mod, "_store", None)
        monkeypatch.setattr(lca_mod, "_engine", None)
        lca_mod._loaded_students.clear()
    except ImportError:
        pass
    try:
        import web.api.dual_agent as da_mod

        monkeypatch.setattr(da_mod, "_dual_store", None)
    except ImportError:
        pass

    yield tmp_db


@pytest.fixture(scope="session")
def project_root() -> Path:
    """项目根目录路径."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def ecos_dir() -> Path:
    """ecos/ Python 包路径."""
    return PROJECT_ROOT / "ecos"


@pytest.fixture(scope="session")
def web_dir() -> Path:
    """web/ Flask 应用路径."""
    return PROJECT_ROOT / "web"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """data/ 数据文件路径."""
    return PROJECT_ROOT / "data"


@pytest.fixture(scope="session")
def research_dir() -> Path:
    """research/ 文档路径."""
    return PROJECT_ROOT / "research"


@pytest.fixture(scope="session")
def lbc_history() -> dict:
    """黄金重放数据: lbc001/002/003 response_history.

    v0.98.5 从生产库导出到 tests/fixtures/lbc_response_history.json —
    此前回归测试直接 sqlite3.connect("web/ecos.db") 读生产库, 数据清理
    后改走 fixture 文件 (CI 可复现, 不依赖本地 DB 状态).
    """
    import json

    path = PROJECT_ROOT / "tests" / "fixtures" / "lbc_response_history.json"
    return json.loads(path.read_text(encoding="utf-8"))
