import pytest

from app.database import Store, metadata
from app.engine import TradingEngine


@pytest.fixture
def engine(tmp_path):
    store = Store("sqlite:///" + str(tmp_path / "engine.db"))
    metadata.create_all(store.engine)
    instance = TradingEngine(store)
    yield instance
    store.engine.dispose()
