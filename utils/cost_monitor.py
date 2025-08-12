import json
import time
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone


class CostMonitor:
    def __init__(self, max_monthly_cost: float = 10.0, alert_threshold: float = 8.0):
        self.max_monthly_cost = max_monthly_cost
        self.alert_threshold = alert_threshold
        
        self.data_file = Path('data/cost_tracking.json')
        self.data_file.parent.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        self._load_data()
    
    def _load_data(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    self.data = json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load cost data: {e}")
                self.data = self._create_empty_data()
        else:
            self.data = self._create_empty_data()
    
    def _create_empty_data(self) -> Dict:
        return {
            'monthly_costs': {},
            'daily_requests': {},
            'total_requests': 0,
            'estimated_monthly_cost': 0.0,
            'last_updated': time.time()
        }
    
    def _save_data(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save cost data: {e}")
    
    def _get_current_month_key(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y-%m')
    
    def _get_current_day_key(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    async def record_request(self, estimated_cost: float = 0.001) -> bool:
        month_key = self._get_current_month_key()
        day_key = self._get_current_day_key()
        
        current_monthly_cost = self.data['monthly_costs'].get(month_key, 0.0)
        
        if current_monthly_cost + estimated_cost > self.max_monthly_cost:
            self.logger.error(f"Monthly cost limit exceeded: {current_monthly_cost + estimated_cost:.4f} > {self.max_monthly_cost}")
            return False
        
        self.data['monthly_costs'][month_key] = current_monthly_cost + estimated_cost
        self.data['daily_requests'][day_key] = self.data['daily_requests'].get(day_key, 0) + 1
        self.data['total_requests'] += 1
        self.data['estimated_monthly_cost'] = self.data['monthly_costs'][month_key]
        self.data['last_updated'] = time.time()
        
        if current_monthly_cost + estimated_cost > self.alert_threshold:
            self.logger.warning(f"Cost alert: Monthly cost approaching limit ({current_monthly_cost + estimated_cost:.4f}/{self.max_monthly_cost})")
        
        self._save_data()
        return True
    
    def get_current_month_cost(self) -> float:
        month_key = self._get_current_month_key()
        return self.data['monthly_costs'].get(month_key, 0.0)
    
    def get_usage_stats(self) -> Dict:
        month_key = self._get_current_month_key()
        day_key = self._get_current_day_key()
        
        return {
            'current_month_cost': self.data['monthly_costs'].get(month_key, 0.0),
            'max_monthly_cost': self.max_monthly_cost,
            'cost_percentage': (self.data['monthly_costs'].get(month_key, 0.0) / self.max_monthly_cost) * 100,
            'requests_today': self.data['daily_requests'].get(day_key, 0),
            'total_requests': self.data['total_requests'],
            'alert_threshold': self.alert_threshold,
            'last_updated': self.data['last_updated']
        }
    
    def can_make_request(self) -> bool:
        month_key = self._get_current_month_key()
        current_cost = self.data['monthly_costs'].get(month_key, 0.0)
        return current_cost < self.max_monthly_cost