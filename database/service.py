"""
Database service layer for Key Translation Bot
Provides high-level database operations
"""

import json
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, date

from .connection import db_manager
from .models import (
    GuildConfig, TranslationConfig, TTSConfig, MusicConfig,
    MessageMapping, UsageStats, AdminPermission, SupportedLanguage,
    FeatureType, PermissionLevel, DatabaseError, ConfigurationError
)


class DatabaseService:
    """High-level database service for bot operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db = db_manager
    
    # Guild Configuration Methods
    
    async def get_guild_config(self, guild_id: int) -> Optional[GuildConfig]:
        """Get guild configuration"""
        try:
            row = await self.db.fetch_one(
                "SELECT * FROM guild_configs WHERE guild_id = $1",
                guild_id
            )
            
            if row:
                # Parse JSON fields if they are strings
                features = row['features']
                if isinstance(features, str):
                    features = json.loads(features)
                
                channels = row['channels']
                if isinstance(channels, str):
                    channels = json.loads(channels)
                
                settings = row['settings']
                if isinstance(settings, str):
                    settings = json.loads(settings)
                
                return GuildConfig(
                    guild_id=row['guild_id'],
                    guild_name=row['guild_name'],
                    api_key=row['api_key'],
                    features=features,
                    channels=channels,
                    settings=settings,
                    is_initialized=row['is_initialized'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get guild config for {guild_id}: {e}")
            raise DatabaseError(f"Failed to get guild config: {e}")
    
    async def create_guild_config(self, guild_config: GuildConfig) -> GuildConfig:
        """Create a new guild configuration"""
        try:
            query = """
                INSERT INTO guild_configs 
                (guild_id, guild_name, api_key, features, channels, settings, is_initialized)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
            """
            
            row = await self.db.fetch_one(
                query,
                guild_config.guild_id,
                guild_config.guild_name,
                guild_config.api_key,
                json.dumps(guild_config.features),
                json.dumps(guild_config.channels),
                json.dumps(guild_config.settings),
                guild_config.is_initialized
            )
            
            self.logger.info(f"✅ Created guild config for {guild_config.guild_id}")
            return await self.get_guild_config(guild_config.guild_id)
            
        except Exception as e:
            self.logger.error(f"Failed to create guild config for {guild_config.guild_id}: {e}")
            raise DatabaseError(f"Failed to create guild config: {e}")
    
    async def update_guild_config(self, guild_config: GuildConfig) -> GuildConfig:
        """Update guild configuration"""
        try:
            query = """
                UPDATE guild_configs 
                SET guild_name = $2, api_key = $3, features = $4, 
                    channels = $5, settings = $6, is_initialized = $7
                WHERE guild_id = $1
                RETURNING *
            """
            
            await self.db.execute(
                query,
                guild_config.guild_id,
                guild_config.guild_name,
                guild_config.api_key,
                json.dumps(guild_config.features),
                json.dumps(guild_config.channels),
                json.dumps(guild_config.settings),
                guild_config.is_initialized
            )
            
            self.logger.info(f"✅ Updated guild config for {guild_config.guild_id}")
            return await self.get_guild_config(guild_config.guild_id)
            
        except Exception as e:
            self.logger.error(f"Failed to update guild config for {guild_config.guild_id}: {e}")
            raise DatabaseError(f"Failed to update guild config: {e}")
    
    async def delete_guild_config(self, guild_id: int) -> bool:
        """Delete guild configuration and all related data"""
        try:
            # This will cascade delete all related data due to foreign key constraints
            result = await self.db.execute(
                "DELETE FROM guild_configs WHERE guild_id = $1",
                guild_id
            )
            
            self.logger.info(f"🗑️ Deleted guild config for {guild_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete guild config for {guild_id}: {e}")
            raise DatabaseError(f"Failed to delete guild config: {e}")
    
    # Translation Configuration Methods
    
    async def get_translation_configs(self, guild_id: int) -> List[TranslationConfig]:
        """Get all translation configurations for a guild"""
        try:
            rows = await self.db.fetch_all(
                "SELECT * FROM translation_configs WHERE guild_id = $1 ORDER BY language_code",
                guild_id
            )
            
            return [
                TranslationConfig(
                    id=row['id'],
                    guild_id=row['guild_id'],
                    language_code=row['language_code'],
                    language_name=row['language_name'],
                    channel_id=row['channel_id'],
                    is_active=row['is_active'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to get translation configs for {guild_id}: {e}")
            raise DatabaseError(f"Failed to get translation configs: {e}")
    
    async def create_translation_config(self, config: TranslationConfig) -> TranslationConfig:
        """Create a translation configuration"""
        try:
            query = """
                INSERT INTO translation_configs 
                (guild_id, language_code, language_name, channel_id, is_active)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """
            
            row = await self.db.fetch_one(
                query,
                config.guild_id,
                config.language_code,
                config.language_name,
                config.channel_id,
                config.is_active
            )
            
            return TranslationConfig(**row)
            
        except Exception as e:
            self.logger.error(f"Failed to create translation config: {e}")
            raise DatabaseError(f"Failed to create translation config: {e}")
    
    # Message Mapping Methods
    
    async def create_message_mapping(self, mapping: MessageMapping) -> MessageMapping:
        """Create a message mapping"""
        try:
            query = """
                INSERT INTO message_mappings 
                (guild_id, original_message_id, original_channel_id, translated_messages, original_content)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """
            
            row = await self.db.fetch_one(
                query,
                mapping.guild_id,
                mapping.original_message_id,
                mapping.original_channel_id,
                json.dumps(mapping.translated_messages),
                mapping.original_content
            )
            
            return MessageMapping(**{**row, 'translated_messages': json.loads(row['translated_messages'])})
            
        except Exception as e:
            self.logger.error(f"Failed to create message mapping: {e}")
            raise DatabaseError(f"Failed to create message mapping: {e}")
    
    async def get_message_mapping(self, guild_id: int, original_message_id: int) -> Optional[MessageMapping]:
        """Get message mapping"""
        try:
            row = await self.db.fetch_one(
                "SELECT * FROM message_mappings WHERE guild_id = $1 AND original_message_id = $2",
                guild_id, original_message_id
            )
            
            if row:
                return MessageMapping(
                    id=row['id'],
                    guild_id=row['guild_id'],
                    original_message_id=row['original_message_id'],
                    original_channel_id=row['original_channel_id'],
                    translated_messages=row['translated_messages'],
                    original_content=row['original_content'],
                    created_at=row['created_at']
                )
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get message mapping: {e}")
            raise DatabaseError(f"Failed to get message mapping: {e}")
    
    async def update_message_mapping(self, guild_id: int, original_message_id: int, 
                                   translated_messages: Dict[str, int], 
                                   original_content: str) -> bool:
        """Update message mapping"""
        try:
            query = """
                UPDATE message_mappings 
                SET translated_messages = $3, original_content = $4
                WHERE guild_id = $1 AND original_message_id = $2
            """
            
            await self.db.execute(
                query,
                guild_id,
                original_message_id,
                json.dumps(translated_messages),
                original_content
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update message mapping: {e}")
            raise DatabaseError(f"Failed to update message mapping: {e}")
    
    async def delete_message_mapping(self, guild_id: int, original_message_id: int) -> bool:
        """Delete message mapping"""
        try:
            await self.db.execute(
                "DELETE FROM message_mappings WHERE guild_id = $1 AND original_message_id = $2",
                guild_id, original_message_id
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete message mapping: {e}")
            raise DatabaseError(f"Failed to delete message mapping: {e}")
    
    # Utility Methods
    
    async def get_supported_languages(self) -> List[SupportedLanguage]:
        """Get all supported languages"""
        try:
            rows = await self.db.fetch_all(
                "SELECT * FROM supported_languages WHERE is_active = true ORDER BY name_en"
            )
            
            return [
                SupportedLanguage(
                    code=row['code'],
                    name_en=row['name_en'],
                    name_native=row['name_native'],
                    is_active=row['is_active']
                )
                for row in rows
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to get supported languages: {e}")
            raise DatabaseError(f"Failed to get supported languages: {e}")
    
    async def guild_exists(self, guild_id: int) -> bool:
        """Check if guild exists in database"""
        try:
            count = await self.db.fetch_val(
                "SELECT COUNT(*) FROM guild_configs WHERE guild_id = $1",
                guild_id
            )
            return count > 0
            
        except Exception as e:
            self.logger.error(f"Failed to check if guild exists: {e}")
            return False
    
    async def is_guild_initialized(self, guild_id: int) -> bool:
        """Check if guild is initialized"""
        try:
            result = await self.db.fetch_val(
                "SELECT is_initialized FROM guild_configs WHERE guild_id = $1",
                guild_id
            )
            return result is True
            
        except Exception as e:
            self.logger.error(f"Failed to check if guild is initialized: {e}")
            return False
    
    async def get_guild_stats(self) -> Dict[str, Any]:
        """Get overall guild statistics"""
        try:
            return await self.db.get_database_stats()
        except Exception as e:
            self.logger.error(f"Failed to get guild stats: {e}")
            return {}


# Global database service instance
db_service = DatabaseService()