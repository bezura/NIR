from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from nir_tagging_service.config import Settings, get_settings


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url
    if database_url.startswith("sqlite://"):
        return database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return database_url


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    current_settings = settings or get_settings()
    engine_kwargs = {
        "pool_pre_ping": True,
    }
    database_url = _normalize_database_url(current_settings.database_url)

    if database_url.startswith("sqlite+aiosqlite://"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if database_url == "sqlite+aiosqlite:///:memory:":
            engine_kwargs["poolclass"] = StaticPool

    return create_async_engine(database_url, **engine_kwargs)


def create_session_factory(
    settings: Settings | None = None,
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    engine = engine or create_engine(settings)
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
