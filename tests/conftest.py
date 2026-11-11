from __future__ import annotations

from pathlib import Path

import pytest

from pergunteoee.data.generate import generate_database


@pytest.fixture(scope="session")
def synthetic_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("dados") / "pergunteoee.duckdb"
    generate_database(path, seed=42)
    return path
