import finnhub
import time
from .config import FinanceConfig

class FinnhubClient:
    def __init__(self):
        self.client = finnhub.Client(api_key=FinanceConfig.FINNHUB_API_KEY)
        self.last_call_time = 0
    
    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < FinanceConfig.API_CALL_DELAY:
            time.sleep(FinanceConfig.API_CALL_DELAY - time_since_last_call)
        self.last_call_time = time.time()
    
    def get_quote(self, symbol):
        """Get real-time stock quote"""
        try:
            self._rate_limit()
            data = self.client.quote(symbol)
            return {
                'symbol': symbol,
                'current_price': data.get('c', 0),
                'change': data.get('d', 0),
                'percent_change': data.get('dp', 0),
                'high': data.get('h', 0),
                'low': data.get('l', 0),
                'open': data.get('o', 0),
                'previous_close': data.get('pc', 0),
                'source': 'finnhub'
            }
        except Exception as e:
            return {'error': str(e), 'source': 'finnhub'}
    
    def get_company_profile(self, symbol):
        """Get company basic information"""
        try:
            self._rate_limit()
            data = self.client.company_profile2(symbol=symbol)
            return {
                'symbol': symbol,
                'name': data.get('name', ''),
                'country': data.get('country', ''),
                'currency': data.get('currency', ''),
                'exchange': data.get('exchange', ''),
                'industry': data.get('finnhubIndustry', ''),
                'market_cap': data.get('marketCapitalization', 0),
                'source': 'finnhub'
            }
        except Exception as e:
            return {'error': str(e), 'source': 'finnhub'}
