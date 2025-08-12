import asyncio
import time
from collections import deque
from typing import Deque
import logging


class RateLimiter:
    def __init__(self, requests_per_minute: int = 30, max_daily_requests: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.max_daily_requests = max_daily_requests
        
        self.minute_requests: Deque[float] = deque()
        self.daily_requests: Deque[float] = deque()
        
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)
    
    async def acquire(self) -> bool:
        async with self._lock:
            now = time.time()
            
            self._cleanup_old_requests(now)
            
            if len(self.minute_requests) >= self.requests_per_minute:
                self.logger.warning("Rate limit exceeded: per minute limit reached")
                return False
            
            if len(self.daily_requests) >= self.max_daily_requests:
                self.logger.warning("Rate limit exceeded: daily limit reached")
                return False
            
            self.minute_requests.append(now)
            self.daily_requests.append(now)
            
            self.logger.debug(f"Request allowed. Current usage: {len(self.minute_requests)}/min, {len(self.daily_requests)}/day")
            return True
    
    def _cleanup_old_requests(self, now: float):
        minute_ago = now - 60
        while self.minute_requests and self.minute_requests[0] < minute_ago:
            self.minute_requests.popleft()
        
        day_ago = now - 86400  # 24 hours
        while self.daily_requests and self.daily_requests[0] < day_ago:
            self.daily_requests.popleft()
    
    def get_usage_stats(self) -> dict:
        now = time.time()
        self._cleanup_old_requests(now)
        
        return {
            'requests_this_minute': len(self.minute_requests),
            'requests_per_minute_limit': self.requests_per_minute,
            'requests_today': len(self.daily_requests),
            'max_daily_requests': self.max_daily_requests
        }