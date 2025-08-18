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
from .interactive_ui import (
    StatusView, FeatureToggleView, QuickSetupView, 
    ConfigModal, LanguageSelectView
)


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
        """Show bot status for this server with interactive controls"""
        guild_config = await self._get_guild_config(interaction.guild.id)
        
        if not guild_config:
            embed = discord.Embed(
                title="❌ 봇이 설정되지 않음",
                description="아래 버튼을 클릭하여 빠른 설정을 시작하거나 `/init` 명령어를 사용하세요.",
                color=0xFF0000
            )
            view = QuickSetupView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
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
        
        # Add interactive status view
        view = StatusView(guild_config)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
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
    
    @app_commands.command(name="manage", description="봇 기능을 대화형으로 관리합니다 (관리자 전용)")
    async def manage_command(self, interaction: discord.Interaction):
        """Interactive feature management"""
        # Check admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        try:
            guild_config = await self._get_guild_config(interaction.guild.id)
            if not guild_config:
                embed = discord.Embed(
                    title="❌ 봇이 설정되지 않음",
                    description="먼저 `/init` 명령어로 봇을 설정해주세요.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title="⚙️ 봇 기능 관리",
                description="버튼을 클릭하여 기능을 활성화/비활성화하세요.",
                color=0x7289DA
            )
            
            embed.add_field(
                name="현재 상태",
                value=f"🌐 번역: {'✅' if guild_config.is_feature_enabled(FeatureType.TRANSLATION) else '❌'}\n"
                      f"🔊 TTS: {'✅' if guild_config.is_feature_enabled(FeatureType.TTS) else '❌'}\n"
                      f"🎵 음악: {'✅' if guild_config.is_feature_enabled(FeatureType.MUSIC) else '❌'}",
                inline=False
            )
            
            view = FeatureToggleView(guild_config)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load management interface: {e}")
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {e}",
                ephemeral=True
            )
    
    @app_commands.command(name="quick_setup", description="빠른 설정으로 일반적인 구성을 쉽게 설정합니다")
    async def quick_setup_command(self, interaction: discord.Interaction):
        """Quick setup with common configurations"""
        # Check admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🚀 빠른 설정",
            description="사용하고자 하는 기능을 선택하세요:",
            color=0x00FF7F
        )
        
        embed.add_field(
            name="설정 옵션",
            value="🌐 **번역만 사용** - 다국어 번역 기능만 활성화\n"
                  "🔊 **TTS만 사용** - 텍스트 음성 변환만 활성화\n"
                  "🎵 **음악만 사용** - 음악 재생만 활성화\n"
                  "⚙️ **전체 설정** - 모든 기능을 단계별로 설정",
            inline=False
        )
        
        view = QuickSetupView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="settings", description="고급 설정을 관리합니다 (관리자 전용)")
    @app_commands.describe(
        setting="변경할 설정",
        value="새로운 값"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="API 키", value="api_key"),
        app_commands.Choice(name="TTS 타임아웃", value="tts_timeout"),
        app_commands.Choice(name="최대 큐 크기", value="max_queue"),
        app_commands.Choice(name="속도 제한", value="rate_limit")
    ])
    async def settings_command(self, interaction: discord.Interaction,
                             setting: app_commands.Choice[str],
                             value: str = None):
        """Advanced settings management"""
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
        
        if setting.value == "api_key":
            if not value:
                # Show modal for secure API key input
                modal = ConfigModal("API 키 변경", "api_key")
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message(
                    "⚠️ 보안을 위해 API 키는 모달을 통해 입력해주세요.",
                    ephemeral=True
                )
        else:
            if not value:
                # Show current value
                if not guild_config.settings or not isinstance(guild_config.settings, dict):
                    current_value = "설정되지 않음"
                else:
                    current_value = guild_config.settings.get(setting.value, "설정되지 않음")
                await interaction.response.send_message(
                    f"📊 현재 **{setting.name}**: {current_value}",
                    ephemeral=True
                )
            else:
                # Update setting
                try:
                    if not guild_config.settings or not isinstance(guild_config.settings, dict):
                        guild_config.settings = {
                            "tts_timeout_minutes": 10,
                            "max_queue_size": 100,
                            "rate_limit_per_minute": 30,
                            "max_daily_requests": 1000,
                            "max_monthly_cost_usd": 10.0,
                            "cost_alert_threshold_usd": 8.0
                        }
                    guild_config.settings[setting.value] = value
                    await db_service.update_guild_config(guild_config)
                    
                    await interaction.response.send_message(
                        f"✅ **{setting.name}**이(가) `{value}`로 변경되었습니다.",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ 설정 변경 중 오류가 발생했습니다: {e}",
                        ephemeral=True
                    )


async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(SlashCommands(bot))