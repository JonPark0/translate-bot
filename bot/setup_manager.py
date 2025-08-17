"""
Setup Manager for Key Translation Bot
Handles initial guild configuration through interactive prompts
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field

import discord
from discord.ext import commands

from database.service import db_service
from database.models import GuildConfig, TranslationConfig, FeatureType


class SetupState(Enum):
    """Setup process states"""
    NOT_STARTED = "not_started"
    API_KEY_CHECK = "api_key_check"
    API_KEY_INPUT = "api_key_input"
    FEATURE_SELECTION = "feature_selection"
    TRANSLATION_LANGUAGES = "translation_languages"
    TRANSLATION_CHANNELS = "translation_channels"
    TTS_CONFIG = "tts_config"
    MUSIC_CONFIG = "music_config"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class SetupSession:
    """Represents an active setup session"""
    guild_id: int
    user_id: int
    channel_id: int
    state: SetupState = SetupState.NOT_STARTED
    data: Dict[str, Any] = field(default_factory=dict)
    timeout_task: Optional[asyncio.Task] = None
    last_message: Optional[discord.Message] = None


class SetupManager:
    """Manages guild setup processes"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.active_sessions: Dict[int, SetupSession] = {}  # guild_id -> SetupSession
        self.session_timeout = 600  # 10 minutes
        
        # Supported languages mapping
        self.supported_languages = {
            'ko': '한국어 (Korean)',
            'en': 'English',
            'ja': '日本語 (Japanese)',
            'zh': '中文 (Chinese)',
            'ar': 'العربية (Arabic)',
            'fr': 'français (French)',
            'de': 'Deutsch (German)',
            'es': 'español (Spanish)',
            'it': 'italiano (Italian)',
            'pt': 'português (Portuguese)',
            'ru': 'русский (Russian)',
            'hi': 'हिन्दी (Hindi)',
            'th': 'ไทย (Thai)',
            'vi': 'Tiếng Việt (Vietnamese)'
        }
    
    async def start_setup(self, ctx) -> bool:
        """Start the setup process for a guild"""
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        
        # Check if user has permission to setup
        if not (ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild):
            await ctx.send("❌ 봇 설정 권한이 없습니다. 관리자 권한이 필요합니다.")
            return False
        
        # Check if setup is already in progress
        if guild_id in self.active_sessions:
            await ctx.send("⚠️ 이미 설정이 진행 중입니다. 기존 설정을 완료하거나 취소해주세요.")
            return False
        
        # Check if guild is already initialized
        if await db_service.is_guild_initialized(guild_id):
            embed = discord.Embed(
                title="🔧 봇 재설정",
                description="이 서버는 이미 설정되어 있습니다. 기존 설정을 덮어쓰시겠습니까?",
                color=0xFFA500
            )
            embed.add_field(
                name="선택 옵션",
                value="✅ `yes` - 새로 설정\n❌ `no` - 취소",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            try:
                response = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no'],
                    timeout=30
                )
                
                if response.content.lower() == 'no':
                    await ctx.send("❌ 설정이 취소되었습니다.")
                    return False
                    
            except asyncio.TimeoutError:
                await ctx.send("⏰ 응답 시간이 초과되었습니다. 설정이 취소되었습니다.")
                return False
        
        # Create setup session
        session = SetupSession(
            guild_id=guild_id,
            user_id=user_id,
            channel_id=ctx.channel.id,
            state=SetupState.API_KEY_CHECK
        )
        
        self.active_sessions[guild_id] = session
        
        # Start timeout task
        session.timeout_task = asyncio.create_task(self._session_timeout(guild_id))
        
        self.logger.info(f"🚀 Started setup for guild {guild_id} by user {user_id}")
        
        # Start the setup process
        await self._process_api_key_check(ctx, session)
        return True
    
    async def _session_timeout(self, guild_id: int):
        """Handle session timeout"""
        await asyncio.sleep(self.session_timeout)
        
        if guild_id in self.active_sessions:
            session = self.active_sessions[guild_id]
            await self._cancel_setup(guild_id, "⏰ 설정 시간이 초과되었습니다.")
    
    async def _cancel_setup(self, guild_id: int, message: str = "❌ 설정이 취소되었습니다."):
        """Cancel an active setup session"""
        if guild_id in self.active_sessions:
            session = self.active_sessions[guild_id]
            
            # Cancel timeout task
            if session.timeout_task:
                session.timeout_task.cancel()
            
            # Send cancellation message
            try:
                channel = self.bot.get_channel(session.channel_id)
                if channel:
                    await channel.send(message)
            except:
                pass
            
            # Remove session
            del self.active_sessions[guild_id]
            self.logger.info(f"❌ Setup cancelled for guild {guild_id}")
    
    async def handle_setup_response(self, message: discord.Message) -> bool:
        """Handle user responses during setup"""
        guild_id = message.guild.id
        
        if guild_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[guild_id]
        
        # Check if it's the right user and channel
        if message.author.id != session.user_id or message.channel.id != session.channel_id:
            return False
        
        # Process based on current state
        try:
            if session.state == SetupState.API_KEY_INPUT:
                await self._process_api_key_input(message, session)
            elif session.state == SetupState.FEATURE_SELECTION:
                await self._process_feature_selection(message, session)
            elif session.state == SetupState.TRANSLATION_LANGUAGES:
                await self._process_translation_languages(message, session)
            elif session.state == SetupState.TRANSLATION_CHANNELS:
                await self._process_translation_channels(message, session)
            elif session.state == SetupState.TTS_CONFIG:
                await self._process_tts_config(message, session)
            elif session.state == SetupState.MUSIC_CONFIG:
                await self._process_music_config(message, session)
            elif session.state == SetupState.CONFIRMATION:
                await self._process_confirmation(message, session)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error processing setup response: {e}")
            await message.channel.send(f"❌ 설정 처리 중 오류가 발생했습니다: {e}")
            await self._cancel_setup(guild_id)
            return False
    
    async def _process_api_key_check(self, ctx: commands.Context, session: SetupSession):
        """Step 1: Check if user has API key"""
        embed = discord.Embed(
            title="🔑 Google AI Studio API 키 설정",
            description="케이 봇을 사용하기 위해 Google AI Studio API 키가 필요합니다.",
            color=0x4285F4
        )
        
        embed.add_field(
            name="1단계: API 키 확인",
            value="기존에 보유한 Google AI Studio API 키가 있나요?",
            inline=False
        )
        
        embed.add_field(
            name="선택 옵션",
            value="✅ `yes` - 이미 API 키가 있음\n❌ `no` - API 키 발급 안내 필요",
            inline=False
        )
        
        session.last_message = await ctx.send(embed=embed)
        
        # Wait for response
        try:
            response = await self.bot.wait_for(
                'message',
                check=lambda m: m.author.id == session.user_id and m.channel.id == session.channel_id and m.content.lower() in ['yes', 'no'],
                timeout=120
            )
            
            if response.content.lower() == 'yes':
                session.state = SetupState.API_KEY_INPUT
                await self._process_api_key_input_prompt(ctx, session)
            else:
                await self._show_api_key_guide(ctx, session)
                
        except asyncio.TimeoutError:
            await self._cancel_setup(session.guild_id, "⏰ 응답 시간이 초과되었습니다.")
    
    async def _show_api_key_guide(self, ctx: commands.Context, session: SetupSession):
        """Show API key generation guide"""
        embed = discord.Embed(
            title="🔗 Google AI Studio API 키 발급 안내",
            description="다음 단계를 따라 API 키를 발급받으세요:",
            color=0x4285F4
        )
        
        embed.add_field(
            name="1. Google Cloud Project 생성",
            value="[Google Cloud Console](https://console.cloud.google.com/projectcreate)에서 새 프로젝트를 생성하세요.",
            inline=False
        )
        
        embed.add_field(
            name="2. API 키 발급",
            value="[Google AI Studio](https://aistudio.google.com/app/apikey)에서 API 키를 발급받으세요.",
            inline=False
        )
        
        embed.add_field(
            name="3. API 키 입력",
            value="발급받은 API 키를 준비한 후 `ready`를 입력하세요.",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
        # Wait for ready
        try:
            await self.bot.wait_for(
                'message',
                check=lambda m: m.author.id == session.user_id and m.channel.id == session.channel_id and m.content.lower() == 'ready',
                timeout=300  # 5 minutes for API key generation
            )
            
            session.state = SetupState.API_KEY_INPUT
            await self._process_api_key_input_prompt(ctx, session)
            
        except asyncio.TimeoutError:
            await self._cancel_setup(session.guild_id, "⏰ API 키 발급 대기 시간이 초과되었습니다.")
    
    async def _process_api_key_input_prompt(self, ctx: commands.Context, session: SetupSession):
        """Prompt for API key input"""
        embed = discord.Embed(
            title="🔑 API 키 입력",
            description="Google AI Studio에서 발급받은 API 키를 입력해주세요.",
            color=0x00FF00
        )
        
        embed.add_field(
            name="⚠️ 보안 주의사항",
            value="API 키는 다른 사용자가 볼 수 없도록 **개인 메시지(DM)**로 전송하거나, 입력 후 즉시 메시지를 삭제하세요.",
            inline=False
        )
        
        embed.add_field(
            name="입력 형식",
            value="`AIza...` 형태의 API 키를 입력하세요.",
            inline=False
        )
        
        await ctx.send(embed=embed)
        session.state = SetupState.API_KEY_INPUT
    
    async def _process_api_key_input(self, message: discord.Message, session: SetupSession):
        """Process API key input"""
        api_key = message.content.strip()
        
        # Validate API key format
        if not api_key.startswith('AIza') or len(api_key) < 30:
            await message.channel.send("❌ 올바르지 않은 API 키 형식입니다. `AIza`로 시작하는 키를 입력해주세요.")
            return
        
        # Try to delete the message for security
        try:
            await message.delete()
        except:
            pass
        
        session.data['api_key'] = api_key
        session.state = SetupState.FEATURE_SELECTION
        
        await self._process_feature_selection_prompt(message, session)
    
    async def _process_feature_selection_prompt(self, message: discord.Message, session: SetupSession):
        """Prompt for feature selection"""
        embed = discord.Embed(
            title="🎯 기능 선택",
            description="사용할 기능을 선택해주세요. 여러 기능을 선택할 수 있습니다.",
            color=0xFF6B6B
        )
        
        embed.add_field(
            name="📝 채팅 채널 다국어 동시 번역",
            value="`translation` - 여러 언어 채널 간 실시간 번역",
            inline=False
        )
        
        embed.add_field(
            name="🔊 음성채팅 TTS",
            value="`tts` - 텍스트를 음성으로 변환하여 음성 채널에서 재생",
            inline=False
        )
        
        embed.add_field(
            name="🎵 음악 재생",
            value="`music` - YouTube, SoundCloud 등의 음악 재생",
            inline=False
        )
        
        embed.add_field(
            name="입력 방법",
            value="원하는 기능을 쉼표로 구분하여 입력하세요.\n예: `translation, tts` 또는 `translation, music`",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        session.state = SetupState.FEATURE_SELECTION
    
    async def _process_feature_selection(self, message: discord.Message, session: SetupSession):
        """Process feature selection"""
        features_input = message.content.lower().replace(' ', '').split(',')
        valid_features = ['translation', 'tts', 'music']
        
        selected_features = []
        for feature in features_input:
            if feature in valid_features:
                selected_features.append(feature)
        
        if not selected_features:
            await message.channel.send("❌ 올바른 기능을 선택해주세요. `translation`, `tts`, `music` 중에서 선택하세요.")
            return
        
        session.data['features'] = selected_features
        
        # Move to next appropriate step
        if 'translation' in selected_features:
            session.state = SetupState.TRANSLATION_LANGUAGES
            await self._process_translation_languages_prompt(message, session)
        elif 'tts' in selected_features:
            session.state = SetupState.TTS_CONFIG
            await self._process_tts_config_prompt(message, session)
        elif 'music' in selected_features:
            session.state = SetupState.MUSIC_CONFIG
            await self._process_music_config_prompt(message, session)
        else:
            session.state = SetupState.CONFIRMATION
            await self._process_confirmation_prompt(message, session)
    
    async def _process_translation_languages_prompt(self, message: discord.Message, session: SetupSession):
        """Prompt for translation language selection"""
        embed = discord.Embed(
            title="🌍 번역 언어 선택",
            description="동시 번역에 사용할 언어를 선택하세요. (최대 4개)",
            color=0x9B59B6
        )
        
        # Show available languages in groups
        lang_list = []
        for code, name in list(self.supported_languages.items())[:14]:  # Show first 14
            lang_list.append(f"`{code}` - {name}")
        
        embed.add_field(
            name="지원 언어",
            value="\n".join(lang_list),
            inline=False
        )
        
        embed.add_field(
            name="입력 방법",
            value="언어 코드를 쉼표로 구분하여 입력하세요.\n예: `ko, en, ja, zh`",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        session.state = SetupState.TRANSLATION_LANGUAGES
    
    async def _process_translation_languages(self, message: discord.Message, session: SetupSession):
        """Process translation language selection"""
        lang_codes = [code.strip() for code in message.content.lower().split(',')]
        
        if len(lang_codes) > 4:
            await message.channel.send("❌ 최대 4개의 언어만 선택할 수 있습니다.")
            return
        
        valid_languages = []
        for code in lang_codes:
            if code in self.supported_languages:
                valid_languages.append({
                    'code': code,
                    'name': self.supported_languages[code]
                })
        
        if len(valid_languages) < 2:
            await message.channel.send("❌ 최소 2개의 유효한 언어를 선택해주세요.")
            return
        
        session.data['translation_languages'] = valid_languages
        session.state = SetupState.TRANSLATION_CHANNELS
        
        await self._process_translation_channels_prompt(message, session)
    
    async def _process_translation_channels_prompt(self, message: discord.Message, session: SetupSession):
        """Prompt for translation channel setup"""
        languages = session.data['translation_languages']
        
        embed = discord.Embed(
            title="📺 번역 채널 설정",
            description="각 언어별로 사용할 채널을 지정해주세요.",
            color=0x3498DB
        )
        
        channel_info = []
        for lang in languages:
            channel_info.append(f"**{lang['name']}** ({lang['code']})")
        
        embed.add_field(
            name="설정할 언어",
            value="\n".join(channel_info),
            inline=False
        )
        
        embed.add_field(
            name="입력 방법",
            value="채널 ID를 순서대로 공백으로 구분하여 입력하세요.\n예: `123456789 987654321 555666777 111222333`\n\n**채널 ID 확인 방법**: 개발자 모드 활성화 후 채널 우클릭 → ID 복사",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        session.state = SetupState.TRANSLATION_CHANNELS
    
    async def _process_translation_channels(self, message: discord.Message, session: SetupSession):
        """Process translation channel setup"""
        channel_ids = message.content.strip().split()
        languages = session.data['translation_languages']
        
        if len(channel_ids) != len(languages):
            await message.channel.send(f"❌ {len(languages)}개의 채널 ID가 필요합니다.")
            return
        
        # Validate channel IDs
        channel_mapping = {}
        for i, (lang, channel_id) in enumerate(zip(languages, channel_ids)):
            try:
                channel_id = int(channel_id)
                channel = self.bot.get_channel(channel_id)
                if not channel or channel.guild.id != session.guild_id:
                    await message.channel.send(f"❌ 채널 ID {channel_id}가 이 서버에 없습니다.")
                    return
                
                channel_mapping[lang['code']] = {
                    'channel_id': channel_id,
                    'channel_name': channel.name
                }
                
            except ValueError:
                await message.channel.send(f"❌ 올바르지 않은 채널 ID: {channel_id}")
                return
        
        session.data['translation_channels'] = channel_mapping
        
        # Continue to next feature or confirmation
        if 'tts' in session.data['features']:
            session.state = SetupState.TTS_CONFIG
            await self._process_tts_config_prompt(message, session)
        elif 'music' in session.data['features']:
            session.state = SetupState.MUSIC_CONFIG
            await self._process_music_config_prompt(message, session)
        else:
            session.state = SetupState.CONFIRMATION
            await self._process_confirmation_prompt(message, session)
    
    async def _process_tts_config_prompt(self, message: discord.Message, session: SetupSession):
        """Prompt for TTS configuration"""
        embed = discord.Embed(
            title="🔊 TTS 설정",
            description="음성 채팅 TTS 기능을 설정합니다.",
            color=0xE67E22
        )
        
        embed.add_field(
            name="1. 텍스트 채널 ID",
            value="TTS로 읽을 텍스트가 입력될 채널의 ID를 입력하세요.",
            inline=False
        )
        
        embed.add_field(
            name="2. 음성 채널 ID(들)",
            value="TTS 음성이 재생될 음성 채널 ID(들)을 공백으로 구분하여 입력하세요.",
            inline=False
        )
        
        embed.add_field(
            name="3. 타임아웃 (분)",
            value="마지막 텍스트 입력 후 음성 채널에서 나갈 시간 (기본: 10분)",
            inline=False
        )
        
        embed.add_field(
            name="입력 형식",
            value="`텍스트채널ID 음성채널ID1 음성채널ID2 타임아웃분`\n예: `123456789 987654321 555666777 10`",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        session.state = SetupState.TTS_CONFIG
    
    async def _process_tts_config(self, message: discord.Message, session: SetupSession):
        """Process TTS configuration"""
        parts = message.content.strip().split()
        
        if len(parts) < 3:
            await message.channel.send("❌ 최소 3개의 값이 필요합니다: 텍스트채널ID 음성채널ID 타임아웃분")
            return
        
        try:
            text_channel_id = int(parts[0])
            voice_channel_ids = [int(parts[i]) for i in range(1, len(parts)-1)]
            timeout_minutes = int(parts[-1])
            
            # Validate channels
            text_channel = self.bot.get_channel(text_channel_id)
            if not text_channel or text_channel.guild.id != session.guild_id:
                await message.channel.send(f"❌ 텍스트 채널 {text_channel_id}가 이 서버에 없습니다.")
                return
            
            for voice_id in voice_channel_ids:
                voice_channel = self.bot.get_channel(voice_id)
                if not voice_channel or voice_channel.guild.id != session.guild_id:
                    await message.channel.send(f"❌ 음성 채널 {voice_id}가 이 서버에 없습니다.")
                    return
            
            session.data['tts_config'] = {
                'text_channel_id': text_channel_id,
                'voice_channel_ids': voice_channel_ids,
                'timeout_minutes': timeout_minutes
            }
            
            # Continue to next feature or confirmation
            if 'music' in session.data['features']:
                session.state = SetupState.MUSIC_CONFIG
                await self._process_music_config_prompt(message, session)
            else:
                session.state = SetupState.CONFIRMATION
                await self._process_confirmation_prompt(message, session)
                
        except ValueError:
            await message.channel.send("❌ 올바르지 않은 ID 형식입니다. 숫자로 입력해주세요.")
    
    async def _process_music_config_prompt(self, message: discord.Message, session: SetupSession):
        """Prompt for music configuration"""
        embed = discord.Embed(
            title="🎵 음악 재생 설정",
            description="음악 재생 기능을 설정합니다.",
            color=0x1DB954
        )
        
        embed.add_field(
            name="1. 명령어 채널 (선택사항)",
            value="음악 명령어를 받을 특정 채널 ID (비워두면 모든 채널에서 가능)",
            inline=False
        )
        
        embed.add_field(
            name="2. 음성 채널/카테고리 (선택사항)",
            value="기본 음성 채널 ID 또는 카테고리 ID (비워두면 사용자가 있는 채널 자동 감지)",
            inline=False
        )
        
        embed.add_field(
            name="입력 형식",
            value="`명령어채널ID 음성채널ID`\n비워두려면 `none`으로 입력\n예: `123456789 987654321` 또는 `none none`",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        session.state = SetupState.MUSIC_CONFIG
    
    async def _process_music_config(self, message: discord.Message, session: SetupSession):
        """Process music configuration"""
        parts = message.content.strip().split()
        
        if len(parts) != 2:
            await message.channel.send("❌ 2개의 값이 필요합니다: 명령어채널ID 음성채널ID (사용안함은 none)")
            return
        
        try:
            command_channel_id = None if parts[0].lower() == 'none' else int(parts[0])
            voice_channel_id = None if parts[1].lower() == 'none' else int(parts[1])
            
            # Validate channels if provided
            if command_channel_id:
                command_channel = self.bot.get_channel(command_channel_id)
                if not command_channel or command_channel.guild.id != session.guild_id:
                    await message.channel.send(f"❌ 명령어 채널 {command_channel_id}가 이 서버에 없습니다.")
                    return
            
            if voice_channel_id:
                voice_channel = self.bot.get_channel(voice_channel_id)
                if not voice_channel or voice_channel.guild.id != session.guild_id:
                    await message.channel.send(f"❌ 음성 채널 {voice_channel_id}가 이 서버에 없습니다.")
                    return
            
            session.data['music_config'] = {
                'command_channel_id': command_channel_id,
                'voice_channel_id': voice_channel_id
            }
            
            session.state = SetupState.CONFIRMATION
            await self._process_confirmation_prompt(message, session)
            
        except ValueError:
            await message.channel.send("❌ 올바르지 않은 채널 ID입니다. 숫자로 입력하거나 `none`을 사용하세요.")
    
    async def _process_confirmation_prompt(self, message: discord.Message, session: SetupSession):
        """Show configuration summary and ask for confirmation"""
        embed = discord.Embed(
            title="✅ 설정 확인",
            description="다음 설정으로 봇을 구성합니다. 확인해주세요.",
            color=0x00FF00
        )
        
        # Show selected features
        features = session.data['features']
        embed.add_field(
            name="선택된 기능",
            value=", ".join(features),
            inline=False
        )
        
        # Show translation config if selected
        if 'translation' in features:
            translation_info = []
            for lang_code, channel_info in session.data['translation_channels'].items():
                translation_info.append(f"{self.supported_languages[lang_code]}: <#{channel_info['channel_id']}>")
            
            embed.add_field(
                name="번역 채널",
                value="\n".join(translation_info),
                inline=False
            )
        
        # Show TTS config if selected
        if 'tts' in features:
            tts_config = session.data['tts_config']
            tts_info = f"텍스트: <#{tts_config['text_channel_id']}>\n"
            tts_info += f"음성: {', '.join([f'<#{vid}>' for vid in tts_config['voice_channel_ids']])}\n"
            tts_info += f"타임아웃: {tts_config['timeout_minutes']}분"
            
            embed.add_field(
                name="TTS 설정",
                value=tts_info,
                inline=False
            )
        
        # Show music config if selected
        if 'music' in features:
            music_config = session.data['music_config']
            command_channel_text = '모든 채널' if not music_config['command_channel_id'] else f"<#{music_config['command_channel_id']}>"
            voice_channel_text = '자동 감지' if not music_config['voice_channel_id'] else f"<#{music_config['voice_channel_id']}>"
            music_info = f"명령어 채널: {command_channel_text}\n"
            music_info += f"음성 채널: {voice_channel_text}"
            
            embed.add_field(
                name="음악 설정",
                value=music_info,
                inline=False
            )
        
        embed.add_field(
            name="확인",
            value="✅ `confirm` - 설정 적용\n❌ `cancel` - 설정 취소",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        session.state = SetupState.CONFIRMATION
    
    async def _process_confirmation(self, message: discord.Message, session: SetupSession):
        """Process final confirmation"""
        response = message.content.lower().strip()
        
        if response == 'confirm':
            await self._save_configuration(message, session)
        elif response == 'cancel':
            await self._cancel_setup(session.guild_id, "❌ 설정이 취소되었습니다.")
        else:
            await message.channel.send("❌ `confirm` 또는 `cancel`을 입력해주세요.")
    
    async def _save_configuration(self, message: discord.Message, session: SetupSession):
        """Save the configuration to database"""
        try:
            guild = message.guild
            
            # Prepare guild config
            guild_config = GuildConfig(
                guild_id=session.guild_id,
                guild_name=guild.name,
                api_key=session.data['api_key'],
                features={
                    'translation': 'translation' in session.data['features'],
                    'tts': 'tts' in session.data['features'],
                    'music': 'music' in session.data['features']
                },
                channels=self._prepare_channels_data(session),
                settings=self._prepare_settings_data(session),
                is_initialized=True
            )
            
            # Save to database
            if await db_service.guild_exists(session.guild_id):
                await db_service.update_guild_config(guild_config)
            else:
                await db_service.create_guild_config(guild_config)
            
            # Save translation configurations
            if 'translation' in session.data['features']:
                await self._save_translation_configs(session)
            
            # Create final success message
            embed = discord.Embed(
                title="🎉 설정 완료!",
                description="케이 봇이 성공적으로 설정되었습니다!",
                color=0x00FF00
            )
            
            embed.add_field(
                name="다음 단계",
                value="이제 봇의 모든 기능을 사용할 수 있습니다. `/keyhelp` 명령어로 사용 가능한 명령어를 확인하세요.",
                inline=False
            )
            
            await message.channel.send(embed=embed)
            
            # Clean up session
            if session.timeout_task:
                session.timeout_task.cancel()
            del self.active_sessions[session.guild_id]
            
            self.logger.info(f"✅ Setup completed for guild {session.guild_id}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save configuration: {e}")
            await message.channel.send(f"❌ 설정 저장 중 오류가 발생했습니다: {e}")
            await self._cancel_setup(session.guild_id)
    
    def _prepare_channels_data(self, session: SetupSession) -> Dict[str, Any]:
        """Prepare channels data for storage"""
        channels = {}
        
        if 'translation_channels' in session.data:
            channels['translation'] = session.data['translation_channels']
        
        if 'tts_config' in session.data:
            channels['tts'] = session.data['tts_config']
        
        if 'music_config' in session.data:
            channels['music'] = session.data['music_config']
        
        return channels
    
    def _prepare_settings_data(self, session: SetupSession) -> Dict[str, Any]:
        """Prepare settings data for storage"""
        settings = {
            'rate_limit_per_minute': 30,
            'max_daily_requests': 1000,
            'max_monthly_cost_usd': 10.0,
            'cost_alert_threshold_usd': 8.0
        }
        
        if 'tts_config' in session.data:
            settings['tts_timeout_minutes'] = session.data['tts_config']['timeout_minutes']
        
        return settings
    
    async def _save_translation_configs(self, session: SetupSession):
        """Save translation configurations"""
        if 'translation_languages' not in session.data or 'translation_channels' not in session.data:
            return
        
        for lang in session.data['translation_languages']:
            lang_code = lang['code']
            if lang_code in session.data['translation_channels']:
                channel_info = session.data['translation_channels'][lang_code]
                
                config = TranslationConfig(
                    id=None,
                    guild_id=session.guild_id,
                    language_code=lang_code,
                    language_name=lang['name'],
                    channel_id=channel_info['channel_id'],
                    is_active=True
                )
                
                await db_service.create_translation_config(config)