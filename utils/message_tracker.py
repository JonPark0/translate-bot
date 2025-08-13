import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio


@dataclass
class MessageMapping:
    """Represents a mapping between original and translated messages."""
    original_message_id: int
    original_channel_id: int
    original_author_id: int
    translated_messages: Dict[str, int]  # {channel_name: message_id}
    timestamp: str
    content_preview: str
    message_type: str  # 'text', 'emoji', 'sticker', 'attachment', 'embed'
    reply_to: Optional[int] = None  # Original message ID if this is a reply


class MessageTracker:
    """Tracks relationships between original and translated messages."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "message_mappings.json"
        self.logger = logging.getLogger(__name__)
        
        # In-memory storage for fast access
        self.mappings: Dict[int, MessageMapping] = {}
        self.reverse_mappings: Dict[int, int] = {}  # translated_id -> original_id
        
        self._lock = asyncio.Lock()
        self._load_data()
    
    def _load_data(self):
        """Load message mappings from file."""
        if not self.data_file.exists():
            self.logger.info("No existing message mappings found")
            return
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for original_id_str, mapping_data in data.items():
                original_id = int(original_id_str)
                mapping = MessageMapping(**mapping_data)
                self.mappings[original_id] = mapping
                
                # Build reverse mappings
                for translated_id in mapping.translated_messages.values():
                    self.reverse_mappings[translated_id] = original_id
            
            self.logger.info(f"Loaded {len(self.mappings)} message mappings")
            
        except Exception as e:
            self.logger.error(f"Failed to load message mappings: {e}")
            self.mappings = {}
            self.reverse_mappings = {}
    
    async def _save_data(self):
        """Save message mappings to file."""
        try:
            # Convert to serializable format
            data = {}
            for original_id, mapping in self.mappings.items():
                data[str(original_id)] = asdict(mapping)
            
            # Write to temporary file first, then rename for atomicity
            temp_file = self.data_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_file.replace(self.data_file)
            self.logger.debug(f"Saved {len(self.mappings)} message mappings")
            
        except Exception as e:
            self.logger.error(f"Failed to save message mappings: {e}")
    
    async def add_mapping(self, original_message_id: int, original_channel_id: int,
                         original_author_id: int, translated_messages: Dict[str, int],
                         content_preview: str, message_type: str,
                         reply_to: Optional[int] = None):
        """Add a new message mapping."""
        async with self._lock:
            mapping = MessageMapping(
                original_message_id=original_message_id,
                original_channel_id=original_channel_id,
                original_author_id=original_author_id,
                translated_messages=translated_messages,
                timestamp=datetime.utcnow().isoformat(),
                content_preview=content_preview[:100],  # Limit preview length
                message_type=message_type,
                reply_to=reply_to
            )
            
            self.mappings[original_message_id] = mapping
            
            # Update reverse mappings
            for translated_id in translated_messages.values():
                self.reverse_mappings[translated_id] = original_message_id
            
            await self._save_data()
            self.logger.debug(f"Added mapping for message {original_message_id} -> {translated_messages}")
    
    async def get_mapping(self, original_message_id: int) -> Optional[MessageMapping]:
        """Get mapping for an original message."""
        async with self._lock:
            return self.mappings.get(original_message_id)
    
    async def get_original_from_translated(self, translated_message_id: int) -> Optional[MessageMapping]:
        """Get original message mapping from a translated message ID."""
        async with self._lock:
            original_id = self.reverse_mappings.get(translated_message_id)
            if original_id:
                return self.mappings.get(original_id)
            return None
    
    async def remove_mapping(self, original_message_id: int) -> Optional[MessageMapping]:
        """Remove a message mapping and return it."""
        async with self._lock:
            mapping = self.mappings.pop(original_message_id, None)
            if mapping:
                # Remove reverse mappings
                for translated_id in mapping.translated_messages.values():
                    self.reverse_mappings.pop(translated_id, None)
                
                await self._save_data()
                self.logger.debug(f"Removed mapping for message {original_message_id}")
            
            return mapping
    
    async def update_mapping(self, original_message_id: int,
                           new_translated_messages: Dict[str, int],
                           new_content_preview: str = None):
        """Update translated message IDs for an existing mapping."""
        async with self._lock:
            mapping = self.mappings.get(original_message_id)
            if not mapping:
                self.logger.warning(f"No mapping found for message {original_message_id}")
                return False
            
            # Remove old reverse mappings
            for old_translated_id in mapping.translated_messages.values():
                self.reverse_mappings.pop(old_translated_id, None)
            
            # Update mapping
            mapping.translated_messages = new_translated_messages
            if new_content_preview:
                mapping.content_preview = new_content_preview[:100]
            
            # Add new reverse mappings
            for new_translated_id in new_translated_messages.values():
                self.reverse_mappings[new_translated_id] = original_message_id
            
            await self._save_data()
            self.logger.debug(f"Updated mapping for message {original_message_id}")
            return True
    
    async def get_reply_chain(self, message_id: int) -> List[MessageMapping]:
        """Get the reply chain for a message (replies to this message)."""
        async with self._lock:
            chain = []
            for mapping in self.mappings.values():
                if mapping.reply_to == message_id:
                    chain.append(mapping)
            return chain
    
    async def cleanup_old_mappings(self, max_age_days: int = 30):
        """Remove mappings older than specified days."""
        async with self._lock:
            cutoff_date = datetime.utcnow().timestamp() - (max_age_days * 24 * 60 * 60)
            removed_count = 0
            
            to_remove = []
            for original_id, mapping in self.mappings.items():
                mapping_time = datetime.fromisoformat(mapping.timestamp).timestamp()
                if mapping_time < cutoff_date:
                    to_remove.append(original_id)
            
            for original_id in to_remove:
                await self.remove_mapping(original_id)
                removed_count += 1
            
            if removed_count > 0:
                self.logger.info(f"Cleaned up {removed_count} old message mappings")
            
            return removed_count
    
    def get_stats(self) -> Dict:
        """Get statistics about tracked messages."""
        total_mappings = len(self.mappings)
        total_translated = len(self.reverse_mappings)
        
        type_counts = {}
        reply_counts = 0
        
        for mapping in self.mappings.values():
            type_counts[mapping.message_type] = type_counts.get(mapping.message_type, 0) + 1
            if mapping.reply_to:
                reply_counts += 1
        
        return {
            'total_original_messages': total_mappings,
            'total_translated_messages': total_translated,
            'message_types': type_counts,
            'reply_messages': reply_counts,
            'data_file_size': self.data_file.stat().st_size if self.data_file.exists() else 0
        }