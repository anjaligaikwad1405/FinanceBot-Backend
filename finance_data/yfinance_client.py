import yfinance as yf
from datetime import datetime, timedelta

class YFinanceClient:
    def __init__(self):
        pass
    
    def get_stock_data(self, symbol, period='1d'):
        """Get stock data using yfinance (free, no API key needed)"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get current info
            info = ticker.info
            
            # Get recent history
            hist = ticker.history(period=period)
            
            if hist.empty:
                return {'error': 'No data available', 'source': 'yfinance'}
            
            latest = hist.iloc[-1]
            
            return {
                'symbol': symbol,
                'current_price': round(float(latest['Close']), 2),
                'open': round(float(latest['Open']), 2),
                'high': round(float(latest['High']), 2),
                'low': round(float(latest['Low']), 2),
                'volume': int(latest['Volume']),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'dividend_yield': info.get('dividendYield', 0),
                'company_name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'source': 'yfinance'
            }
        except Exception as e:
            return {'error': str(e), 'source': 'yfinance'}
    
    def get_crypto_data(self, symbol):
        """Get cryptocurrency data"""
        try:
            # yfinance crypto symbols usually end with -USD
            if not symbol.endswith('-USD'):
                symbol = f"{symbol}-USD"
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d')
            
            if hist.empty:
                return {'error': 'No data available', 'source': 'yfinance'}
            
            latest = hist.iloc[-1]
            
            return {
                'symbol': symbol,
                'current_price': round(float(latest['Close']), 2),
                'open': round(float(latest['Open']), 2),
                'high': round(float(latest['High']), 2),
                'low': round(float(latest['Low']), 2),
                'volume': int(latest['Volume']),
                'source': 'yfinance'
            }
        except Exception as e:
            return {'error': str(e), 'source': 'yfinance'}
