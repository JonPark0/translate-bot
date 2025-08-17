"""
PostgreSQL database connection and pool management
"""

import os
import asyncio
import logging
from typing import Optional, Any, Dict, List
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Pool, Connection

from .models import DatabaseError


class DatabaseManager:
    """Manages PostgreSQL connections and provides database operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pool: Optional[Pool] = None
        self._connection_params = self._get_connection_params()
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Get database connection parameters from environment variables"""
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'keybot'),
            'user': os.getenv('DB_USER', 'keybot'),
            'password': os.getenv('DB_PASSWORD', ''),
            'min_size': 5,
            'max_size': 20,
            'command_timeout': 30,
            'server_settings': {
                'application_name': 'key_translation_bot',
                'timezone': 'UTC'
            }
        }
    
    async def initialize(self) -> None:
        """Initialize the database connection pool"""
        try:
            self.logger.info("🔗 Initializing database connection pool...")
            
            self.pool = await asyncpg.create_pool(**self._connection_params)
            
            # Test the connection
            async with self.pool.acquire() as conn:
                await conn.execute('SELECT 1')
            
            self.logger.info("✅ Database connection pool initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize database: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")
    
    async def close(self) -> None:
        """Close the database connection pool"""
        if self.pool:
            await self.pool.close()
            self.logger.info("🔌 Database connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool"""
        if not self.pool:
            raise DatabaseError("Database pool is not initialized")
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query that doesn't return data"""
        async with self.get_connection() as conn:
            try:
                result = await conn.execute(query, *args)
                self.logger.debug(f"Executed query: {query[:100]}...")
                return result
            except Exception as e:
                self.logger.error(f"Query execution failed: {e}")
                raise DatabaseError(f"Query execution failed: {e}")
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row from the database"""
        async with self.get_connection() as conn:
            try:
                row = await conn.fetchrow(query, *args)
                if row:
                    return dict(row)
                return None
            except Exception as e:
                self.logger.error(f"Fetch one failed: {e}")
                raise DatabaseError(f"Fetch one failed: {e}")
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows from the database"""
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
            except Exception as e:
                self.logger.error(f"Fetch all failed: {e}")
                raise DatabaseError(f"Fetch all failed: {e}")
    
    async def fetch_val(self, query: str, *args) -> Any:
        """Fetch a single value from the database"""
        async with self.get_connection() as conn:
            try:
                return await conn.fetchval(query, *args)
            except Exception as e:
                self.logger.error(f"Fetch value failed: {e}")
                raise DatabaseError(f"Fetch value failed: {e}")
    
    async def execute_transaction(self, queries: List[tuple]) -> None:
        """Execute multiple queries in a transaction"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                try:
                    for query, args in queries:
                        await conn.execute(query, *args)
                    self.logger.debug(f"Transaction completed with {len(queries)} queries")
                except Exception as e:
                    self.logger.error(f"Transaction failed: {e}")
                    raise DatabaseError(f"Transaction failed: {e}")
    
    async def health_check(self) -> bool:
        """Check if the database is healthy"""
        try:
            async with self.get_connection() as conn:
                await conn.execute('SELECT 1')
            return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            queries = {
                'guilds_count': 'SELECT COUNT(*) FROM guild_configs',
                'initialized_guilds': 'SELECT COUNT(*) FROM guild_configs WHERE is_initialized = true',
                'active_translations': 'SELECT COUNT(*) FROM translation_configs WHERE is_active = true',
                'active_tts': 'SELECT COUNT(*) FROM tts_configs WHERE is_active = true',
                'active_music': 'SELECT COUNT(*) FROM music_configs WHERE is_active = true',
                'total_mappings': 'SELECT COUNT(*) FROM message_mappings',
                'database_size': "SELECT pg_size_pretty(pg_database_size(current_database()))"
            }
            
            stats = {}
            for key, query in queries.items():
                stats[key] = await self.fetch_val(query)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get database stats: {e}")
            return {}


# Global database manager instance
db_manager = DatabaseManager()