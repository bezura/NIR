from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from nir_tagging_service.config import Settings
from nir_tagging_service.db.session import create_engine, create_session_factory


def test_db_session_layer_uses_async_sqlalchemy_for_sqlite(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-async.db'}")

    engine = create_engine(settings)
    session_factory = create_session_factory(settings, engine=engine)

    assert isinstance(engine, AsyncEngine)
    assert isinstance(session_factory, async_sessionmaker)
    assert session_factory.class_ is AsyncSession
