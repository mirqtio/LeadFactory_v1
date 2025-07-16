import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import base first
from database.base import Base  # noqa: E402
from database.governance_models import *  # noqa: E402, F403

# Import all models to ensure they're registered with Base.metadata
# This is critical for alembic autogenerate to work correctly
from database.models import *  # noqa: E402, F403

# Import domain-specific models
try:
    from d1_targeting.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d2_sourcing.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d3_assessment.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d4_enrichment.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d5_scoring.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d6_reports.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d6_reports.lineage.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d7_storefront.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d8_personalization.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d9_delivery.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d10_analytics.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from d11_orchestration.models import *  # noqa: E402, F403
except ImportError:
    pass

# Import feature-specific models
try:
    from batch_runner.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from lead_explorer.models import *  # noqa: E402, F403
except ImportError:
    pass

try:
    from account_management.models import *  # noqa: E402, F403
except ImportError:
    pass

# governance models are in database.governance_models, imported above

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    import os

    # Get URL from environment or config
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    import os

    configuration = config.get_section(config.config_ini_section, {})

    # Override with DATABASE_URL from environment if available
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        configuration["sqlalchemy.url"] = database_url

    # Add SQLite specific connection args
    url = configuration.get("sqlalchemy.url", "")
    if url.startswith("sqlite"):
        configuration["sqlalchemy.connect_args"] = {"check_same_thread": False}

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
