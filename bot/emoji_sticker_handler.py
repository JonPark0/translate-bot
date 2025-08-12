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
    
    def _get_sticker_url(self, sticker_id: str, format_type: str = 'png') -> str:
        """Generate Discord CDN URL for sticker."""
        # Discord stickers can be in different formats: png, apng, lottie
        return f"https://cdn.discordapp.com/stickers/{sticker_id}.{format_type}"
    
    def get_sticker_info(self, stickers: List) -> List[Dict]:
        """Get detailed info about stickers."""
        sticker_info = []
        for sticker in stickers:
            # Get sticker format - more robust approach
            format_type = sticker.format if hasattr(sticker, 'format') else discord.StickerFormatType.png
            
            self.logger.debug(f"Processing sticker {sticker.name} (ID: {sticker.id}) - Format: {format_type}")
            
            # Determine the best URL format based on sticker type
            if format_type == discord.StickerFormatType.png:
                # Static PNG stickers
                primary_url = self._get_sticker_url(str(sticker.id), 'png')
                fallback_urls = []
                extension = 'png'
                animated = False
                
            elif format_type == discord.StickerFormatType.apng:
                # Animated PNG stickers - try GIF first for better Discord support
                primary_url = self._get_sticker_url(str(sticker.id), 'png') # Discord serves APNG as PNG with animation
                fallback_urls = [
                    self._get_sticker_url(str(sticker.id), 'gif'),  # Alternative GIF version
                ]
                extension = 'png'  # Keep original extension
                animated = True
                
            elif format_type == discord.StickerFormatType.lottie:
                # Lottie animations - Discord converts to GIF for display
                primary_url = self._get_sticker_url(str(sticker.id), 'png')  # Try PNG conversion first
                fallback_urls = [
                    self._get_sticker_url(str(sticker.id), 'gif'),   # GIF conversion
                    self._get_sticker_url(str(sticker.id), 'json')   # Original Lottie JSON
                ]
                extension = 'png'
                animated = True
                
            else:
                # Unknown format - default to PNG
                primary_url = self._get_sticker_url(str(sticker.id), 'png')
                fallback_urls = []
                extension = 'png'
                animated = False
            
            sticker_data = {
                'id': str(sticker.id),
                'name': sticker.name,
                'format': format_type,
                'format_name': format_type.name if hasattr(format_type, 'name') else str(format_type),
                'extension': extension,
                'url': primary_url,
                'fallback_urls': fallback_urls,
                'all_urls': [primary_url] + fallback_urls,
                'description': getattr(sticker, 'description', ''),
                'tags': getattr(sticker, 'tags', []),
                'animated': animated
            }
            
            self.logger.debug(f"Sticker info: {sticker_data}")
            sticker_info.append(sticker_data)
        
        return sticker_info
    
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
        """Send sticker message with sticker images using embeds."""
        try:
            sticker_info_list = self.get_sticker_info(stickers)
            content = original_message.content
            
            # Create embed for sticker display
            embed = discord.Embed(
                description=f"**{username}** sent sticker{'s' if len(stickers) > 1 else ''}:",
                color=0x9966CC  # Purple color for stickers
            )
            
            # Add text content if present
            if content:
                embed.add_field(
                    name="Message",
                    value=content,
                    inline=False
                )
            
            # Handle multiple stickers
            for i, sticker_info in enumerate(sticker_info_list):
                sticker_name = sticker_info['name']
                sticker_url = sticker_info['url']
                is_animated = sticker_info.get('animated', False)
                fallback_urls = sticker_info.get('fallback_urls', [])
                
                # Set first sticker as main image
                if i == 0:
                    embed.set_image(url=sticker_url)
                    footer_text = f"Sticker: {sticker_name}"
                    if is_animated:
                        footer_text += " (Animated)"
                    embed.set_footer(text=footer_text)
                else:
                    # Add additional stickers as fields
                    sticker_links = [f"[View Sticker]({sticker_url})"]
                    
                    # Add fallback links for animated stickers
                    if fallback_urls:
                        for j, fallback_url in enumerate(fallback_urls):
                            sticker_links.append(f"[Alt {j+1}]({fallback_url})")
                    
                    embed.add_field(
                        name=f"Sticker: {sticker_name}" + (" (Animated)" if is_animated else ""),
                        value=" • ".join(sticker_links),
                        inline=True
                    )
                
                # Add description if available
                if sticker_info['description']:
                    embed.add_field(
                        name=f"{sticker_name} Description",
                        value=sticker_info['description'][:100],  # Limit description length
                        inline=True
                    )
                
                # Add format info for debugging (only in DEBUG mode)
                if self.logger.isEnabledFor(logging.DEBUG):
                    format_info = f"Type: {sticker_info.get('format_name', 'unknown')}, "
                    format_info += f"Extension: {sticker_info.get('extension', 'unknown')}, "
                    format_info += f"Animated: {sticker_info.get('animated', False)}"
                    
                    embed.add_field(
                        name="Debug Info",
                        value=format_info,
                        inline=True
                    )
                    
                    # Add all URLs for testing
                    all_urls = sticker_info.get('all_urls', [sticker_url])
                    if len(all_urls) > 1:
                        embed.add_field(
                            name="All URLs",
                            value="\n".join([f"{i+1}. {url}" for i, url in enumerate(all_urls)]),
                            inline=False
                        )
            
            await target_channel.send(embed=embed)
            
            # Log sticker details
            sticker_details = []
            for s in sticker_info_list:
                detail = f"{s['name']} (ID: {s['id']}, Format: {s.get('format_name', 'unknown')}, "
                detail += f"Animated: {s.get('animated', False)}, Primary URL: {s['url']}"
                if s.get('fallback_urls'):
                    detail += f", Fallback URLs: {s['fallback_urls']}"
                sticker_details.append(detail)
            
            self.logger.info(f"Sent sticker embed - Stickers: {sticker_details}")
            
            return True
            
        except Exception as e:
            # Fallback to text-only message if embed fails
            self.logger.warning(f"Sticker embed failed, using fallback: {e}")
            return await self._send_sticker_fallback(target_channel, username, stickers, original_message.content)
    
    async def _send_sticker_fallback(self, target_channel: discord.TextChannel,
                                   username: str, stickers: List, content: str = None) -> bool:
        """Fallback method for sticker messages when embeds fail."""
        try:
            sticker_info = f"**{username}** sent sticker{'s' if len(stickers) > 1 else ''}"
            
            if content:
                display_content = f"{sticker_info}: {content}"
            else:
                display_content = sticker_info
            
            # Add sticker names
            sticker_names = [sticker.name for sticker in stickers]
            display_content += f" ({', '.join(sticker_names)})"
            
            await target_channel.send(display_content)
            
            self.logger.debug(f"Sent sticker fallback message")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send sticker fallback message: {e}")
            return False