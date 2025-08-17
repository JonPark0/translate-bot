"""
Multi-server Translation Bot with Database Support
Enhanced Key Translation Bot with /init setup system
"""

import logging
import asyncio
from typing import Dict, Optional, Set, Any

import discord
from discord.ext import commands

from .translator import GeminiTranslator
from .image_handler import ImageHandler
from .emoji_sticker_handler import EmojiStickerHandler
from .setup_manager import SetupManager
from utils.message_tracker_db import DatabaseMessageTracker
from database.service import db_service
from database.models import GuildConfig, FeatureType


class TranslationBot(commands.Bot):
    """Multi-server translation bot with database configuration"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.logger = logging.getLogger(__name__)
        
        # Core components
        self.image_handler = ImageHandler()
        self.emoji_sticker_handler = EmojiStickerHandler()
        self.setup_manager = SetupManager(self)
        
        # Guild-specific data (cached from database)
        self.guild_configs: Dict[int, GuildConfig] = {}
        self.guild_translators: Dict[int, GeminiTranslator] = {}
        self.guild_trackers: Dict[int, DatabaseMessageTracker] = {}
        
        # Processing state
        self.processing_messages: Set[int] = set()
        
        # Register commands
        self._register_commands()
    
    def _register_commands(self):
        """Register bot commands"""
        
        @self.command(name='init')
        async def init_command(ctx):
            """Initialize bot configuration for this server"""
            await self.setup_manager.start_setup(ctx)
        
        @self.command(name='status')
        async def status_command(ctx):
            """Show bot status for this server"""
            await self._show_status(ctx)
        
        @self.command(name='help')
        async def help_command(ctx):
            """Show help information"""
            await self._show_help(ctx)
        
        @self.command(name='test_logging')
        @commands.has_permissions(administrator=True)
        async def test_logging_command(ctx):
            """Test all logging levels (Admin only)"""
            await self._test_logging(ctx)
    
    async def on_ready(self):
        """Bot ready event"""
        self.logger.info(f"🤖 Bot logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"🌐 Connected to {len(self.guilds)} guilds")
        
        # Load configurations for all guilds
        await self._load_all_guild_configs()
        
        # Test logging at startup
        self.logger.debug("🔍 DEBUG: Bot initialization debug info")
        self.logger.warning("⚠️ WARNING: Startup warning test")
        self.logger.critical("🚨 CRITICAL: Startup critical test")
        
        self.logger.info("✅ Bot is ready and operational!")
    
    async def on_guild_join(self, guild):
        """Handle bot joining a new guild"""
        self.logger.info(f"🏠 Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Send welcome message to the first available text channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="🎉 케이 봇에 오신 것을 환영합니다!",
                    description="다국어 실시간 번역, TTS, 음악 재생 기능을 제공하는 봇입니다.",
                    color=0x00FF00
                )
                
                embed.add_field(
                    name="🚀 시작하기",
                    value="`/init` 명령어를 사용하여 봇을 설정해주세요.",
                    inline=False
                )
                
                embed.add_field(
                    name="📚 도움말",
                    value="`/help` 명령어로 사용 가능한 기능을 확인하세요.",
                    inline=False
                )
                
                try:
                    await channel.send(embed=embed)
                    break
                except discord.Forbidden:
                    continue
    
    async def on_guild_remove(self, guild):
        """Handle bot leaving a guild"""
        self.logger.info(f"👋 Left guild: {guild.name} (ID: {guild.id})")
        
        # Clean up cached data
        if guild.id in self.guild_configs:
            del self.guild_configs[guild.id]
        if guild.id in self.guild_translators:
            del self.guild_translators[guild.id]
        if guild.id in self.guild_trackers:
            del self.guild_trackers[guild.id]
    
    async def on_message(self, message):
        """Handle incoming messages"""
        # Process commands first
        await self.process_commands(message)
        
        # Handle setup responses
        if await self.setup_manager.handle_setup_response(message):
            return
        
        # Skip bot messages and DMs
        if message.author.bot or not message.guild:
            return
        
        # Check if guild is configured for translation
        guild_config = await self._get_guild_config(message.guild.id)
        if not guild_config or not guild_config.is_feature_enabled(FeatureType.TRANSLATION):
            return
        
        # Process translation
        await self._process_message(message)
    
    async def on_message_delete(self, message):
        """Handle message deletion - sync delete translated messages"""
        if message.author.bot or not message.guild:
            return
        
        guild_config = await self._get_guild_config(message.guild.id)
        if not guild_config or not guild_config.is_feature_enabled(FeatureType.TRANSLATION):
            return
        
        # Get message tracker for this guild
        tracker = await self._get_message_tracker(message.guild.id)
        if not tracker:
            return
        
        # Check if this message has translations
        mapping = await tracker.get_mapping(message.id)
        if mapping:
            self.logger.info(f"🗑️ Message deleted in {message.guild.name}: {message.id}")
            
            # Delete translated messages
            await self._delete_translated_messages(mapping, message.guild.id)
            
            # Remove mapping
            await tracker.remove_mapping(message.id)
            
            self.logger.info(f"✅ Deleted {len(mapping.translated_messages)} translated messages")
    
    async def on_message_edit(self, before, after):
        """Handle message editing - update translated messages in place"""
        if after.author.bot or not after.guild:
            return
        
        guild_config = await self._get_guild_config(after.guild.id)
        if not guild_config or not guild_config.is_feature_enabled(FeatureType.TRANSLATION):
            return
        
        # Get channel mapping for this guild
        channel_mapping = await self._get_translation_channel_mapping(after.guild.id)
        if not channel_mapping or after.channel.id not in channel_mapping:
            return
        
        source_channel = channel_mapping[after.channel.id]
        tracker = await self._get_message_tracker(after.guild.id)
        
        if not tracker:
            return
        
        self.logger.info(f"✏️ Message edited in {source_channel}: {after.id}")
        
        # Get existing mapping
        mapping = await tracker.get_mapping(after.id)
        if mapping:
            # Edit existing translated messages in place
            updated_messages = await self._edit_translated_messages(after, mapping, source_channel, after.guild.id)
            
            # Update mapping with new content
            if updated_messages:
                await tracker.update_mapping(
                    after.id,
                    updated_messages,
                    after.content
                )
                self.logger.info(f"✅ Edited {len(updated_messages)} translated messages in place")
    
    async def _load_all_guild_configs(self):
        """Load configurations for all connected guilds"""
        for guild in self.guilds:
            try:
                config = await db_service.get_guild_config(guild.id)
                if config:
                    self.guild_configs[guild.id] = config
                    
                    # Initialize translator if API key is available
                    if config.api_key:
                        self.guild_translators[guild.id] = GeminiTranslator(config.api_key)
                    
                    # Initialize message tracker
                    self.guild_trackers[guild.id] = DatabaseMessageTracker(guild.id)
                    
                    self.logger.info(f"✅ Loaded config for guild: {guild.name}")
                else:
                    self.logger.info(f"ℹ️ No config found for guild: {guild.name} - use /init to configure")
                    
            except Exception as e:
                self.logger.error(f"❌ Failed to load config for guild {guild.id}: {e}")
    
    async def _get_guild_config(self, guild_id: int) -> Optional[GuildConfig]:
        """Get guild configuration, loading from database if not cached"""
        if guild_id not in self.guild_configs:
            try:
                config = await db_service.get_guild_config(guild_id)
                if config:
                    self.guild_configs[guild_id] = config
                    
                    # Initialize translator if needed
                    if config.api_key and guild_id not in self.guild_translators:
                        self.guild_translators[guild_id] = GeminiTranslator(config.api_key)
                    
                    # Initialize message tracker if needed
                    if guild_id not in self.guild_trackers:
                        self.guild_trackers[guild_id] = DatabaseMessageTracker(guild_id)
                        
                return config
            except Exception as e:
                self.logger.error(f"❌ Failed to get guild config for {guild_id}: {e}")
                return None
        
        return self.guild_configs.get(guild_id)
    
    async def _get_translator(self, guild_id: int) -> Optional[GeminiTranslator]:
        """Get translator for a guild"""
        if guild_id not in self.guild_translators:
            config = await self._get_guild_config(guild_id)
            if config and config.api_key:
                self.guild_translators[guild_id] = GeminiTranslator(config.api_key)
        
        return self.guild_translators.get(guild_id)
    
    async def _get_message_tracker(self, guild_id: int) -> Optional[DatabaseMessageTracker]:
        """Get message tracker for a guild"""
        if guild_id not in self.guild_trackers:
            self.guild_trackers[guild_id] = DatabaseMessageTracker(guild_id)
        
        return self.guild_trackers.get(guild_id)
    
    async def _get_translation_channel_mapping(self, guild_id: int) -> Optional[Dict[int, str]]:
        """Get channel ID to language mapping for translation"""
        try:
            translation_configs = await db_service.get_translation_configs(guild_id)
            if not translation_configs:
                return None
            
            return {config.channel_id: config.language_code for config in translation_configs}
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get translation channel mapping for {guild_id}: {e}")
            return None
    
    async def _process_message(self, message):
        """Process message for translation"""
        guild_id = message.guild.id
        
        # Prevent duplicate processing
        if message.id in self.processing_messages:
            return
        
        self.processing_messages.add(message.id)
        
        try:
            # Get channel mapping
            channel_mapping = await self._get_translation_channel_mapping(guild_id)
            if not channel_mapping or message.channel.id not in channel_mapping:
                return
            
            source_language = channel_mapping[message.channel.id]
            
            # Check for emoji/sticker only content
            if self.emoji_sticker_handler.should_skip_translation(message):
                await self._handle_emoji_sticker_message(message, source_language, guild_id)
                return
            
            # Handle text translation
            if message.content and not self._is_command_or_link(message.content):
                await self._handle_text_translation(message, source_language, guild_id)
            
            # Handle image/file sharing
            if message.attachments:
                await self._handle_attachments(message, source_language, guild_id)
                
        except Exception as e:
            self.logger.error(f"❌ Error processing message {message.id}: {e}")
        finally:
            self.processing_messages.discard(message.id)
    
    async def _handle_text_translation(self, message, source_language: str, guild_id: int):
        """Handle text message translation"""
        translator = await self._get_translator(guild_id)
        if not translator:
            self.logger.warning(f"⚠️ No translator available for guild {guild_id}")
            return
        
        # Get translation channel mapping
        translation_configs = await db_service.get_translation_configs(guild_id)
        target_channels = {config.language_code: config.channel_id for config in translation_configs}
        
        # Remove source channel from targets
        target_channels.pop(source_language, None)
        
        if not target_channels:
            return
        
        # Translate to all target languages
        translations = {}
        for target_lang, channel_id in target_channels.items():
            try:
                translated_text = await translator.translate(message.content, target_lang)
                if translated_text:
                    translations[target_lang] = translated_text
            except Exception as e:
                self.logger.error(f"❌ Translation failed for {target_lang}: {e}")
        
        if not translations:
            return
        
        # Send translations and track messages
        translated_messages = {}
        tracker = await self._get_message_tracker(guild_id)
        
        # Handle reply chains
        reply_mappings = {}
        if message.reference and message.reference.message_id:
            original_mapping = await tracker.get_mapping(message.reference.message_id)
            if original_mapping:
                reply_mappings = original_mapping.translated_messages
        
        # Send translations
        for target_lang, translated_text in translations.items():
            channel_id = target_channels[target_lang]
            channel = self.get_channel(channel_id)
            
            if channel:
                try:
                    # Send with reply if applicable
                    reply_to_id = reply_mappings.get(target_lang)
                    sent_message = await self._send_translation_with_reply(
                        message, channel, translated_text, reply_to_id
                    )
                    
                    if sent_message:
                        translated_messages[target_lang] = sent_message.id
                        
                except Exception as e:
                    self.logger.error(f"❌ Failed to send translation to {target_lang}: {e}")
        
        # Save message mapping
        if translated_messages and tracker:
            await tracker.add_mapping(
                message.id,
                message.channel.id,
                translated_messages,
                message.content
            )
    
    async def _send_translation_with_reply(self, original_message, target_channel, 
                                         translated_text: str, reply_to_id: Optional[int] = None):
        """Send translation with reply reference if applicable"""
        try:
            # Create embed
            username = original_message.author.display_name
            embed = discord.Embed(
                description=translated_text,
                color=0x7289DA
            )
            embed.set_author(
                name=username,
                icon_url=original_message.author.display_avatar.url
            )
            
            # Send with reply if available
            reference = None
            if reply_to_id:
                try:
                    reply_message = await target_channel.fetch_message(reply_to_id)
                    reference = reply_message
                except:
                    pass
            
            return await target_channel.send(embed=embed, reference=reference)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send translation: {e}")
            return None
    
    def _is_command_or_link(self, content: str) -> bool:
        """Check if content is a command or contains only links"""
        content = content.strip()
        
        if content.startswith(('/', '!', '?', '.', ',')):
            return True
        
        # Check if content is primarily links
        words = content.split()
        link_count = sum(1 for word in words if word.startswith(('http://', 'https://', 'www.')))
        
        return len(words) > 0 and (link_count / len(words)) > 0.5
    
    # Command implementations
    
    async def _show_status(self, ctx):
        """Show bot status for this server"""
        guild_config = await self._get_guild_config(ctx.guild.id)
        
        if not guild_config:
            embed = discord.Embed(
                title="❌ 봇이 설정되지 않음",
                description="`/init` 명령어를 사용하여 봇을 설정해주세요.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"📊 {ctx.guild.name} 봇 상태",
            color=0x00FF00
        )
        
        # Show enabled features
        features = []
        if guild_config.is_feature_enabled(FeatureType.TRANSLATION):
            features.append("🌐 번역")
        if guild_config.is_feature_enabled(FeatureType.TTS):
            features.append("🔊 TTS")
        if guild_config.is_feature_enabled(FeatureType.MUSIC):
            features.append("🎵 음악")
        
        embed.add_field(
            name="활성화된 기능",
            value=" | ".join(features) if features else "없음",
            inline=False
        )
        
        # Show translation channels if enabled
        if guild_config.is_feature_enabled(FeatureType.TRANSLATION):
            translation_configs = await db_service.get_translation_configs(ctx.guild.id)
            if translation_configs:
                channel_info = []
                for config in translation_configs:
                    channel_info.append(f"{config.language_name}: <#{config.channel_id}>")
                
                embed.add_field(
                    name="번역 채널",
                    value="\n".join(channel_info),
                    inline=False
                )
        
        embed.add_field(
            name="초기화 상태",
            value="✅ 완료" if guild_config.is_initialized else "❌ 미완료",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    async def _show_help(self, ctx):
        """Show help information"""
        embed = discord.Embed(
            title="📚 케이 봇 도움말",
            description="다국어 실시간 번역, TTS, 음악 재생 봇",
            color=0x7289DA
        )
        
        embed.add_field(
            name="🚀 초기 설정",
            value="`/init` - 봇 초기 설정 (관리자 권한 필요)",
            inline=False
        )
        
        embed.add_field(
            name="📊 상태 확인",
            value="`/status` - 현재 서버의 봇 설정 상태 확인",
            inline=False
        )
        
        embed.add_field(
            name="🔧 관리자 명령어",
            value="`/test_logging` - 로깅 레벨 테스트 (관리자 전용)",
            inline=False
        )
        
        guild_config = await self._get_guild_config(ctx.guild.id)
        if guild_config and guild_config.is_initialized:
            embed.add_field(
                name="✅ 현재 상태",
                value="봇이 설정되어 있습니다. 설정된 기능을 사용할 수 있습니다.",
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ 설정 필요",
                value="`/init` 명령어로 봇을 설정해주세요.",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    async def _test_logging(self, ctx):
        """Test all logging levels"""
        self.logger.debug("🔍 DEBUG: Test debug message")
        self.logger.info("ℹ️ INFO: Test info message")
        self.logger.warning("⚠️ WARNING: Test warning message")
        self.logger.error("❌ ERROR: Test error message")
        self.logger.critical("🚨 CRITICAL: Test critical message")
        
        await ctx.send("✅ 모든 로깅 레벨 테스트 완료. 로그 파일을 확인하세요.")
    
    # Helper methods for message editing/deletion
    
    async def _delete_translated_messages(self, mapping, guild_id: int):
        """Delete translated messages"""
        for channel_name, message_id in mapping.translated_messages.items():
            try:
                # Get channel from translation configs
                translation_configs = await db_service.get_translation_configs(guild_id)
                target_channel_id = None
                
                for config in translation_configs:
                    if config.language_code == channel_name:
                        target_channel_id = config.channel_id
                        break
                
                if target_channel_id:
                    channel = self.get_channel(target_channel_id)
                    if channel:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                        self.logger.debug(f"🗑️ Deleted message {message_id} in {channel_name}")
                        
            except discord.NotFound:
                self.logger.warning(f"⚠️ Message {message_id} not found for deletion")
            except Exception as e:
                self.logger.error(f"❌ Failed to delete message {message_id}: {e}")
    
    async def _edit_translated_messages(self, edited_message, mapping, source_language: str, guild_id: int):
        """Edit existing translated messages in place"""
        updated_messages = {}
        
        try:
            if edited_message.content and not self._is_command_or_link(edited_message.content):
                translator = await self._get_translator(guild_id)
                if not translator:
                    return updated_messages
                
                # Get translation configs
                translation_configs = await db_service.get_translation_configs(guild_id)
                target_channels = {config.language_code: config.channel_id for config in translation_configs}
                target_channels.pop(source_language, None)
                
                # Translate to all target languages
                for target_lang, channel_id in target_channels.items():
                    if target_lang in mapping.translated_messages:
                        try:
                            translated_text = await translator.translate(edited_message.content, target_lang)
                            if translated_text:
                                # Get the existing translated message
                                channel = self.get_channel(channel_id)
                                if channel:
                                    message_id = mapping.translated_messages[target_lang]
                                    existing_message = await channel.fetch_message(message_id)
                                    
                                    # Create updated embed
                                    username = edited_message.author.display_name
                                    embed = discord.Embed(
                                        description=translated_text,
                                        color=0x7289DA
                                    )
                                    embed.set_author(
                                        name=username,
                                        icon_url=edited_message.author.display_avatar.url
                                    )
                                    
                                    # Edit the existing message
                                    await existing_message.edit(embed=embed)
                                    updated_messages[target_lang] = message_id
                                    self.logger.debug(f"✏️ Edited message in {target_lang}: {message_id}")
                        
                        except discord.NotFound:
                            self.logger.warning(f"⚠️ Translated message not found for editing: {message_id}")
                        except Exception as e:
                            self.logger.error(f"❌ Failed to edit translated message in {target_lang}: {e}")
        
        except Exception as e:
            self.logger.error(f"❌ Failed to edit translated messages: {e}")
        
        return updated_messages
    
    # Placeholder methods for future features
    
    async def _handle_emoji_sticker_message(self, message, source_language: str, guild_id: int):
        """Handle emoji/sticker only messages"""
        # This will be implemented when emoji/sticker sharing is needed
        pass
    
    async def _handle_attachments(self, message, source_language: str, guild_id: int):
        """Handle message attachments"""
        # This will be implemented when file sharing is needed
        pass