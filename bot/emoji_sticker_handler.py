import re
import logging
from typing import List, Optional, Dict, Tuple
import discord
import aiohttp


class EmojiStickerHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Discord custom emoji patterns
        self.custom_emoji_pattern = re.compile(r'<(a?):([a-zA-Z0-9_]+):(\d+)>')  # <:name:id> or <a:name:id> with groups
        self.text_emoji_pattern = re.compile(r':([a-zA-Z0-9_]+):')  # :emoji_name: with group
    
    def extract_discord_emojis(self, content: str) -> List[Dict]:
        """Extract Discord custom emojis from message content with detailed info."""
        emojis = []
        
        # Custom emojis with ID: <:name:id> or <a:name:id>
        for match in self.custom_emoji_pattern.finditer(content):
            animated, name, emoji_id = match.groups()
            emojis.append({
                'type': 'custom',
                'animated': bool(animated),
                'name': name,
                'id': emoji_id,
                'original': match.group(0),
                'url': self._get_emoji_url(emoji_id, bool(animated))
            })
        
        # Text-format emojis: :emoji_name: (likely from other servers)
        for match in self.text_emoji_pattern.finditer(content):
            name = match.group(1)
            emojis.append({
                'type': 'text',
                'animated': False,
                'name': name,
                'id': None,
                'original': match.group(0),
                'url': None
            })
        
        return emojis
    
    def _get_emoji_url(self, emoji_id: str, animated: bool = False) -> str:
        """Generate Discord CDN URL for emoji."""
        extension = 'gif' if animated else 'png'
        return f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}"
    
    def has_only_discord_emojis(self, content: str) -> bool:
        """Check if message contains only Discord custom emojis and whitespace."""
        if not content.strip():
            return False
        
        # Remove all Discord emojis (both formats) and check if anything meaningful remains
        content_no_custom = self.custom_emoji_pattern.sub('', content)
        content_no_text = self.text_emoji_pattern.sub('', content_no_custom)
        
        # If only whitespace remains, it's emoji-only
        return not content_no_text.strip()
    
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
            'emoji_count': len(emojis),
            'custom_emojis': [e for e in emojis if e['type'] == 'custom'],
            'text_emojis': [e for e in emojis if e['type'] == 'text']
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
            
            # Handle emoji-only messages
            if content and self.has_only_discord_emojis(content):
                return await self._send_emoji_as_images(original_message, target_channel, username, content)
            
            # Handle sticker messages
            elif stickers:
                return await self._send_sticker_message(original_message, target_channel, username, stickers)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to send emoji/sticker message: {e}")
            return False
    
    async def _send_emoji_as_images(self, original_message: discord.Message, 
                                   target_channel: discord.TextChannel, 
                                   username: str, content: str) -> bool:
        """Send emojis as images using embeds."""
        try:
            emoji_info = self.get_emoji_info(content)
            custom_emojis = emoji_info['custom_emojis']
            text_emojis = emoji_info['text_emojis']
            
            self.logger.debug(f"Processing emoji message - Custom: {len(custom_emojis)}, Text: {len(text_emojis)}")
            
            # If we have custom emojis with URLs, send them as embeds
            if custom_emojis:
                await self._send_custom_emoji_embeds(target_channel, username, custom_emojis, text_emojis)
                return True
            
            # If only text emojis, send as regular message
            elif text_emojis:
                display_content = f"**{username}**: {content}"
                await target_channel.send(display_content)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to send emoji images: {e}")
            return False
    
    async def _send_custom_emoji_embeds(self, target_channel: discord.TextChannel, 
                                      username: str, custom_emojis: List[Dict], 
                                      text_emojis: List[Dict]):
        """Send custom emojis as embed images."""
        try:
            # Create embed for emoji display
            embed = discord.Embed(
                description=f"**{username}** sent emojis:",
                color=0x7289DA
            )
            
            # Add emoji images
            emoji_descriptions = []
            for i, emoji in enumerate(custom_emojis):
                emoji_descriptions.append(f":{emoji['name']}:")
                
                # Set first emoji as main image, others as thumbnails (Discord limitation)
                if i == 0:
                    embed.set_image(url=emoji['url'])
                else:
                    # Add as field for multiple emojis
                    embed.add_field(
                        name=f":{emoji['name']}:",
                        value=f"[View Emoji]({emoji['url']})",
                        inline=True
                    )
            
            # Add text emojis if any
            if text_emojis:
                text_emoji_names = [f":{e['name']}:" for e in text_emojis]
                embed.add_field(
                    name="Text Emojis",
                    value=" ".join(text_emoji_names),
                    inline=False
                )
            
            await target_channel.send(embed=embed)
            self.logger.debug(f"Sent emoji embed with {len(custom_emojis)} custom emojis")
            
        except Exception as e:
            # Fallback to regular message if embed fails
            self.logger.warning(f"Emoji embed failed, using fallback: {e}")
            emoji_text = " ".join([f":{e['name']}:" for e in custom_emojis + text_emojis])
            await target_channel.send(f"**{username}**: {emoji_text}")
    
    async def _send_sticker_message(self, original_message: discord.Message,
                                  target_channel: discord.TextChannel,
                                  username: str, stickers: List) -> bool:
        """Send sticker message with sticker info."""
        try:
            sticker_info = f"**{username}** sent a sticker"
            content = original_message.content
            
            if content:
                display_content = f"{sticker_info}: {content}"
            else:
                display_content = sticker_info
            
            # Add sticker names
            sticker_names = [sticker.name for sticker in stickers]
            display_content += f" (Stickers: {', '.join(sticker_names)})"
            
            await target_channel.send(display_content)
            
            # Log sticker details
            sticker_details = [f"{s.name} (ID: {s.id})" for s in stickers]
            self.logger.debug(f"Sent sticker message - Stickers: {sticker_details}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send sticker message: {e}")
            return False