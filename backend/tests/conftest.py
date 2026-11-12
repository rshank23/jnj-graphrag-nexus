"""Shared test isolation: in-memory ops DB and no hosted LLM calls."""
import pytest

from app.core.db import OpsDB, set_db
from app.llm.router import ModelRouter, set_router


@pytest.fixture(autouse=True)
def _isolated_ops(tmp_path):
    db = OpsDB(tmp_path / "ops.db")
    set_db(db)
    set_router(ModelRouter(providers=[]))
    yield db
    set_router(None)
    db.close()
