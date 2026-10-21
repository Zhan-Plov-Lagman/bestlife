from alembic import context
from app.database import db_engine, metadata

if context.is_offline_mode():
    import os

    context.configure(
        url=os.getenv("DATABASE_URL", "sqlite:///./trading.db"),
        target_metadata=metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with db_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
