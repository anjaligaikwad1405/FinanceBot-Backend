import os
from dotenv import load_dotenv

load_dotenv()

class FinanceConfig:
    # API Keys - Add these to your .env file
    FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '')
    ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    IEX_CLOUD_API_KEY = os.getenv('IEX_CLOUD_API_KEY', '')
    
    # Cache settings
    CACHE_TIMEOUT = 300  # 5 minutes
    
    # Rate limiting
    API_CALL_DELAY = 1  # seconds between calls
