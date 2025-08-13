import re
import logging
from typing import Optional, Dict, List
import google.generativeai as genai


class GeminiTranslator:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        self.logger = logging.getLogger(__name__)
        
        self.language_codes = {
            'korean': 'ko',
            'english': 'en',
            'japanese': 'ja',
            'chinese': 'zh'
        }
        
        self.language_names = {
            'ko': '한국어',
            'en': 'English',
            'ja': '日本語',
            'zh': '中文'
        }
    
    def _detect_language(self, text: str) -> str:
        korean_chars = len(re.findall(r'[가-힣]', text))
        japanese_chars = len(re.findall(r'[ひらがなカタカナ一-龯]', text))
        chinese_chars = len(re.findall(r'[一-龯]', text)) - japanese_chars
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        total_chars = korean_chars + japanese_chars + chinese_chars + english_chars
        
        if total_chars == 0:
            return 'en'
        
        if korean_chars / total_chars > 0.3:
            return 'ko'
        elif japanese_chars / total_chars > 0.2:
            return 'ja'
        elif chinese_chars / total_chars > 0.3:
            return 'zh'
        else:
            return 'en'
    
    def _clean_mentions(self, text: str) -> str:
        text = re.sub(r'@everyone', '[everyone]', text)
        text = re.sub(r'@here', '[here]', text)
        text = re.sub(r'<@!?\d+>', '[user]', text)
        text = re.sub(r'<@&\d+>', '[role]', text)
        text = re.sub(r'<#\d+>', '[channel]', text)
        return text
    
    def _restore_mentions(self, translated_text: str) -> str:
        translated_text = re.sub(r'\[everyone\]', '@everyone', translated_text)
        translated_text = re.sub(r'\[here\]', '@here', translated_text)
        return translated_text
    
    async def translate(self, text: str, target_language: str) -> Optional[str]:
        try:
            if not text.strip():
                return None
            
            source_lang = self._detect_language(text)
            
            if source_lang == target_language:
                return None
            
            clean_text = self._clean_mentions(text)
            
            prompt = f"""
            Translate the following text to {self.language_names[target_language]}.
            Keep the tone and style natural.
            Do not translate proper nouns, usernames, or technical terms unless necessary.
            If the text contains links or commands, preserve them exactly.
            
            Text to translate: {clean_text}
            
            Provide only the translation, no explanations.
            """
            
            response = await self.model.generate_content_async(prompt)
            
            if response.text:
                translated = response.text.strip()
                return self._restore_mentions(translated)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Translation failed: {e}")
            return None
    
    async def translate_to_all_languages(self, text: str, source_channel: str) -> Dict[str, Optional[str]]:
        channel_to_lang = {
            'korean': 'ko',
            'english': 'en', 
            'japanese': 'ja',
            'chinese': 'zh'
        }
        
        source_lang = channel_to_lang.get(source_channel)
        if not source_lang:
            return {}
        
        translations = {}
        
        for channel, lang_code in channel_to_lang.items():
            if channel != source_channel:
                translation = await self.translate(text, lang_code)
                if translation:
                    translations[channel] = translation
        
        return translations