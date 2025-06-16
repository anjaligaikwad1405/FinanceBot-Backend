import os
import time
import re
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from mistralai import Mistral
import yfinance as yf
import requests
from functools import lru_cache

app = Flask(__name__)

# Enhanced CORS Configuration
CORS(app, 
     origins=["https://finance-bot-frontend.vercel.app", "http://localhost:3000", "http://127.0.0.1:3000"], 
     methods=["GET","POST","OPTIONS"], 
     allow_headers=["Content-Type","Authorization"], 
     supports_credentials=True)

# API Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "QKIr9flpqitrfwPJP1PsVf83I03jUUdd")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "cvu01ehr01qjg136mv40cvu01ehr01qjg136mv4g")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "HCNAPMP7ZWYFT3YO")
MISTRAL_MODEL = "mistral-tiny"

# Initialize Mistral client
client = Mistral(api_key=MISTRAL_API_KEY)

# Cache for financial data to avoid excessive API calls
financial_cache = {}
CACHE_DURATION = 300  # 5 minutes

DEFAULT_SYSTEM_MESSAGE = """
You are a sophisticated personal financial AI assistant with access to real-time market data. Your job is to:

1. Understand user financial goals, risk tolerance, investment timeline, and personal details
2. Provide personalized investment advice based on current market conditions
3. Integrate real-time stock prices, market data, and financial metrics into your responses
4. Offer actionable, practical financial guidance

CONVERSATION RULES:
- NEVER start responses with "Welcome to FinanceGuru" unless it's the first interaction
- Provide immediate value - don't gatekeep information behind personal details
- Ask for personal details only when needed for personalized advice
- Use real-time data when discussing specific stocks, ETFs, or market conditions
- Maintain conversation context and avoid repetitive questions

INPUT VALIDATION RULES:
- Reject unrealistic ages (outside 5-120 years)
- Question impossibly large investment amounts
- Politely correct obviously false information
- Ask for clarification when inputs seem unrealistic

REAL-TIME DATA INTEGRATION:
- When users mention specific stocks (e.g., AAPL, TSLA), include current price and key metrics
- Provide context about market conditions when giving advice
- Use actual performance data to support recommendations
- Include relevant financial ratios and indicators

INVESTMENT ADVICE FRAMEWORK:
- Ages 18-30: 70-90% stocks, 10-30% bonds/alternatives
- Ages 31-50: 60-80% stocks, 20-40% bonds/alternatives  
- Ages 51+: 40-70% stocks, 30-60% bonds/alternatives
- Adjust based on risk tolerance and goals
"""

class FinancialDataClient:
    """Unified client for fetching financial data from multiple sources"""
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = CACHE_DURATION
    
    def _is_cache_valid(self, key):
        """Check if cached data is still valid"""
        if key not in self.cache:
            return False
        cache_time = self.cache[key].get('timestamp', 0)
        return (time.time() - cache_time) < self.cache_duration
    
    def _cache_data(self, key, data):
        """Cache data with timestamp"""
        self.cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def get_stock_data(self, symbol):
        """Get comprehensive stock data using yfinance"""
        cache_key = f"stock_{symbol.upper()}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']
        
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            hist = ticker.history(period="1d")
            
            if hist.empty:
                return {"error": f"No data found for symbol {symbol}"}
            
            current_price = hist['Close'].iloc[-1]
            prev_close = info.get('previousClose', current_price)
            change = current_price - prev_close
            percent_change = (change / prev_close) * 100 if prev_close != 0 else 0
            
            data = {
                "symbol": symbol.upper(),
                "name": info.get('longName', 'N/A'),
                "current_price": round(current_price, 2),
                "previous_close": round(prev_close, 2),
                "change": round(change, 2),
                "percent_change": round(percent_change, 2),
                "volume": info.get('volume', 0),
                "market_cap": info.get('marketCap', 0),
                "pe_ratio": info.get('trailingPE', 'N/A'),
                "dividend_yield": info.get('dividendYield', 0),
                "52_week_high": info.get('fiftyTwoWeekHigh', 0),
                "52_week_low": info.get('fiftyTwoWeekLow', 0),
                "sector": info.get('sector', 'N/A'),
                "industry": info.get('industry', 'N/A'),
                "source": "yfinance",
                "timestamp": datetime.now().isoformat()
            }
            
            self._cache_data(cache_key, data)
            return data
            
        except Exception as e:
            return {"error": f"Failed to fetch data for {symbol}: {str(e)}"}
    
    def get_crypto_data(self, symbol):
        """Get cryptocurrency data"""
        cache_key = f"crypto_{symbol.upper()}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']
        
        try:
            # Use yfinance for crypto (e.g., BTC-USD, ETH-USD)
            crypto_symbol = f"{symbol.upper()}-USD"
            ticker = yf.Ticker(crypto_symbol)
            hist = ticker.history(period="1d")
            
            if hist.empty:
                return {"error": f"No crypto data found for {symbol}"}
            
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Open'].iloc[0]
            change = current_price - prev_close
            percent_change = (change / prev_close) * 100 if prev_close != 0 else 0
            
            data = {
                "symbol": symbol.upper(),
                "current_price": round(current_price, 2),
                "change": round(change, 2),
                "percent_change": round(percent_change, 2),
                "volume": hist['Volume'].iloc[-1] if not hist.empty else 0,
                "source": "yfinance_crypto",
                "timestamp": datetime.now().isoformat()
            }
            
            self._cache_data(cache_key, data)
            return data
            
        except Exception as e:
            return {"error": f"Failed to fetch crypto data for {symbol}: {str(e)}"}
    
    def search_stocks(self, query):
        """Search for stocks by name or symbol"""
        try:
            # Simple search using yfinance
            search_symbols = [query.upper(), f"{query}.NS", f"{query}.BO"]  # Include Indian markets
            results = []
            
            for symbol in search_symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    if info.get('longName') or info.get('shortName'):
                        results.append({
                            "symbol": symbol,
                            "name": info.get('longName', info.get('shortName', 'N/A')),
                            "sector": info.get('sector', 'N/A')
                        })
                except:
                    continue
            
            return {"results": results[:5]}  # Limit to 5 results
            
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}

# Initialize financial data client
financial_client = FinancialDataClient()

def extract_stock_symbols(text):
    """Extract potential stock symbols from text"""
    # Common patterns for stock symbols
    patterns = [
        r'\b[A-Z]{1,5}\b',  # 1-5 uppercase letters
        r'\$([A-Z]{1,5})\b',  # $AAPL format
        r'\b([A-Z]{1,5})\.NS\b',  # Indian NSE format
        r'\b([A-Z]{1,5})\.BO\b',  # Indian BSE format
    ]
    
    symbols = set()
    for pattern in patterns:
        matches = re.findall(pattern, text.upper())
        symbols.update(matches if isinstance(matches[0], str) if matches else [] for match in matches)
    
    # Filter out common words that might match the pattern
    common_words = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'HAD', 'BUT', 'WHAT', 'WERE', 'THEY', 'WE', 'BEEN', 'HAVE', 'THEIR', 'WHERE', 'WHO', 'OIL', 'GAS', 'CAR', 'NEW', 'OLD', 'BIG', 'GET', 'USE', 'MAN', 'DAY', 'TOO', 'ANY', 'MAY', 'SAY', 'SHE', 'ITS', 'HOW', 'TWO', 'WHO', 'BOY', 'DID', 'HAS', 'LET', 'PUT', 'END', 'WHY', 'TRY', 'GOD', 'SIX', 'DOG', 'EAT', 'AGO', 'SIT', 'FUN', 'BAD', 'YES', 'YET', 'ARM', 'FAR', 'OFF', 'BAG', 'BED', 'BET', 'BOX', 'BOY', 'BUS', 'BUY', 'CAN', 'CAR', 'CAT', 'CUP', 'CUT', 'DAD', 'DAY', 'DID', 'DOG', 'EAR', 'EAT', 'EGG', 'END', 'EYE', 'FAR', 'FED', 'FEW', 'FIX', 'FLY', 'FOR', 'FOX', 'FUN', 'GET', 'GOD', 'GOT', 'GUN', 'HAD', 'HAM', 'HAS', 'HAT', 'HER', 'HIM', 'HIS', 'HIT', 'HOT', 'HOW', 'HUG', 'ICE', 'ILL', 'JAM', 'JOB', 'JOY', 'KEY', 'KID', 'LAP', 'LAY', 'LEG', 'LET', 'LID', 'LIE', 'LOG', 'LOT', 'LOW', 'MAD', 'MAN', 'MAP', 'MAY', 'MOM', 'MUD', 'NET', 'NEW', 'NOD', 'NOT', 'NOW', 'NUT', 'ODD', 'OFF', 'OLD', 'ONE', 'OUR', 'OUT', 'OWN', 'PAD', 'PAN', 'PAY', 'PEN', 'PET', 'PIE', 'PIG', 'POT', 'PUT', 'RAN', 'RAT', 'RAW', 'RED', 'RID', 'RIP', 'ROW', 'RUB', 'RUG', 'RUN', 'SAD', 'SAT', 'SAW', 'SAY', 'SEA', 'SEE', 'SET', 'SHE', 'SIT', 'SIX', 'SKY', 'SON', 'SUN', 'TAX', 'TEA', 'TEN', 'THE', 'TIE', 'TIP', 'TOO', 'TOP', 'TOY', 'TRY', 'TWO', 'USE', 'VAN', 'WAR', 'WAS', 'WAY', 'WE', 'WET', 'WHO', 'WHY', 'WIN', 'WON', 'YES', 'YET', 'YOU', 'ZIP'}
    
    return [s for s in symbols if s not in common_words and len(s) >= 2]

def validate_user_input(user_input):
    """Validate user input for unrealistic values"""
    lowercase_input = user_input.lower()
    
    # Check for unrealistic age
    age_patterns = [r'i am (\d+)', r"i'm (\d+)", r'age (\d+)', r'(\d+) years old']
    for pattern in age_patterns:
        matches = re.findall(pattern, lowercase_input)
        for match in matches:
            try:
                age = int(match)
                if age > 120:
                    return (False, f"I noticed you mentioned being {age} years old. For accurate financial planning, could you please confirm your actual age?")
                elif age < 5:
                    return (False, f"Financial planning for someone {age} years old typically involves parents or guardians. Are you planning on behalf of someone else?")
            except ValueError:
                continue
    
    # Check for unrealistic investment amounts
    amount_patterns = [r'invest (\d+(?:\.\d+)?)\s*(trillion|billion|million|lakh|crore)', 
                      r'(\d+(?:\.\d+)?)\s*(trillion|billion|million|lakh|crore)']
    for pattern in amount_patterns:
        matches = re.findall(pattern, lowercase_input)
        for amount_str, unit in matches:
            try:
                amount = float(amount_str)
                if unit == 'trillion' or (unit == 'billion' and amount > 10):
                    return (False, "I noticed you mentioned an extremely large investment amount. Could you please confirm a more realistic figure for personalized advice?")
            except ValueError:
                continue
    
    return (True, None)

def call_mistral_api(messages, temperature=0.7, max_tokens=800, max_retries=3):
    """Make a call to the Mistral API with retry logic"""
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            response = client.chat.complete(
                model=MISTRAL_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate limit" in error_str.lower():
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    break
            else:
                return {"error": f"API error: {error_str}"}
    
    return {"error": "Maximum retry attempts exceeded"}

def enhance_message_with_financial_data(user_input):
    """Enhance user message with real-time financial data"""
    stock_symbols = extract_stock_symbols(user_input)
    financial_context = ""
    
    if stock_symbols:
        financial_context += "\n\nREAL-TIME MARKET DATA:\n"
        for symbol in stock_symbols[:3]:  # Limit to 3 symbols to avoid context overflow
            stock_data = financial_client.get_stock_data(symbol)
            if 'error' not in stock_data:
                financial_context += f"{symbol}: ${stock_data['current_price']} ({stock_data['change']:+.2f}, {stock_data['percent_change']:+.2f}%) - {stock_data['name']}\n"
    
    # Check for crypto mentions
    crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency']
    mentioned_crypto = [kw for kw in crypto_keywords if kw in user_input.lower()]
    
    if mentioned_crypto and 'bitcoin' in mentioned_crypto or 'btc' in mentioned_crypto:
        crypto_data = financial_client.get_crypto_data('BTC')
        if 'error' not in crypto_data:
            financial_context += f"Bitcoin: ${crypto_data['current_price']} ({crypto_data['change']:+.2f}, {crypto_data['percent_change']:+.2f}%)\n"
    
    return financial_context

# API Routes
@app.route('/')
def home():
    return jsonify({
        "status": "FinanceGuru Backend Running",
        "version": "2.0",
        "features": ["Real-time stock data", "Crypto prices", "Personalized advice", "Market analysis"],
        "endpoints": ["/api/chat", "/api/finance/quote/<symbol>", "/api/finance/crypto/<symbol>", "/api/health"]
    })

@app.route('/api/finance/quote/<symbol>')
def get_stock_quote(symbol):
    """Get real-time stock quote"""
    data = financial_client.get_stock_data(symbol)
    return jsonify(data)

@app.route('/api/finance/crypto/<symbol>')
def get_crypto_quote(symbol):
    """Get cryptocurrency quote"""
    data = financial_client.get_crypto_data(symbol)
    return jsonify(data)

@app.route('/api/finance/search')
def search_stocks():
    """Search for stocks"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Please provide search query"}), 400
    
    data = financial_client.search_stocks(query)
    return jsonify(data)

@app.route('/api/finance/market-status')
def market_status():
    """Get market status"""
    try:
        # Get major indices
        indices = ['SPY', 'QQQ', 'DIA']  # S&P 500, NASDAQ, Dow
        market_data = {}
        
        for index in indices:
            data = financial_client.get_stock_data(index)
            if 'error' not in data:
                market_data[index] = {
                    "price": data['current_price'],
                    "change": data['change'],
                    "percent_change": data['percent_change']
                }
        
        return jsonify({
            "status": "open" if datetime.now().weekday() < 5 else "closed",
            "indices": market_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat endpoint with real-time financial data integration"""
    try:
        data = request.json
        user_input = data.get('user_input', '')
        user_id = data.get('user_id', 'anonymous')
        conversation_history = data.get('conversation_history', [])
        
        if not user_input:
            return jsonify({"error": "Please provide user input"}), 400
        
        # Handle short inputs
        if len(user_input.strip()) < 5:
            if user_input.lower().strip() in ["hi", "hello", "hey"]:
                if len(conversation_history) == 0:
                    return jsonify({
                        "response": "Hello! I'm your AI financial advisor with access to real-time market data. I can help you with investment planning, stock analysis, and personalized financial advice. What would you like to know?",
                        "user_id": user_id
                    })
                else:
                    return jsonify({
                        "response": "Hi there! Do you have any financial questions or want to check on specific stocks?",
                        "user_id": user_id
                    })
            
            return jsonify({
                "response": "Could you provide more details so I can better assist with your financial planning?",
                "user_id": user_id
            })
        
        # Validate input
        is_valid, validation_message = validate_user_input(user_input)
        if not is_valid:
            return jsonify({
                "response": validation_message,
                "user_id": user_id,
                "validated": False
            })
        
        # Enhance message with real-time financial data
        financial_context = enhance_message_with_financial_data(user_input)
        
        # Build enhanced system message
        enhanced_system_message = DEFAULT_SYSTEM_MESSAGE
        if financial_context:
            enhanced_system_message += f"\n\nCURRENT MARKET CONTEXT:{financial_context}"
        
        # Build messages with conversation history
        messages = [{"role": "system", "content": enhanced_system_message}]
        
        # Add conversation history (limit to last 5 exchanges)
        for exchange in conversation_history[-5:]:
            if exchange.get("user_message"):
                messages.append({"role": "user", "content": exchange["user_message"]})
            if exchange.get("assistant_message"):
                messages.append({"role": "assistant", "content": exchange["assistant_message"]})
        
        # Add current user input
        messages.append({"role": "user", "content": user_input})
        
        # Call Mistral API
        response = call_mistral_api(messages)
        
        if isinstance(response, dict) and "error" in response:
            fallback_response = get_enhanced_fallback_response(user_input, financial_context)
            return jsonify({
                "response": fallback_response,
                "user_id": user_id,
                "error": response["error"]
            })
        
        response_text = response.choices[0].message.content.strip()
        
        # Remove redundant welcome messages
        if len(conversation_history) > 0 and "welcome to financeguru" in response_text.lower():
            parts = response_text.split("welcome to financeguru", 1)
            if len(parts) > 1:
                response_text = parts[1].strip()
                if response_text:
                    response_text = response_text[0].upper() + response_text[1:]
        
        return jsonify({
            "response": response_text,
            "user_id": user_id,
            "market_data_included": bool(financial_context)
        })
        
    except Exception as e:
        return jsonify({
            "response": "I'm experiencing technical difficulties. Please try asking about a specific stock or financial topic.",
            "user_id": data.get('user_id', 'anonymous') if 'data' in locals() else 'anonymous',
            "error": str(e)
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Enhanced health check with financial data sources"""
    try:
        # Test Mistral API
        mistral_status = "connected" if MISTRAL_API_KEY and len(MISTRAL_API_KEY) > 10 else "error: Invalid API key"
        
        # Test financial data
        try:
            test_data = financial_client.get_stock_data('AAPL')
            yfinance_status = "connected" if 'error' not in test_data else f"error: {test_data['error']}"
        except Exception as e:
            yfinance_status = f"error: {str(e)}"
        
        overall_status = "ok" if mistral_status == "connected" and "error" not in yfinance_status else "degraded"
        
        return jsonify({
            "status": overall_status,
            "mistral_api": mistral_status,
            "yfinance": yfinance_status,
            "model": MISTRAL_MODEL,
            "cache_size": len(financial_client.cache),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })

def get_enhanced_fallback_response(user_input, financial_context=""):
    """Enhanced fallback response with financial context"""
    is_valid, validation_message = validate_user_input(user_input)
    if not is_valid:
        return validation_message
    
    lowercase_input = user_input.lower()
    
    # Extract mentioned stocks
    stock_symbols = extract_stock_symbols(user_input)
    
    response_parts = ["I'm currently having trouble accessing my full advisory system, but I can still help you!"]
    
    # Include real-time data if available
    if financial_context:
        response_parts.append("Here's the current market data you mentioned:")
        response_parts.append(financial_context.strip())
    
    # Provide relevant advice based on keywords
    if any(term in lowercase_input for term in ["retire", "retirement"]):
        response_parts.append("For retirement planning, consider starting with tax-advantaged accounts like 401(k)s and IRAs, then build a diversified portfolio based on your age and risk tolerance.")
    
    elif any(term in lowercase_input for term in ["emergency", "emergency fund"]):
        response_parts.append("An emergency fund should cover 3-6 months of expenses in a high-yield savings account or money market fund for easy access.")
    
    elif stock_symbols:
        response_parts.append(f"For specific analysis of {', '.join(stock_symbols)}, consider factors like P/E ratio, earnings growth, debt levels, and industry outlook.")
    
    elif any(term in lowercase_input for term in ["crypto", "bitcoin", "ethereum"]):
        response_parts.append("Cryptocurrency should be a small portion of your portfolio (typically 5-10%) due to high volatility. Never invest more than you can afford to lose.")
    
    else:
        response_parts.append("For general investment advice: diversify across asset classes, invest regularly, keep costs low, and maintain a long-term perspective. Consider your age, risk tolerance, and investment timeline when building your portfolio.")
    
    return " ".join(response_parts)

if __name__ == "__main__":
    print("🚀 Starting Enhanced FinanceGuru Backend")
    print("📊 Features: Real-time stock data, crypto prices, market analysis")
    print(f"🤖 AI Model: {MISTRAL_MODEL}")
    print("🔥 Financial Data: yfinance integration")
    app.run(debug=True, host='0.0.0.0', port=5000)
