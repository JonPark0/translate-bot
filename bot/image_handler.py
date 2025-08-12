import io
import logging
from typing import Optional
import aiohttp
import discord
from pathlib import Path


class ImageHandler:
    def __init__(self, max_file_size_mb: int = 25):
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.logger = logging.getLogger(__name__)
        
        self.supported_formats = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg',
            '.pdf', '.txt', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.rar', '.7z', '.tar', '.gz'
        }
    
    async def process_attachment(self, attachment: discord.Attachment) -> Optional[io.BytesIO]:
        try:
            if attachment.size > self.max_file_size_bytes:
                self.logger.warning(f"File too large: {attachment.filename} ({attachment.size} bytes)")
                return None
            
            file_extension = Path(attachment.filename).suffix.lower()
            if file_extension not in self.supported_formats:
                self.logger.warning(f"Unsupported file type: {attachment.filename}")
                return None
            
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as response:
                    if response.status == 200:
                        file_data = await response.read()
                        return io.BytesIO(file_data)
                    else:
                        self.logger.error(f"Failed to download attachment: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            self.logger.error(f"Error processing attachment {attachment.filename}: {e}")
            return None
    
    def is_image(self, filename: str) -> bool:
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        return Path(filename).suffix.lower() in image_extensions
    
    def get_file_info(self, attachment: discord.Attachment) -> dict:
        return {
            'filename': attachment.filename,
            'size_bytes': attachment.size,
            'size_mb': round(attachment.size / (1024 * 1024), 2),
            'url': attachment.url,
            'is_image': self.is_image(attachment.filename),
            'extension': Path(attachment.filename).suffix.lower()
        }