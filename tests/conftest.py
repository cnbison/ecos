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
