import asyncio
import json
import logging
from aiohttp import web
from typing import Optional


class HealthServer:
    def __init__(self, bot, port: int = 8080):
        self.bot = bot
        self.port = port
        self.logger = logging.getLogger(__name__)
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
        self._setup_routes()
    
    def _setup_routes(self):
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/status', self.status_check)
        self.app.router.add_get('/metrics', self.metrics)
    
    async def health_check(self, request):
        if self.bot.is_ready():
            return web.json_response({
                'status': 'healthy',
                'bot_ready': True,
                'latency': f"{self.bot.latency * 1000:.2f}ms"
            })
        else:
            return web.json_response({
                'status': 'unhealthy',
                'bot_ready': False
            }, status=503)
    
    async def status_check(self, request):
        rate_stats = self.bot.rate_limiter.get_usage_stats()
        cost_stats = self.bot.cost_monitor.get_usage_stats()
        
        return web.json_response({
            'bot': {
                'ready': self.bot.is_ready(),
                'latency_ms': f"{self.bot.latency * 1000:.2f}",
                'guild_count': len(self.bot.guilds),
                'user_count': len(self.bot.users)
            },
            'rate_limiting': rate_stats,
            'cost_monitoring': cost_stats
        })
    
    async def metrics(self, request):
        rate_stats = self.bot.rate_limiter.get_usage_stats()
        cost_stats = self.bot.cost_monitor.get_usage_stats()
        
        metrics = []
        metrics.append(f"# HELP bot_ready Bot ready status")
        metrics.append(f"# TYPE bot_ready gauge")
        metrics.append(f"bot_ready {1 if self.bot.is_ready() else 0}")
        
        metrics.append(f"# HELP bot_latency_seconds Bot latency in seconds")
        metrics.append(f"# TYPE bot_latency_seconds gauge")
        metrics.append(f"bot_latency_seconds {self.bot.latency}")
        
        metrics.append(f"# HELP rate_limit_requests_minute Current requests per minute")
        metrics.append(f"# TYPE rate_limit_requests_minute gauge")
        metrics.append(f"rate_limit_requests_minute {rate_stats['requests_this_minute']}")
        
        metrics.append(f"# HELP rate_limit_requests_daily Current requests today")
        metrics.append(f"# TYPE rate_limit_requests_daily gauge")
        metrics.append(f"rate_limit_requests_daily {rate_stats['requests_today']}")
        
        metrics.append(f"# HELP cost_monthly_usd Monthly cost in USD")
        metrics.append(f"# TYPE cost_monthly_usd gauge")
        metrics.append(f"cost_monthly_usd {cost_stats['current_month_cost']}")
        
        return web.Response(text='\n'.join(metrics), content_type='text/plain')
    
    async def start(self):
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await self.site.start()
            
            self.logger.info(f"Health server started on port {self.port}")
            
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Health server error: {e}")
    
    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        self.logger.info("Health server stopped")