"""
Database-based message tracking for translation synchronization
Replaces the JSON file-based message tracker
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from database.service import db_service
from database.models import MessageMapping


@dataclass
class MessageMappingData:
    """Data class for message mapping information"""
    translated_messages: Dict[str, int]
    original_content: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'translated_messages': self.translated_messages,
            'original_content': self.original_content
        }


class DatabaseMessageTracker:
    """Database-based message relationship tracker for translation synchronization"""
    
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.logger = logging.getLogger(__name__)
    
    async def add_mapping(self, original_message_id: int, original_channel_id: int,
                         translated_messages: Dict[str, int], original_content: str = None) -> bool:
        """
        Add a new message mapping to the database
        
        Args:
            original_message_id: ID of the original message
            original_channel_id: ID of the channel containing the original message
            translated_messages: Dict mapping channel names to translated message IDs
            original_content: Original message content (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            mapping = MessageMapping(
                id=None,
                guild_id=self.guild_id,
                original_message_id=original_message_id,
                original_channel_id=original_channel_id,
                translated_messages=translated_messages,
                original_content=original_content
            )
            
            await db_service.create_message_mapping(mapping)
            
            self.logger.debug(
                f"📝 Added mapping for message {original_message_id} -> "
                f"{len(translated_messages)} translations"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to add message mapping: {e}")
            return False
    
    async def get_mapping(self, original_message_id: int) -> Optional[MessageMappingData]:
        """
        Get message mapping data for an original message
        
        Args:
            original_message_id: ID of the original message
        
        Returns:
            MessageMappingData if found, None otherwise
        """
        try:
            mapping = await db_service.get_message_mapping(self.guild_id, original_message_id)
            
            if mapping:
                return MessageMappingData(
                    translated_messages=mapping.translated_messages,
                    original_content=mapping.original_content
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get message mapping for {original_message_id}: {e}")
            return None
    
    async def update_mapping(self, original_message_id: int, 
                           translated_messages: Dict[str, int], original_content: str = None) -> bool:
        """
        Update an existing message mapping
        
        Args:
            original_message_id: ID of the original message
            translated_messages: Updated dict mapping channel names to message IDs
            original_content: Updated original message content (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            success = await db_service.update_message_mapping(
                self.guild_id,
                original_message_id,
                translated_messages,
                original_content or ""
            )
            
            if success:
                self.logger.debug(
                    f"✏️ Updated mapping for message {original_message_id} -> "
                    f"{len(translated_messages)} translations"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update message mapping for {original_message_id}: {e}")
            return False
    
    async def remove_mapping(self, original_message_id: int) -> bool:
        """
        Remove a message mapping from the database
        
        Args:
            original_message_id: ID of the original message
        
        Returns:
            True if successful, False otherwise
        """
        try:
            success = await db_service.delete_message_mapping(self.guild_id, original_message_id)
            
            if success:
                self.logger.debug(f"🗑️ Removed mapping for message {original_message_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Failed to remove message mapping for {original_message_id}: {e}")
            return False
    
    async def get_mapping_count(self) -> int:
        """
        Get the total number of message mappings for this guild
        
        Returns:
            Number of mappings
        """
        try:
            # Note: This would require a new method in db_service
            # For now, we'll return 0 as a placeholder
            return 0
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get mapping count: {e}")
            return 0
    
    async def cleanup_old_mappings(self, days: int = 30) -> int:
        """
        Clean up old message mappings (older than specified days)
        
        Args:
            days: Number of days to keep mappings
        
        Returns:
            Number of cleaned up mappings
        """
        try:
            # This would require implementation in db_service
            # For now, we'll return 0 as a placeholder
            self.logger.info(f"🧹 Cleanup old mappings older than {days} days (placeholder)")
            return 0
            
        except Exception as e:
            self.logger.error(f"❌ Failed to cleanup old mappings: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about message mappings for this guild
        
        Returns:
            Dictionary with mapping statistics
        """
        try:
            mapping_count = await self.get_mapping_count()
            
            return {
                'guild_id': self.guild_id,
                'total_mappings': mapping_count,
                'tracking_enabled': True
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get mapping stats: {e}")
            return {
                'guild_id': self.guild_id,
                'total_mappings': 0,
                'tracking_enabled': False,
                'error': str(e)
            }