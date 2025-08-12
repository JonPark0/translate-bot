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


class TranslationBot(commands.Bot):
    def __init__(self, rate_limiter: RateLimiter, cost_monitor: CostMonitor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.logger = logging.getLogger(__name__)
        self.rate_limiter = rate_limiter
        self.cost_monitor = cost_monitor
        
        self.translator = GeminiTranslator(os.getenv('GEMINI_API_KEY'))
        self.image_handler = ImageHandler()
        self.emoji_sticker_handler = EmojiStickerHandler()
        
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
        self.logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Monitoring server ID: {self.server_id}")
        self.logger.info(f"Translation channels: {self.channel_ids}")
        
        try:
            synced = await self.tree.sync()
            self.logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")
    
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.guild.id != self.server_id:
            return
        
        if message.channel.id not in self.id_to_channel:
            return
        
        if message.id in self.processing_messages:
            return
        
        self.processing_messages.add(message.id)
        
        try:
            await self._process_message(message)
        finally:
            self.processing_messages.discard(message.id)
    
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
            
            for target_channel, translated_text in translations.items():
                if translated_text:
                    await self._send_translation(
                        message, target_channel, translated_text
                    )
                    
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
                  "`/help` - Show this help message",
            inline=False
        )
        
        await ctx.send(embed=embed)