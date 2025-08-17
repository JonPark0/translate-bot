"""
Slash Commands for Key Translation Bot
Discord Application Commands (Slash Commands) implementation
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .setup_manager import SetupManager
from database.service import db_service
from database.models import GuildConfig, FeatureType


class SlashCommands(commands.Cog):
    """Slash commands for the translation bot"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.setup_manager = SetupManager(bot)
    
    async def _get_guild_config(self, guild_id: int) -> Optional[GuildConfig]:
        """Get guild configuration"""
        try:
            return await db_service.get_guild_config(guild_id)
        except Exception as e:
            self.logger.error(f"❌ Failed to get guild config for {guild_id}: {e}")
            return None
    
    @app_commands.command(name="init", description="봇 초기 설정을 시작합니다 (관리자 권한 필요)")
    @app_commands.describe()
    async def init_command(self, interaction: discord.Interaction):
        """Initialize bot configuration for this server"""
        # Check permissions
        if not (interaction.user.guild_permissions.administrator or 
                interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message(
                "❌ 봇 설정 권한이 없습니다. 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        # Create a mock context for the setup manager
        class MockContext:
            def __init__(self, interaction):
                self.guild = interaction.guild
                self.author = interaction.user
                self.channel = interaction.channel
                self.send = interaction.followup.send
        
        # Defer the response since setup might take time
        await interaction.response.defer()
        
        # Create mock context and start setup
        mock_ctx = MockContext(interaction)
        success = await self.setup_manager.start_setup(mock_ctx)
        
        if success:
            await interaction.followup.send("🚀 설정 프로세스가 시작되었습니다!")
        else:
            await interaction.followup.send("❌ 설정을 시작할 수 없습니다.")
    
    @app_commands.command(name="status", description="현재 서버의 봇 설정 상태를 확인합니다")
    async def status_command(self, interaction: discord.Interaction):
        """Show bot status for this server"""
        guild_config = await self._get_guild_config(interaction.guild.id)
        
        if not guild_config:
            embed = discord.Embed(
                title="❌ 봇이 설정되지 않음",
                description="`/init` 명령어를 사용하여 봇을 설정해주세요.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"📊 {interaction.guild.name} 봇 상태",
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
            try:
                translation_configs = await db_service.get_translation_configs(interaction.guild.id)
                if translation_configs:
                    channel_info = []
                    for config in translation_configs:
                        channel_info.append(f"{config.language_name}: <#{config.channel_id}>")
                    
                    embed.add_field(
                        name="번역 채널",
                        value="\n".join(channel_info),
                        inline=False
                    )
            except Exception as e:
                self.logger.error(f"❌ Failed to get translation configs: {e}")
        
        embed.add_field(
            name="초기화 상태",
            value="✅ 완료" if guild_config.is_initialized else "❌ 미완료",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="keyhelp", description="봇 사용법과 명령어를 보여줍니다")
    async def help_command(self, interaction: discord.Interaction):
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
            name="📚 도움말",
            value="`/keyhelp` - 이 도움말 메시지 표시",
            inline=False
        )
        
        embed.add_field(
            name="🔧 관리자 명령어",
            value="`/test_logging` - 로깅 레벨 테스트 (관리자 전용)",
            inline=False
        )
        
        guild_config = await self._get_guild_config(interaction.guild.id)
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
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="test_logging", description="모든 로깅 레벨을 테스트합니다 (관리자 전용)")
    @app_commands.describe()
    async def test_logging_command(self, interaction: discord.Interaction):
        """Test all logging levels (Admin only)"""
        # Check admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        self.logger.debug("🔍 DEBUG: Test debug message")
        self.logger.info("ℹ️ INFO: Test info message")
        self.logger.warning("⚠️ WARNING: Test warning message")
        self.logger.error("❌ ERROR: Test error message")
        self.logger.critical("🚨 CRITICAL: Test critical message")
        
        await interaction.response.send_message(
            "✅ 모든 로깅 레벨 테스트 완료. 로그 파일을 확인하세요.",
            ephemeral=True
        )
    
    @app_commands.command(name="config", description="봇 설정을 관리합니다 (관리자 전용)")
    @app_commands.describe(
        action="수행할 작업",
        feature="관리할 기능"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="활성화", value="enable"),
        app_commands.Choice(name="비활성화", value="disable"),
        app_commands.Choice(name="상태 확인", value="check")
    ])
    @app_commands.choices(feature=[
        app_commands.Choice(name="번역", value="translation"),
        app_commands.Choice(name="TTS", value="tts"),
        app_commands.Choice(name="음악", value="music")
    ])
    async def config_command(self, interaction: discord.Interaction, 
                           action: app_commands.Choice[str],
                           feature: app_commands.Choice[str]):
        """Manage bot configuration (Admin only)"""
        # Check admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        guild_config = await self._get_guild_config(interaction.guild.id)
        if not guild_config:
            await interaction.response.send_message(
                "❌ 봇이 설정되지 않았습니다. `/init` 명령어로 먼저 설정해주세요.",
                ephemeral=True
            )
            return
        
        feature_type = FeatureType(feature.value)
        feature_name = feature.name
        
        if action.value == "check":
            status = "활성화됨" if guild_config.is_feature_enabled(feature_type) else "비활성화됨"
            await interaction.response.send_message(
                f"📊 **{feature_name}** 기능: {status}",
                ephemeral=True
            )
            return
        
        try:
            if action.value == "enable":
                guild_config.enable_feature(feature_type)
                await db_service.update_guild_config(guild_config)
                await interaction.response.send_message(
                    f"✅ **{feature_name}** 기능이 활성화되었습니다.",
                    ephemeral=True
                )
            elif action.value == "disable":
                guild_config.disable_feature(feature_type)
                await db_service.update_guild_config(guild_config)
                await interaction.response.send_message(
                    f"❌ **{feature_name}** 기능이 비활성화되었습니다.",
                    ephemeral=True
                )
        
        except Exception as e:
            self.logger.error(f"❌ Failed to update guild config: {e}")
            await interaction.response.send_message(
                f"❌ 설정 업데이트 중 오류가 발생했습니다: {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(SlashCommands(bot))