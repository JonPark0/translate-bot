import re
import logging
from typing import List, Optional, Dict
import discord


class EmojiStickerHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Discord custom emoji pattern: <:name:id> or <a:name:id>
        self.custom_emoji_pattern = re.compile(r'<a?:[a-zA-Z0-9_]+:\d+>')
    
    def extract_discord_emojis(self, content: str) -> List[str]:
        """Extract Discord custom emojis from message content."""
        return self.custom_emoji_pattern.findall(content)
    
    def has_only_discord_emojis(self, content: str) -> bool:
        """Check if message contains only Discord custom emojis and whitespace."""
        if not content.strip():
            return False
        
        # Remove all Discord emojis and check if anything meaningful remains
        content_no_emojis = self.custom_emoji_pattern.sub('', content)
        
        # If only whitespace remains, it's emoji-only
        return not content_no_emojis.strip()
    
    def has_stickers(self, message: discord.Message) -> bool:
        """Check if message has stickers."""
        return bool(message.stickers)
    
    def get_emoji_info(self, content: str) -> Dict:
        """Get detailed info about Discord emojis in the content."""
        emojis = self.extract_discord_emojis(content)
        return {
            'has_discord_emojis': bool(emojis),
            'emoji_only': self.has_only_discord_emojis(content),
            'emoji_list': emojis,
            'emoji_count': len(emojis)
        }
    
    def should_skip_translation(self, message: discord.Message) -> bool:
        """Determine if message should skip translation due to emoji/sticker content."""
        content = message.content
        
        # Skip if message has stickers
        if self.has_stickers(message):
            self.logger.debug("Message has stickers, skipping translation")
            return True
        
        # Skip if message is Discord emoji-only
        if content and self.has_only_discord_emojis(content):
            self.logger.debug("Message is Discord emoji-only, skipping translation")
            return True
        
        return False
    
    async def send_emoji_sticker_message(self, original_message: discord.Message, 
                                       target_channel: discord.TextChannel) -> bool:
        """Send emoji/sticker message to target channel without translation."""
        try:
            username = original_message.author.display_name
            content = original_message.content
            stickers = original_message.stickers
            
            # Prepare message content
            if content and self.has_only_discord_emojis(content):
                # For Discord emoji-only messages, send as regular message with username
                display_content = f"**{username}**: {content}"
            elif stickers:
                # For sticker messages, mention the sticker
                sticker_info = f"**{username}** sent a sticker"
                if content:
                    display_content = f"{sticker_info}: {content}"
                else:
                    display_content = sticker_info
            else:
                return False
            
            # Send the message
            message_kwargs = {'content': display_content}
            
            # Include sticker info if present
            if stickers:
                sticker_names = [sticker.name for sticker in stickers]
                message_kwargs['content'] += f" (Stickers: {', '.join(sticker_names)})"
            
            await target_channel.send(**message_kwargs)
            
            self.logger.debug(f"Sent emoji/sticker message to {target_channel.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send emoji/sticker message: {e}")
            return False