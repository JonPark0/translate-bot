-- Key Translation Bot Database Schema
-- PostgreSQL Database Schema for Multi-Server Support

-- Guild configurations table
CREATE TABLE guild_configs (
    guild_id BIGINT PRIMARY KEY,
    guild_name TEXT NOT NULL,
    api_key TEXT,
    features JSONB DEFAULT '{
        "translation": false,
        "tts": false,
        "music": false
    }'::jsonb,
    channels JSONB DEFAULT '{}'::jsonb,
    settings JSONB DEFAULT '{
        "tts_timeout_minutes": 10,
        "max_queue_size": 100,
        "rate_limit_per_minute": 30,
        "max_daily_requests": 1000,
        "max_monthly_cost_usd": 10.0,
        "cost_alert_threshold_usd": 8.0
    }'::jsonb,
    is_initialized BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Translation language configurations
CREATE TABLE translation_configs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guild_configs(guild_id) ON DELETE CASCADE,
    language_code VARCHAR(10) NOT NULL,
    language_name TEXT NOT NULL,
    channel_id BIGINT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, language_code),
    UNIQUE(guild_id, channel_id)
);

-- TTS configurations
CREATE TABLE tts_configs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guild_configs(guild_id) ON DELETE CASCADE,
    text_channel_id BIGINT NOT NULL,
    voice_channel_ids BIGINT[] NOT NULL,
    timeout_minutes INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, text_channel_id)
);

-- Music configurations
CREATE TABLE music_configs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guild_configs(guild_id) ON DELETE CASCADE,
    command_channel_id BIGINT, -- NULL means all channels
    voice_channel_id BIGINT,   -- NULL means auto-detect user's voice channel
    category_id BIGINT,        -- Alternative to specific voice channel
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Message tracking for translation synchronization
CREATE TABLE message_mappings (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guild_configs(guild_id) ON DELETE CASCADE,
    original_message_id BIGINT NOT NULL,
    original_channel_id BIGINT NOT NULL,
    translated_messages JSONB NOT NULL, -- {"korean": 123, "english": 456, ...}
    original_content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, original_message_id)
);

-- Bot usage statistics
CREATE TABLE usage_stats (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guild_configs(guild_id) ON DELETE CASCADE,
    feature_type VARCHAR(20) NOT NULL, -- 'translation', 'tts', 'music'
    usage_count INTEGER DEFAULT 1,
    api_cost_usd DECIMAL(10,4) DEFAULT 0,
    date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, feature_type, date)
);

-- Admin permissions
CREATE TABLE admin_permissions (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guild_configs(guild_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    permission_level VARCHAR(20) DEFAULT 'admin', -- 'owner', 'admin', 'moderator'
    granted_by BIGINT, -- user_id who granted this permission
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, user_id)
);

-- Indexes for performance
CREATE INDEX idx_guild_configs_guild_id ON guild_configs(guild_id);
CREATE INDEX idx_translation_configs_guild_id ON translation_configs(guild_id);
CREATE INDEX idx_tts_configs_guild_id ON tts_configs(guild_id);
CREATE INDEX idx_music_configs_guild_id ON music_configs(guild_id);
CREATE INDEX idx_message_mappings_guild_id ON message_mappings(guild_id);
CREATE INDEX idx_message_mappings_original_message ON message_mappings(original_message_id);
CREATE INDEX idx_usage_stats_guild_date ON usage_stats(guild_id, date);
CREATE INDEX idx_admin_permissions_guild_user ON admin_permissions(guild_id, user_id);

-- Updated timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to guild_configs
CREATE TRIGGER update_guild_configs_updated_at
    BEFORE UPDATE ON guild_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default supported languages for reference
CREATE TABLE supported_languages (
    code VARCHAR(10) PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_native TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true
);

INSERT INTO supported_languages (code, name_en, name_native) VALUES
('ko', 'Korean', '한국어'),
('en', 'English', 'English'),
('ja', 'Japanese', '日本語'),
('zh', 'Chinese', '中文'),
('ar', 'Arabic', 'العربية'),
('bn', 'Bengali', 'বাংলা'),
('bg', 'Bulgarian', 'български'),
('hr', 'Croatian', 'hrvatski'),
('cs', 'Czech', 'čeština'),
('da', 'Danish', 'dansk'),
('nl', 'Dutch', 'Nederlands'),
('et', 'Estonian', 'eesti'),
('fi', 'Finnish', 'suomi'),
('fr', 'French', 'français'),
('de', 'German', 'Deutsch'),
('el', 'Greek', 'ελληνικά'),
('iw', 'Hebrew', 'עברית'),
('hi', 'Hindi', 'हिन्दी'),
('hu', 'Hungarian', 'magyar'),
('id', 'Indonesian', 'Bahasa Indonesia'),
('it', 'Italian', 'italiano'),
('lv', 'Latvian', 'latviešu'),
('lt', 'Lithuanian', 'lietuvių'),
('no', 'Norwegian', 'norsk'),
('pl', 'Polish', 'polski'),
('pt', 'Portuguese', 'português'),
('ro', 'Romanian', 'română'),
('ru', 'Russian', 'русский'),
('sr', 'Serbian', 'српски'),
('sk', 'Slovak', 'slovenčina'),
('sl', 'Slovenian', 'slovenščina'),
('es', 'Spanish', 'español'),
('sw', 'Swahili', 'Kiswahili'),
('sv', 'Swedish', 'svenska'),
('th', 'Thai', 'ไทย'),
('tr', 'Turkish', 'Türkçe'),
('uk', 'Ukrainian', 'українська'),
('vi', 'Vietnamese', 'Tiếng Việt');