import logging
from neo4j import GraphDatabase, exceptions
from config import settings

logger = logging.getLogger("chainwatch.neo4j")
_driver = None

def get_driver():
    global _driver
    if _driver is None:
        try:
            _driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.auth_user, settings.neo4j_password),
            )
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {e}")
            raise e
    return _driver

def close_driver():
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        except Exception as e:
            logger.warning(f"Error closing Neo4j driver: {e}")
        finally:
            _driver = None

def run_query(query: str, parameters: dict = None, write: bool = False):
    """
    Single entrypoint for all Cypher execution.
    write=True routes through execute_write for transactional safety on MERGE ops.
    """
    driver = get_driver()
    parameters = parameters or {}
    session_kwargs = {}
    if settings.neo4j_database:
        session_kwargs["database"] = settings.neo4j_database

    try:
        with driver.session(**session_kwargs) as session:
            if write:
                return session.execute_write(lambda tx: [record.data() for record in tx.run(query, parameters)])
            return session.execute_read(lambda tx: [record.data() for record in tx.run(query, parameters)])
    except exceptions.DriverError as err:
        logger.error(f"Neo4j Execution Error: {err}")
        raise err
