from flask import jsonify, request
from . import finance_bp
from .finnhub_client import FinnhubClient
from .alpha_vantage_client import AlphaVantageClient
from .yfinance_client import YFinanceClient
import time

# Initialize clients
finnhub_client = FinnhubClient()
alpha_vantage_client = AlphaVantageClient()
yfinance_client = YFinanceClient()

# Simple in-memory cache
cache = {}
CACHE_DURATION = 300  # 5 minutes

def get_cached_data(key):
    """Get data from cache if not expired"""
    if key in cache:
        data, timestamp = cache[key]
        if time.time() - timestamp < CACHE_DURATION:
            return data
    return None

def set_cached_data(key, data):
    """Store data in cache with timestamp"""
    cache[key] = (data, time.time())

@finance_bp.route('/quote/<symbol>')
def get_quote(symbol):
    """Get stock quote from multiple sources with fallback"""
    symbol = symbol.upper()
    cache_key = f"quote_{symbol}"
    
    # Check cache first
    cached_data = get_cached_data(cache_key)
    if cached_data:
        cached_data['cached'] = True
        return jsonify(cached_data)
    
    # Try multiple sources in order of preference
    sources = [
        ('yfinance', lambda: yfinance_client.get_stock_data(symbol)),
        ('finnhub', lambda: finnhub_client.get_quote(symbol)),
        ('alpha_vantage', lambda: alpha_vantage_client.get_intraday_data(symbol))
    ]
    
    for source_name, source_func in sources:
        try:
            data = source_func()
            if 'error' not in data:
                data['cached'] = False
                set_cached_data(cache_key, data)
                return jsonify(data)
        except Exception as e:
            continue
    
    return jsonify({'error': 'Unable to fetch data from any source'}), 500

@finance_bp.route('/company/<symbol>')
def get_company_info(symbol):
    """Get company information"""
    symbol = symbol.upper()
    cache_key = f"company_{symbol}"
    
    # Check cache first
    cached_data = get_cached_data(cache_key)
    if cached_data:
        cached_data['cached'] = True
        return jsonify(cached_data)
    
    # Try yfinance first (most comprehensive for free)
    data = yfinance_client.get_stock_data(symbol)
    if 'error' not in data:
        data['cached'] = False
        set_cached_data(cache_key, data)
        return jsonify(data)
    
    # Fallback to finnhub
    data = finnhub_client.get_company_profile(symbol)
    if 'error' not in data:
        data['cached'] = False
        set_cached_data(cache_key, data)
        return jsonify(data)
    
    return jsonify({'error': 'Unable to fetch company data'}), 500

@finance_bp.route('/crypto/<symbol>')
def get_crypto_data(symbol):
    """Get cryptocurrency data"""
    symbol = symbol.upper()
    cache_key = f"crypto_{symbol}"
    
    # Check cache first
    cached_data = get_cached_data(cache_key)
    if cached_data:
        cached_data['cached'] = True
        return jsonify(cached_data)
    
    data = yfinance_client.get_crypto_data(symbol)
    if 'error' not in data:
        data['cached'] = False
        set_cached_data(cache_key, data)
        return jsonify(data)
    
    return jsonify({'error': 'Unable to fetch crypto data'}), 500

@finance_bp.route('/search')
def search_stocks():
    """Search for stocks (simple implementation)"""
    query = request.args.get('q', '').upper()
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    # Common stock symbols for demo - in production, use a proper search API
    common_stocks = {
        'AAPL': 'Apple Inc.',
        'GOOGL': 'Alphabet Inc.',
        'MSFT': 'Microsoft Corporation',
        'AMZN': 'Amazon.com Inc.',
        'TSLA': 'Tesla Inc.',
        'META': 'Meta Platforms Inc.',
        'NFLX': 'Netflix Inc.',
        'NVDA': 'NVIDIA Corporation'
    }
    
    results = []
    for symbol, name in common_stocks.items():
        if query in symbol or query in name.upper():
            results.append({'symbol': symbol, 'name': name})
    
    return jsonify({'results': results})

@finance_bp.route('/market-status')
def get_market_status():
    """Get market status"""
    try:
        # Simple market status check using yfinance
        ticker = yf.Ticker("SPY")  # S&P 500 ETF
        data = ticker.history(period='1d')
        
        if not data.empty:
            return jsonify({
                'status': 'open',
                'last_update': data.index[-1].strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'yfinance'
            })
        else:
            return jsonify({'status': 'closed', 'source': 'yfinance'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
