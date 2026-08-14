"""Neo4j 드라이버 팩토리."""

from neo4j import AsyncGraphDatabase

from app.core.config import Settings


def create_neo4j_driver(settings: Settings):
    """비동기 드라이버 생성 (lifespan/worker에서 열고 닫는다)."""
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
