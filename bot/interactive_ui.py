"""
Interactive UI Components for Key Translation Bot
Discord Components (Buttons, Select Menus, Modals) implementation
"""

import logging
from typing import Optional, Dict, Any, List

import discord
from discord import app_commands
from discord.ext import commands

from database.service import db_service
from database.models import GuildConfig, FeatureType


class FeatureToggleView(discord.ui.View):
    """Interactive view for enabling/disabling features"""
    
    def __init__(self, guild_config: GuildConfig):
        super().__init__(timeout=300)
        self.guild_config = guild_config
        self.logger = logging.getLogger(__name__)
        
        # Add feature toggle buttons
        self.add_item(FeatureToggleButton(
            feature=FeatureType.TRANSLATION,
            enabled=guild_config.is_feature_enabled(FeatureType.TRANSLATION),
            label="🌐 번역",
            row=0
        ))
        
        self.add_item(FeatureToggleButton(
            feature=FeatureType.TTS,
            enabled=guild_config.is_feature_enabled(FeatureType.TTS),
            label="🔊 TTS",
            row=0
        ))
        
        self.add_item(FeatureToggleButton(
            feature=FeatureType.MUSIC,
            enabled=guild_config.is_feature_enabled(FeatureType.MUSIC),
            label="🎵 음악",
            row=0
        ))


class FeatureToggleButton(discord.ui.Button):
    """Button for toggling features on/off"""
    
    def __init__(self, feature: FeatureType, enabled: bool, label: str, row: int):
        self.feature = feature
        self.enabled = enabled
        
        style = discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary
        emoji = "✅" if enabled else "❌"
        
        super().__init__(
            style=style,
            label=f"{emoji} {label}",
            custom_id=f"toggle_{feature.value}",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click"""
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        try:
            # Get current guild config
            guild_config = await db_service.get_guild_config(interaction.guild.id)
            if not guild_config:
                await interaction.response.send_message(
                    "❌ 봇이 설정되지 않았습니다.", 
                    ephemeral=True
                )
                return
            
            # Toggle feature
            if guild_config.is_feature_enabled(self.feature):
                guild_config.disable_feature(self.feature)
                action = "비활성화"
                new_enabled = False
            else:
                guild_config.enable_feature(self.feature)
                action = "활성화"
                new_enabled = True
            
            # Update database
            await db_service.update_guild_config(guild_config)
            
            # Update button appearance
            self.enabled = new_enabled
            self.style = discord.ButtonStyle.success if new_enabled else discord.ButtonStyle.secondary
            emoji = "✅" if new_enabled else "❌"
            feature_name = self.label.split(" ", 1)[1]  # Remove old emoji
            self.label = f"{emoji} {feature_name}"
            
            # Update view and respond
            await interaction.response.edit_message(view=self.view)
            
            # Send confirmation
            await interaction.followup.send(
                f"✅ **{feature_name}** 기능이 {action}되었습니다.",
                ephemeral=True
            )
            
        except Exception as e:
            logging.getLogger(__name__).error(f"❌ Feature toggle failed: {e}")
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {e}",
                ephemeral=True
            )


class LanguageSelectView(discord.ui.View):
    """View for selecting translation languages"""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.selected_languages = []
        self.add_item(LanguageSelectMenu())
        self.add_item(ConfirmLanguageButton())


class LanguageSelectMenu(discord.ui.Select):
    """Select menu for choosing translation languages"""
    
    def __init__(self):
        # Define language options (first 25 due to Discord limit)
        languages = [
            ('ko', '한국어 (Korean)'),
            ('en', 'English'),
            ('ja', '日本語 (Japanese)'),
            ('zh', '中文 (Chinese)'),
            ('ar', 'العربية (Arabic)'),
            ('fr', 'français (French)'),
            ('de', 'Deutsch (German)'),
            ('es', 'español (Spanish)'),
            ('it', 'italiano (Italian)'),
            ('pt', 'português (Portuguese)'),
            ('ru', 'русский (Russian)'),
            ('hi', 'हिन्दी (Hindi)'),
            ('th', 'ไทย (Thai)'),
            ('vi', 'Tiếng Việt (Vietnamese)'),
            ('nl', 'Nederlands (Dutch)'),
            ('pl', 'polski (Polish)'),
            ('tr', 'Türkçe (Turkish)'),
            ('sv', 'svenska (Swedish)'),
            ('da', 'dansk (Danish)'),
            ('no', 'norsk (Norwegian)'),
            ('fi', 'suomi (Finnish)'),
            ('cs', 'čeština (Czech)'),
            ('hu', 'magyar (Hungarian)'),
            ('ro', 'română (Romanian)'),
            ('bg', 'български (Bulgarian)')
        ]
        
        options = [
            discord.SelectOption(
                label=name,
                value=code,
                emoji="🌍"
            )
            for code, name in languages
        ]
        
        super().__init__(
            placeholder="번역에 사용할 언어를 선택하세요 (최대 4개)",
            min_values=2,
            max_values=4,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle language selection"""
        self.view.selected_languages = self.values
        
        selected_names = [option.label for option in self.options if option.value in self.values]
        
        await interaction.response.send_message(
            f"선택된 언어: {', '.join(selected_names)}\n**확인** 버튼을 클릭하여 계속하세요.",
            ephemeral=True
        )


class ConfirmLanguageButton(discord.ui.Button):
    """Button to confirm language selection"""
    
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="✅ 확인",
            custom_id="confirm_languages"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle confirmation"""
        if not self.view.selected_languages:
            await interaction.response.send_message(
                "❌ 먼저 언어를 선택해주세요.",
                ephemeral=True
            )
            return
        
        # Store selected languages (this would integrate with setup process)
        languages_text = ", ".join(self.view.selected_languages)
        await interaction.response.send_message(
            f"✅ 선택된 언어: {languages_text}\n다음 단계로 진행합니다.",
            ephemeral=True
        )


class ChannelSelectView(discord.ui.View):
    """View for selecting channels for each language"""
    
    def __init__(self, languages: List[str]):
        super().__init__(timeout=300)
        self.languages = languages
        self.channel_mappings = {}
        
        for lang in languages:
            self.add_item(ChannelSelectMenu(lang))


class ChannelSelectMenu(discord.ui.Select):
    """Select menu for choosing a channel for a specific language"""
    
    def __init__(self, language: str):
        self.language = language
        
        super().__init__(
            placeholder=f"{language} 채널을 선택하세요",
            custom_id=f"channel_select_{language}",
            channel_types=[discord.ChannelType.text]
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle channel selection"""
        selected_channel = interaction.data['values'][0]
        self.view.channel_mappings[self.language] = selected_channel
        
        await interaction.response.send_message(
            f"✅ {self.language}: <#{selected_channel}>",
            ephemeral=True
        )


class ConfigModal(discord.ui.Modal):
    """Modal for configuration input"""
    
    def __init__(self, title: str, config_type: str):
        super().__init__(title=title)
        self.config_type = config_type
        
        if config_type == "api_key":
            self.add_item(discord.ui.TextInput(
                label="Google AI Studio API Key",
                placeholder="AIza로 시작하는 API 키를 입력하세요",
                style=discord.TextStyle.short,
                max_length=100,
                required=True
            ))
        elif config_type == "tts_config":
            self.add_item(discord.ui.TextInput(
                label="텍스트 채널 ID",
                placeholder="TTS 텍스트가 입력될 채널 ID",
                style=discord.TextStyle.short,
                required=True
            ))
            self.add_item(discord.ui.TextInput(
                label="음성 채널 ID들",
                placeholder="음성이 재생될 채널 ID들 (공백으로 구분)",
                style=discord.TextStyle.short,
                required=True
            ))
            self.add_item(discord.ui.TextInput(
                label="타임아웃 (분)",
                placeholder="10",
                style=discord.TextStyle.short,
                default="10",
                required=False
            ))
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        if self.config_type == "api_key":
            api_key = self.children[0].value
            
            # Validate API key format
            if not api_key.startswith('AIza') or len(api_key) < 30:
                await interaction.response.send_message(
                    "❌ 올바르지 않은 API 키 형식입니다.",
                    ephemeral=True
                )
                return
            
            await interaction.response.send_message(
                "✅ API 키가 저장되었습니다.",
                ephemeral=True
            )
            
        elif self.config_type == "tts_config":
            text_channel = self.children[0].value
            voice_channels = self.children[1].value
            timeout = self.children[2].value or "10"
            
            await interaction.response.send_message(
                f"✅ TTS 설정 완료:\n"
                f"• 텍스트 채널: <#{text_channel}>\n"
                f"• 음성 채널: {voice_channels}\n"
                f"• 타임아웃: {timeout}분",
                ephemeral=True
            )


class StatusView(discord.ui.View):
    """Interactive status view with action buttons"""
    
    def __init__(self, guild_config: GuildConfig):
        super().__init__(timeout=300)
        self.guild_config = guild_config
        
        # Add action buttons
        if guild_config.is_initialized:
            self.add_item(ManageButton())
            self.add_item(ReconfigureButton())
        else:
            self.add_item(InitButton())


class InitButton(discord.ui.Button):
    """Button to start initialization"""
    
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="🚀 초기 설정 시작",
            custom_id="start_init"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Start initialization process"""
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "🚀 초기 설정을 시작합니다. `/init` 명령어를 사용하세요.",
            ephemeral=True
        )


class ManageButton(discord.ui.Button):
    """Button to open management interface"""
    
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="⚙️ 기능 관리",
            custom_id="manage_features"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Open feature management"""
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        try:
            guild_config = await db_service.get_guild_config(interaction.guild.id)
            if not guild_config:
                await interaction.response.send_message(
                    "❌ 설정을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="⚙️ 기능 관리",
                description="버튼을 클릭하여 기능을 활성화/비활성화하세요.",
                color=0x7289DA
            )
            
            view = FeatureToggleView(guild_config)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {e}",
                ephemeral=True
            )


class ReconfigureButton(discord.ui.Button):
    """Button to reconfigure the bot"""
    
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="🔄 재설정",
            custom_id="reconfigure"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Reconfigure the bot"""
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 권한이 필요합니다.", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="⚠️ 재설정 확인",
            description="기존 설정을 모두 삭제하고 다시 설정하시겠습니까?",
            color=0xFF6B6B
        )
        
        view = ReconfigureConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ReconfigureConfirmView(discord.ui.View):
    """Confirmation view for reconfiguration"""
    
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="✅ 확인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm reconfiguration"""
        await interaction.response.send_message(
            "🔄 재설정을 시작합니다. `/init` 명령어를 사용하세요.",
            ephemeral=True
        )
    
    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel reconfiguration"""
        await interaction.response.send_message(
            "❌ 재설정이 취소되었습니다.",
            ephemeral=True
        )


class QuickSetupView(discord.ui.View):
    """Quick setup view with common configurations"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="🌐 번역만 사용", style=discord.ButtonStyle.primary, row=0)
    async def translation_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Quick setup for translation only"""
        modal = ConfigModal("API 키 입력", "api_key")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔊 TTS만 사용", style=discord.ButtonStyle.secondary, row=0)
    async def tts_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Quick setup for TTS only"""
        modal = ConfigModal("TTS 설정", "tts_config")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🎵 음악만 사용", style=discord.ButtonStyle.secondary, row=0)
    async def music_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Quick setup for music only"""
        await interaction.response.send_message(
            "🎵 음악 기능 설정을 시작합니다.",
            ephemeral=True
        )
    
    @discord.ui.button(label="⚙️ 전체 설정", style=discord.ButtonStyle.success, row=1)
    async def full_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Full setup process"""
        await interaction.response.send_message(
            "⚙️ 전체 설정을 시작합니다. `/init` 명령어를 사용하세요.",
            ephemeral=True
        )