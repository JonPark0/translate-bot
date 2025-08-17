"""
Database models for Key Translation Bot
PostgreSQL-based multi-server configuration system
"""

import json
import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum


class FeatureType(Enum):
    TRANSLATION = "translation"
    TTS = "tts"
    MUSIC = "music"


class PermissionLevel(Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"


@dataclass
class GuildConfig:
    guild_id: int
    guild_name: str
    api_key: Optional[str] = None
    features: Dict[str, bool] = None
    channels: Dict[str, Any] = None
    settings: Dict[str, Any] = None
    is_initialized: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.features is None:
            self.features = {
                "translation": False,
                "tts": False,
                "music": False
            }
        
        if self.channels is None:
            self.channels = {}
        
        if self.settings is None:
            self.settings = {
                "tts_timeout_minutes": 10,
                "max_queue_size": 100,
                "rate_limit_per_minute": 30,
                "max_daily_requests": 1000,
                "max_monthly_cost_usd": 10.0,
                "cost_alert_threshold_usd": 8.0
            }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_feature_enabled(self, feature: FeatureType) -> bool:
        return self.features.get(feature.value, False)

    def enable_feature(self, feature: FeatureType):
        self.features[feature.value] = True

    def disable_feature(self, feature: FeatureType):
        self.features[feature.value] = False


@dataclass
class TranslationConfig:
    id: Optional[int]
    guild_id: int
    language_code: str
    language_name: str
    channel_id: int
    is_active: bool = True
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TTSConfig:
    id: Optional[int]
    guild_id: int
    text_channel_id: int
    voice_channel_ids: List[int]
    timeout_minutes: int = 10
    is_active: bool = True
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MusicConfig:
    id: Optional[int]
    guild_id: int
    command_channel_id: Optional[int] = None  # None means all channels
    voice_channel_id: Optional[int] = None    # None means auto-detect
    category_id: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MessageMapping:
    id: Optional[int]
    guild_id: int
    original_message_id: int
    original_channel_id: int
    translated_messages: Dict[str, int]  # {"korean": 123, "english": 456}
    original_content: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UsageStats:
    id: Optional[int]
    guild_id: int
    feature_type: FeatureType
    usage_count: int = 1
    api_cost_usd: float = 0.0
    date: date = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.date is None:
            self.date = date.today()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['feature_type'] = self.feature_type.value
        return data


@dataclass
class AdminPermission:
    id: Optional[int]
    guild_id: int
    user_id: int
    permission_level: PermissionLevel = PermissionLevel.ADMIN
    granted_by: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['permission_level'] = self.permission_level.value
        return data


@dataclass
class SupportedLanguage:
    code: str
    name_en: str
    name_native: str
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass


class ConfigurationError(Exception):
    """Custom exception for configuration issues"""
    pass