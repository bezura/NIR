from sqlalchemy import Engine, create_engine as sa_create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nir_tagging_service.config import Settings, get_settings


def create_engine(settings: Settings | None = None) -> Engine:
    current_settings = settings or get_settings()
    engine_kwargs = {
        "future": True,
        "pool_pre_ping": True,
    }

    if current_settings.database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if current_settings.database_url == "sqlite:///:memory:":
            engine_kwargs["poolclass"] = StaticPool

    return sa_create_engine(current_settings.database_url, **engine_kwargs)


def create_session_factory(
    settings: Settings | None = None,
    engine: Engine | None = None,
) -> sessionmaker:
    engine = engine or create_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
