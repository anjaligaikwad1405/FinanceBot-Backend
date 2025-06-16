import requests
import time
from .config import FinanceConfig

class AlphaVantageClient:
    def __init__(self):
        self.api_key = FinanceConfig.ALPHA_VANTAGE_API_KEY
        self.base_url = 'https://www.alphavantage.co/query'
        self.last_call_time = 0
    
    def _rate_limit(self):
        """Rate limiting for Alpha Vantage (5 calls/min)"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < 12:  # 5 calls/min = 12 seconds between calls
            time.sleep(12 - time_since_last_call)
        self.last_call_time = time.time()
    
    def get_intraday_data(self, symbol, interval='5min'):
        """Get intraday stock data"""
        try:
            self._rate_limit()
            params = {
                'function': 'TIME_SERIES_INTRADAY',
                'symbol': symbol,
                'interval': interval,
                'apikey': self.api_key,
                'outputsize': 'compact'
            }
            
            response = requests.get(self.base_url, params=params)
            data = response.json()
            
            if 'Error Message' in data:
                return {'error': data['Error Message'], 'source': 'alpha_vantage'}
            
            if 'Note' in data:
                return {'error': 'API call frequency limit reached', 'source': 'alpha_vantage'}
            
            time_series_key = f'Time Series ({interval})'
            if time_series_key not in data:
                return {'error': 'No data available', 'source': 'alpha_vantage'}
            
            time_series = data[time_series_key]
            latest_time = list(time_series.keys())[0]
            latest_data = time_series[latest_time]
            
            return {
                'symbol': symbol,
                'timestamp': latest_time,
                'open': float(latest_data['1. open']),
                'high': float(latest_data['2. high']),
                'low': float(latest_data['3. low']),
                'close': float(latest_data['4. close']),
                'volume': int(latest_data['5. volume']),
                'source': 'alpha_vantage'
            }
        except Exception as e:
            return {'error': str(e), 'source': 'alpha_vantage'}
