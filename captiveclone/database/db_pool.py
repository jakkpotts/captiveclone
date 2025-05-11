"""
Database connection pooling and query optimization for CaptiveClone.

This module provides connection pooling and query optimization to improve
database performance and reliability.
"""

import logging
import functools
import time
from typing import Optional, Dict, Any, Callable, TypeVar, cast
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session, Session, Query
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import Engine

from captiveclone.utils.config import Config
from captiveclone.database.models import Base

logger = logging.getLogger(__name__)

# Type variable for function return types
T = TypeVar('T')

# Query cache
_query_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl: Dict[str, float] = {}
DEFAULT_CACHE_TTL = 60  # Default cache TTL in seconds

# Connection pools
_engine_pools: Dict[str, Engine] = {}
_session_factories: Dict[str, Callable[[], Session]] = {}


def init_db_pool(config: Config, db_uri: Optional[str] = None) -> Engine:
    """
    Initialize the database connection pool.
    
    Args:
        config: Application configuration
        db_uri: Database URI (optional, defaults to config value)
        
    Returns:
        SQLAlchemy engine with connection pooling
    """
    db_uri = db_uri or f"sqlite:///{config.get('database.path', 'captiveclone.db')}"
    
    if db_uri in _engine_pools:
        logger.debug(f"Returning existing engine for {db_uri}")
        return _engine_pools[db_uri]
    
    # Connection pool settings
    pool_size = config.get("database.pool.size", 5)
    max_overflow = config.get("database.pool.max_overflow", 10)
    pool_timeout = config.get("database.pool.timeout", 30)
    pool_recycle = config.get("database.pool.recycle", 3600)  # Recycle connections after 1 hour
    
    # Create engine with connection pooling
    engine = create_engine(
        db_uri,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,  # Test connections before using them
        echo=config.get("database.echo", False)
    )
    
    # Set up event handlers for connection lifecycle
    @event.listens_for(engine, "connect")
    def connect(dbapi_connection, connection_record):
        logger.debug("New database connection established")
        
        # Set pragma for SQLite
        if db_uri.startswith('sqlite:'):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=30000000000")
            cursor.close()
    
    @event.listens_for(engine, "checkout")
    def checkout(dbapi_connection, connection_record, connection_proxy):
        logger.debug("Database connection checked out from pool")
    
    @event.listens_for(engine, "checkin")
    def checkin(dbapi_connection, connection_record):
        logger.debug("Database connection returned to pool")
    
    # Create all tables if they don't exist
    Base.metadata.create_all(engine)
    
    # Store the engine in the pool registry
    _engine_pools[db_uri] = engine
    
    # Create a scoped session factory
    session_factory = scoped_session(sessionmaker(bind=engine))
    _session_factories[db_uri] = session_factory
    
    logger.info(f"Initialized database connection pool for {db_uri}")
    return engine


@contextmanager
def get_db_session(db_uri: Optional[str] = None) -> Session:
    """
    Get a database session from the pool.
    
    Args:
        db_uri: Database URI to get session for
        
    Yields:
        SQLAlchemy session
    """
    if not db_uri and not _session_factories:
        raise ValueError("Database pool not initialized. Call init_db_pool first.")
    
    # Get the session factory for the URI or use the first available one
    session_factory = None
    if db_uri and db_uri in _session_factories:
        session_factory = _session_factories[db_uri]
    elif not db_uri and _session_factories:
        session_factory = next(iter(_session_factories.values()))
    
    if not session_factory:
        raise ValueError(f"No session factory found for URI: {db_uri}")
    
    # Create a new session
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error during database session: {str(e)}")
        raise
    finally:
        session.close()


def cached_query(ttl: Optional[float] = None) -> Callable:
    """
    Decorator for caching query results.
    
    Args:
        ttl: Time-to-live for cache entry in seconds (None = default TTL)
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check if result is in cache and not expired
            now = time.time()
            if key in _query_cache and (key not in _cache_ttl or _cache_ttl[key] > now):
                logger.debug(f"Cache hit for query: {key}")
                return cast(T, _query_cache[key]['result'])
            
            # Execute the query
            result = func(*args, **kwargs)
            
            # Cache the result
            _query_cache[key] = {'result': result}
            _cache_ttl[key] = now + (ttl or DEFAULT_CACHE_TTL)
            
            logger.debug(f"Cache miss for query: {key}, caching result")
            return result
        
        return wrapper
    
    return decorator


def clear_query_cache() -> None:
    """Clear the query cache."""
    _query_cache.clear()
    _cache_ttl.clear()
    logger.debug("Query cache cleared")


def optimize_query(query: Query) -> Query:
    """
    Apply optimization to a SQLAlchemy query.
    
    Args:
        query: SQLAlchemy query object
        
    Returns:
        Optimized query object
    """
    # Add query hints based on the query type
    # This is just a basic example, more advanced optimizations can be added
    
    # Check if select_from is being used
    if hasattr(query, '_select_from_entity') and query._select_from_entity is not None:
        # Add optimization hints for JOINs
        query = query.execution_options(join_eager_strategy='select')
    
    # Add execution options for better performance
    query = query.execution_options(
        compiled_cache={},  # Use compiled query cache
        yield_per=100       # Fetch results in batches of 100
    )
    
    return query


def execute_with_retry(
    session: Session,
    operation: Callable[[], T],
    max_retries: int = 3,
    retry_delay: float = 0.5
) -> T:
    """
    Execute a database operation with automatic retry on failure.
    
    Args:
        session: SQLAlchemy session
        operation: Function to execute against the database
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Result of the operation
        
    Raises:
        Exception: If the operation fails after all retries
    """
    retries = 0
    last_error = None
    
    while retries <= max_retries:
        try:
            if retries > 0:
                # If we're retrying, make sure the connection is still good
                session.rollback()
                session.execute("SELECT 1")  # Simple check query
            
            # Execute the operation
            result = operation()
            
            # If we get here, the operation succeeded
            if retries > 0:
                logger.debug(f"Operation succeeded after {retries} retries")
            
            return result
            
        except Exception as e:
            # Roll back the session
            try:
                session.rollback()
            except Exception:
                pass
            
            last_error = e
            retries += 1
            
            if retries <= max_retries:
                logger.warning(f"Database operation failed, retrying ({retries}/{max_retries}): {str(e)}")
                time.sleep(retry_delay * retries)  # Exponential backoff
            else:
                logger.error(f"Database operation failed after {max_retries} retries: {str(e)}")
    
    # If we get here, all retries failed
    if last_error:
        raise last_error
    else:
        raise Exception("Database operation failed with unknown error")


def shutdown_pool() -> None:
    """Shut down all database connection pools."""
    for uri, engine in _engine_pools.items():
        logger.info(f"Shutting down database connection pool for {uri}")
        engine.dispose()
    
    _engine_pools.clear()
    _session_factories.clear()
    logger.info("All database connection pools have been shut down") 