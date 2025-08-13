import os
import logging
import asyncio
from typing import Dict, Optional, Set
from pathlib import Path

import discord
from discord.ext import commands

from .translator import GeminiTranslator
from .image_handler import ImageHandler
from .emoji_sticker_handler import EmojiStickerHandler
from utils.rate_limiter import RateLimiter
from utils.cost_monitor import CostMonitor
from utils.message_tracker import MessageTracker


class TranslationBot(commands.Bot):
    def __init__(self, rate_limiter: RateLimiter, cost_monitor: CostMonitor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.logger = logging.getLogger(__name__)
        self.rate_limiter = rate_limiter
        self.cost_monitor = cost_monitor
        
        self.translator = GeminiTranslator(os.getenv('GEMINI_API_KEY'))
        self.image_handler = ImageHandler()
        self.emoji_sticker_handler = EmojiStickerHandler()
        self.message_tracker = MessageTracker()
        
        self.server_id = int(os.getenv('SERVER_ID'))
        self.channel_ids = {
            'korean': int(os.getenv('KOREAN_CHANNEL_ID')),
            'english': int(os.getenv('ENGLISH_CHANNEL_ID')),
            'japanese': int(os.getenv('JAPANESE_CHANNEL_ID')),
            'chinese': int(os.getenv('CHINESE_CHANNEL_ID'))
        }
        
        self.id_to_channel = {v: k for k, v in self.channel_ids.items()}
        
        self.processing_messages: Set[int] = set()
    
    async def on_ready(self):
        self.logger.info(f"🤖 Bot logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"🎯 Monitoring server ID: {self.server_id}")
        self.logger.info(f"🌐 Translation channels: {self.channel_ids}")
        
        # Test logging at startup to verify all levels work
        self.logger.debug("🔍 DEBUG test: Bot initialization debug info")
        self.logger.warning("⚠️ WARNING test: This is a startup warning test")
        
        try:
            synced = await self.tree.sync()
            self.logger.info(f"✅ Synced {len(synced)} slash commands")
            
            # Verify channel access
            accessible_channels = 0
            for channel_name, channel_id in self.channel_ids.items():
                channel = self.get_channel(channel_id)
                if channel:
                    accessible_channels += 1
                    self.logger.debug(f"✅ Channel access confirmed: {channel_name} ({channel.name})")
                else:
                    self.logger.error(f"❌ Cannot access channel: {channel_name} (ID: {channel_id})")
            
            self.logger.info(f"📊 Channel accessibility: {accessible_channels}/{len(self.channel_ids)} channels accessible")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to sync commands: {e}")
        
        self.logger.info("🚀 Bot initialization completed - Ready to translate!")
    
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            self.logger.debug(f"🤖 Ignoring bot message from {message.author}")
            return
        
        if message.guild.id != self.server_id:
            self.logger.debug(f"🚫 Ignoring message from different server: {message.guild.id}")
            return
        
        if message.channel.id not in self.id_to_channel:
            self.logger.debug(f"🚫 Ignoring message from non-translation channel: {message.channel.name}")
            return
        
        if message.id in self.processing_messages:
            self.logger.debug(f"⏳ Message already being processed: {message.id}")
            return
        
        source_channel = self.id_to_channel[message.channel.id]
        self.logger.info(f"📨 New message in {source_channel} from {message.author.display_name}: {message.content[:50]}...")
        
        self.processing_messages.add(message.id)
        
        try:
            await self._process_message(message)
        finally:
            self.processing_messages.discard(message.id)

    async def on_message_delete(self, message: discord.Message):
        """Handle message deletion - delete corresponding translated messages."""
        if message.guild.id != self.server_id:
            return
        
        if message.channel.id not in self.id_to_channel:
            return
        
        self.logger.info(f"🗑️ Message deleted in {self.id_to_channel[message.channel.id]}: {message.id}")
        
        # Get mapping and delete translated messages
        mapping = await self.message_tracker.get_mapping(message.id)
        if mapping:
            await self._delete_translated_messages(mapping)
            await self.message_tracker.remove_mapping(message.id)
            self.logger.info(f"✅ Deleted {len(mapping.translated_messages)} translated messages")

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handle message editing - update translated messages."""
        if after.guild.id != self.server_id:
            return
        
        if after.channel.id not in self.id_to_channel:
            return
        
        if after.author.bot:
            return
        
        source_channel = self.id_to_channel[after.channel.id]
        self.logger.info(f"✏️ Message edited in {source_channel}: {after.id}")
        
        # Get existing mapping
        mapping = await self.message_tracker.get_mapping(after.id)
        if mapping:
            # Delete old translated messages
            await self._delete_translated_messages(mapping)
            
            # Re-translate and create new messages
            new_translated_messages = await self._retranslate_message(after, source_channel)
            
            # Update mapping
            if new_translated_messages:
                await self.message_tracker.update_mapping(
                    after.id, 
                    new_translated_messages, 
                    after.content
                )
                self.logger.info(f"✅ Updated {len(new_translated_messages)} translated messages")

    async def _process_message(self, message: discord.Message):
        source_channel = self.id_to_channel[message.channel.id]
        
        # Check if message should skip translation (emoji/sticker only)
        if self.emoji_sticker_handler.should_skip_translation(message):
            await self._handle_emoji_sticker_only(message, source_channel)
            return
        
        if not await self.rate_limiter.acquire():
            self.logger.warning(f"Rate limit exceeded, skipping message from {message.author}")
            return
        
        if not self.cost_monitor.can_make_request():
            self.logger.warning(f"Cost limit reached, skipping message from {message.author}")
            return
        
        has_text = message.content.strip()
        has_attachments = message.attachments
        has_embeds = message.embeds
        has_stickers = message.stickers
        
        if not (has_text or has_attachments or has_embeds or has_stickers):
            return
        
        # Only record cost for actual translation requests
        if has_text and not self._is_command_or_link(message.content):
            await self.cost_monitor.record_request()
        
        tasks = []
        
        if has_text and not self._is_command_or_link(message.content):
            task = self._handle_text_translation(message, source_channel)
            tasks.append(task)
        
        if has_attachments:
            task = self._handle_attachments(message, source_channel)
            tasks.append(task)
        
        if has_embeds or self._is_command_or_link(message.content):
            task = self._handle_embeds_and_links(message, source_channel)
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _is_command_or_link(self, content: str) -> bool:
        content = content.strip().lower()
        return (content.startswith('/') or 
                content.startswith('!') or
                'http://' in content or 
                'https://' in content or
                'discord.gg' in content)
    
    async def _handle_text_translation(self, message: discord.Message, source_channel: str):
        try:
            translations = await self.translator.translate_to_all_languages(
                message.content, source_channel
            )
            
            translated_message_ids = {}
            
            # Check if this is a reply
            reply_to_id = None
            if message.reference and message.reference.message_id:
                reply_to_id = message.reference.message_id
            
            for target_channel, translated_text in translations.items():
                if translated_text:
                    sent_message = await self._send_translation_with_reply(
                        message, target_channel, translated_text, reply_to_id
                    )
                    if sent_message:
                        translated_message_ids[target_channel] = sent_message.id
            
            # Add mapping to tracker
            if translated_message_ids:
                await self.message_tracker.add_mapping(
                    original_message_id=message.id,
                    original_channel_id=message.channel.id,
                    original_author_id=message.author.id,
                    translated_messages=translated_message_ids,
                    content_preview=message.content,
                    message_type='text',
                    reply_to=reply_to_id
                )
                self.logger.debug(f"📝 Added message mapping: {message.id} -> {translated_message_ids}")
                    
        except Exception as e:
            self.logger.error(f"Text translation failed: {e}")
    
    async def _handle_attachments(self, message: discord.Message, source_channel: str):
        try:
            for target_channel in self.channel_ids.keys():
                if target_channel != source_channel:
                    await self._send_attachments(message, target_channel)
                    
        except Exception as e:
            self.logger.error(f"Attachment handling failed: {e}")
    
    async def _handle_embeds_and_links(self, message: discord.Message, source_channel: str):
        try:
            for target_channel in self.channel_ids.keys():
                if target_channel != source_channel:
                    await self._send_embed_or_link(message, target_channel)
                    
        except Exception as e:
            self.logger.error(f"Embed/link handling failed: {e}")
    
    async def _send_translation(self, original_message: discord.Message, 
                              target_channel: str, translated_text: str):
        channel_id = self.channel_ids[target_channel]
        channel = self.get_channel(channel_id)
        
        if not channel:
            self.logger.error(f"Target channel not found: {channel_id}")
            return
        
        username = original_message.author.display_name
        
        embed = discord.Embed(
            description=translated_text,
            color=0x7289DA
        )
        embed.set_author(
            name=username,
            icon_url=original_message.author.display_avatar.url
        )
        
        try:
            await channel.send(embed=embed)
            self.logger.debug(f"Translation sent to {target_channel}: {translated_text[:50]}...")
        except Exception as e:
            self.logger.error(f"Failed to send translation to {target_channel}: {e}")
    
    async def _send_attachments(self, original_message: discord.Message, target_channel: str):
        channel_id = self.channel_ids[target_channel]
        channel = self.get_channel(channel_id)
        
        if not channel:
            return
        
        username = original_message.author.display_name
        files = []
        
        try:
            for attachment in original_message.attachments:
                file_data = await self.image_handler.process_attachment(attachment)
                if file_data:
                    files.append(discord.File(file_data, filename=attachment.filename))
            
            if files:
                await channel.send(
                    content=f"**{username}** uploaded:",
                    files=files
                )
                
        except Exception as e:
            self.logger.error(f"Failed to send attachments to {target_channel}: {e}")
    
    async def _send_embed_or_link(self, original_message: discord.Message, target_channel: str):
        channel_id = self.channel_ids[target_channel]
        channel = self.get_channel(channel_id)
        
        if not channel:
            return
        
        username = original_message.author.display_name
        
        try:
            content = f"**{username}**: {original_message.content}" if original_message.content else f"**{username}**:"
            
            await channel.send(
                content=content,
                embeds=original_message.embeds[:10] if original_message.embeds else None
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send embed/link to {target_channel}: {e}")

    async def _handle_emoji_sticker_only(self, message: discord.Message, source_channel: str):
        """Handle messages that contain only emojis or stickers."""
        try:
            for target_channel in self.channel_ids.keys():
                if target_channel != source_channel:
                    channel_id = self.channel_ids[target_channel]
                    channel = self.get_channel(channel_id)
                    
                    if channel:
                        await self.emoji_sticker_handler.send_emoji_sticker_message(
                            message, channel
                        )
                        
        except Exception as e:
            self.logger.error(f"Failed to handle emoji/sticker message: {e}")

    @commands.hybrid_command(name="status")
    async def status_command(self, ctx):
        rate_stats = self.rate_limiter.get_usage_stats()
        cost_stats = self.cost_monitor.get_usage_stats()
        
        embed = discord.Embed(
            title="🤖 Key Bot Status",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📊 Rate Limiting",
            value=f"Requests this minute: {rate_stats['requests_this_minute']}/{rate_stats['requests_per_minute_limit']}\n"
                  f"Requests today: {rate_stats['requests_today']}/{rate_stats['max_daily_requests']}",
            inline=False
        )
        
        embed.add_field(
            name="💰 Cost Monitoring",
            value=f"Monthly cost: ${cost_stats['current_month_cost']:.4f}/${cost_stats['max_monthly_cost']:.2f}\n"
                  f"Usage: {cost_stats['cost_percentage']:.1f}%\n"
                  f"Total requests: {cost_stats['total_requests']}",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="help")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="🌐 Key Translation Bot",
            description="Multi-language real-time translation bot",
            color=0x7289DA
        )
        
        embed.add_field(
            name="🔄 Auto Translation",
            value="Messages in language channels are automatically translated to other languages",
            inline=False
        )
        
        embed.add_field(
            name="📁 File Support", 
            value="Images and files are automatically shared across channels",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Link & Embed Support",
            value="Links and embeds are preserved and shared across channels",
            inline=False
        )
        
        embed.add_field(
            name="📋 Commands",
            value="`/status` - Check bot status and usage\n"
                  "`/help` - Show this help message\n"
                  "`/test_logging` - Test all logging levels (Admin only)",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="test_logging")
    async def test_logging_command(self, ctx):
        """Test all logging levels - Admin only command."""
        # Check if user has administrator permissions
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ This command requires administrator permissions.", ephemeral=True)
            return
        
        from utils.logger import test_all_log_levels, get_log_level_info
        
        # Get current logging info
        log_info = get_log_level_info()
        
        embed = discord.Embed(
            title="🧪 Logging System Test",
            description="Testing all logging levels...",
            color=0x00ff00
        )
        
        embed.add_field(
            name="Current Log Level",
            value=f"**{log_info['current_level']}**",
            inline=True
        )
        
        embed.add_field(
            name="Visible Levels",
            value=", ".join(log_info['visible_levels']),
            inline=True
        )
        
        if log_info['hidden_levels']:
            embed.add_field(
                name="Hidden Levels",
                value=", ".join(log_info['hidden_levels']),
                inline=True
            )
        
        embed.add_field(
            name="📝 Note",
            value="Check the bot logs to see the test messages. "
                  f"Only levels {', '.join(log_info['visible_levels'])} will be visible with current settings.",
            inline=False
        )
        
        # Send the embed first
        await ctx.send(embed=embed)
        
        # Perform the logging test
        self.logger.info("🧪 LOGGING TEST STARTED by admin")
        test_all_log_levels(self.logger)
        self.logger.info("🧪 LOGGING TEST COMPLETED")
        
        # Send completion message
        await ctx.followup.send("✅ Logging test completed! Check the bot logs to see all test messages.", ephemeral=True)

    async def _delete_translated_messages(self, mapping):
        """Delete all translated messages for a given mapping."""
        for channel_name, message_id in mapping.translated_messages.items():
            try:
                channel_id = self.channel_ids[channel_name]
                channel = self.get_channel(channel_id)
                if channel:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                    self.logger.debug(f"🗑️ Deleted translated message in {channel_name}: {message_id}")
            except discord.NotFound:
                self.logger.debug(f"⚠️ Translated message already deleted: {message_id}")
            except Exception as e:
                self.logger.error(f"❌ Failed to delete translated message {message_id}: {e}")

    async def _retranslate_message(self, message: discord.Message, source_channel: str) -> Dict[str, int]:
        """Re-translate a message and return new message IDs."""
        new_translated_messages = {}
        
        try:
            # Determine message type and handle accordingly
            if self.emoji_sticker_handler.should_skip_translation(message):
                # Handle emoji/sticker messages
                for target_channel in self.channel_ids.keys():
                    if target_channel != source_channel:
                        channel_id = self.channel_ids[target_channel]
                        channel = self.get_channel(channel_id)
                        if channel:
                            success = await self.emoji_sticker_handler.send_emoji_sticker_message(
                                message, channel
                            )
                            if success:
                                # Note: We can't easily get the message ID from send_emoji_sticker_message
                                # This is a limitation we'll need to address
                                pass
            
            elif message.content and not self._is_command_or_link(message.content):
                # Handle text translation
                translations = await self.translator.translate_to_all_languages(
                    message.content, source_channel
                )
                
                for target_channel, translated_text in translations.items():
                    if translated_text:
                        sent_message = await self._send_translation_with_return(
                            message, target_channel, translated_text
                        )
                        if sent_message:
                            new_translated_messages[target_channel] = sent_message.id
            
            # Handle attachments, embeds, etc. (similar pattern)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to retranslate message: {e}")
        
        return new_translated_messages

    async def _send_translation_with_return(self, original_message: discord.Message, 
                                          target_channel: str, translated_text: str) -> Optional[discord.Message]:
        """Send translation and return the sent message object."""
        channel_id = self.channel_ids[target_channel]
        channel = self.get_channel(channel_id)
        
        if not channel:
            self.logger.error(f"Target channel not found: {channel_id}")
            return None
        
        username = original_message.author.display_name
        
        embed = discord.Embed(
            description=translated_text,
            color=0x7289DA
        )
        embed.set_author(
            name=username,
            icon_url=original_message.author.display_avatar.url
        )
        
        try:
            sent_message = await channel.send(embed=embed)
            self.logger.debug(f"✅ Translation sent to {target_channel}: {translated_text[:50]}...")
            return sent_message
        except Exception as e:
            self.logger.error(f"❌ Failed to send translation to {target_channel}: {e}")
            return None

    async def _send_translation_with_reply(self, original_message: discord.Message, 
                                         target_channel: str, translated_text: str,
                                         reply_to_id: Optional[int] = None) -> Optional[discord.Message]:
        """Send translation with reply reference if applicable."""
        channel_id = self.channel_ids[target_channel]
        channel = self.get_channel(channel_id)
        
        if not channel:
            self.logger.error(f"Target channel not found: {channel_id}")
            return None
        
        username = original_message.author.display_name
        
        embed = discord.Embed(
            description=translated_text,
            color=0x7289DA
        )
        embed.set_author(
            name=username,
            icon_url=original_message.author.display_avatar.url
        )
        
        # Handle reply reference
        message_reference = None
        if reply_to_id:
            # Find the translated version of the replied-to message
            reply_mapping = await self.message_tracker.get_mapping(reply_to_id)
            if reply_mapping and target_channel in reply_mapping.translated_messages:
                try:
                    translated_reply_id = reply_mapping.translated_messages[target_channel]
                    reply_message = await channel.fetch_message(translated_reply_id)
                    message_reference = reply_message
                    self.logger.debug(f"🔗 Adding reply reference to message {translated_reply_id}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not fetch reply message: {e}")
        
        try:
            sent_message = await channel.send(
                embed=embed,
                reference=message_reference,
                mention_author=False  # Don't ping the original author
            )
            self.logger.debug(f"✅ Translation sent to {target_channel}: {translated_text[:50]}...")
            return sent_message
        except Exception as e:
            self.logger.error(f"❌ Failed to send translation to {target_channel}: {e}")
            return None