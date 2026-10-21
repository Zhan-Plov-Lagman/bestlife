from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import db_engine, metadata


def test_migration_upgrade_downgrade(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "migration.db"))
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    db = db_engine()
    assert set(metadata.tables) <= set(inspect(db).get_table_names())
    db.dispose()
    command.downgrade(cfg, "base")
    db = db_engine()
    assert inspect(db).get_table_names() == ["alembic_version"]
    db.dispose()
    command.upgrade(cfg, "head")
