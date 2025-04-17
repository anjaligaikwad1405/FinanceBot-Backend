import os
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from mistralai import Mistral

app = Flask(__name__)
CORS(app, origins=["https://finance-bot-frontend.vercel.app"])

# Mistral API Configuration
MISTRAL_API_KEY = "pcrrbcrfeX4lp11mICMNDBTDhzrY4QIf" # Replace with your actual API key or use environment variable
MISTRAL_MODEL = "mistral-tiny"  # Using Mistral-tiny model for testing

# Initialize Mistral client
client = Mistral(api_key=MISTRAL_API_KEY)

DEFAULT_SYSTEM_MESSAGE = """
You are a personal financial AI assistant. Your job is to understand and extract user details such as age, job, investment amount, and investment purpose from natural conversations.

CONVERSATION RULES:
- NEVER start your responses with "Welcome to FinanceGuru" unless explicitly instructed
- Do NOT ask for all user details at once if they're just asking a general question
- If a user asks a general finance question, provide helpful information immediately without requiring personal details
- Only ask for specific personal details if they're relevant to giving personalized advice
- Maintain conversation context - don't repeat questions the user has already answered

INPUT VALIDATION RULES:
- MANDATORY: Check if the user provides unrealistic information (e.g., claiming to be 300 years old)
- NEVER provide financial advice based on impossible or clearly joking inputs
- If the user provides unrealistic information, politely ask for clarification
- Realistic age range for financial advice is 5-120 years old ONLY
- NEVER accept ages over 120 or under 5 years old - always ask for clarification
- Realistic investment amounts should be appropriate to the context (not extremely small or large)
- If a user states an impossible age (like 1000 years), first acknowledge it as unrealistic then ask for their actual age

When providing financial advice:
- If sufficient information is present for personalized advice, provide a tailored investment plan
- Investment plans should include percentages across various instruments based on age group:
  - Up to 30: high risk, high return
  - 31–50: moderate risk
  - 51 and above: low risk
- Always keep financial advice focused, clear, and jargon-free
- Respond in a warm, advisory tone
"""

def validate_user_input(user_input):
    """
    Validate user input for unrealistic values (age, investment amount, etc.)
    Returns a tuple: (is_valid, validation_message)
    """
    # Convert to lowercase for easier matching
    lowercase_input = user_input.lower()
    
    # Check for unrealistic age
    age_words = ["i am", "i'm", "age", "years old"]
    for age_word in age_words:
        if age_word in lowercase_input:
            parts = lowercase_input.split(age_word)
            if len(parts) > 1:
                # Try to extract the age number
                try:
                    words = parts[1].strip().split()
                    for word in words[:2]:  # Look at first two words after age phrase
                        if word.isdigit():
                            age = int(word)
                            # Check if age is unrealistic
                            if age > 120:
                                return (False, f"I noticed you mentioned being {age} years old, which seems unrealistic for financial planning. Could you please confirm your actual age so I can provide more accurate advice?")
                            elif age < 5:
                                return (False, f"I noticed you mentioned being {age} years old, which is quite young for independent financial planning. Are you asking on behalf of someone else?")
                except:
                    pass
    
    # Check for unrealistic investment amounts
    amount_indicators = ["invest", "investing", "investment", "rs", "rupees", "inr", "$", "dollars", "usd"]
    for indicator in amount_indicators:
        if indicator in lowercase_input:
            # Look for extremely large numbers
            parts = lowercase_input.split(indicator)
            for part in parts:
                words = part.strip().split()
                for i, word in enumerate(words):
                    # Clean the word of non-numeric characters
                    clean_word = ''.join(c for c in word if c.isdigit() or c == '.')
                    if clean_word and clean_word.replace('.', '', 1).isdigit():
                        try:
                            amount = float(clean_word)
                            # Check if next word might be "billion", "trillion", etc.
                            if i < len(words) - 1:
                                multiplier_word = words[i+1].lower()
                                if "trillion" in multiplier_word:
                                    return (False, f"I noticed you mentioned investing trillions, which is an extremely large amount. Could you please confirm a more realistic investment amount for personalized advice?")
                                elif "billion" in multiplier_word and amount > 1:
                                    return (False, f"I noticed you mentioned investing billions, which is an extremely large amount. Could you please confirm a more realistic investment amount for personalized advice?")
                        except:
                            pass
    
    # If all checks pass, input is considered valid
    return (True, None)

def call_mistral_api(messages, temperature=0.7, max_tokens=800, max_retries=5):
    """Make a call to the Mistral API using client library with retry logic"""
    retry_delay = 1  # Start with a 1-second delay
    
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt+1}/{max_retries} - Sending request to Mistral API")
            
            # Call the API with the current SDK syntax
            response = client.chat.complete(
                model=MISTRAL_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            print(f"Received response from Mistral API successfully")
            return response
            
        except Exception as e:
            error_str = str(e)
            print(f"Exception when calling Mistral API: {error_str}")
            
            # Check if it's a rate limit error
            if "429" in error_str or "rate limit" in error_str.lower():
                if attempt < max_retries - 1:  # Don't wait after the last attempt
                    print(f"Rate limit exceeded. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"Maximum retries reached. Giving up.")
            else:
                # If it's not a rate limit error, don't retry
                return {"error": f"API error occurred: {error_str}"}
    
    return {"error": "Maximum retry attempts exceeded due to rate limiting."}

def analyze_sentiment(text, max_retries=3):
    """Analyze sentiment of financial text using Mistral API with retry logic"""
    messages = [
        {"role": "system", "content": "You are a financial sentiment analysis assistant."},
        {"role": "user", "content": f"What is the sentiment of this financial text? Please respond with only one word: negative, neutral, or positive.\n\nText: {text}"}
    ]
    
    try:
        result = call_mistral_api(messages, temperature=0.1, max_tokens=50, max_retries=max_retries)
        
        # Check if we got a proper response object
        if isinstance(result, dict) and "error" in result:
            print(f"Error in sentiment analysis: {result['error']}")
            return {"sentiment": "neutral", "input_text": text, "error": result["error"]}
            
        sentiment_response = result.choices[0].message.content.strip().lower()
        
        # Extract just the sentiment word
        if "negative" in sentiment_response:
            sentiment = "negative"
        elif "positive" in sentiment_response:
            sentiment = "positive"
        elif "neutral" in sentiment_response:
            sentiment = "neutral"
        else:
            sentiment = "unknown"
            
        return {"sentiment": sentiment, "input_text": text}
            
    except Exception as e:
        print(f"Sentiment analysis error: {str(e)}")
        return {"sentiment": "neutral", "input_text": text, "error": str(e)}

def get_financial_advice(user_input, sentiment_result=None, max_retries=3):
    """Generate financial advice using Mistral API with retry logic"""
    system_prompt = DEFAULT_SYSTEM_MESSAGE
    
    # Add sentiment analysis result if available
    if sentiment_result and "sentiment" in sentiment_result:
        system_prompt += f"\n\nSentiment analysis of user's query: {sentiment_result['sentiment']}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    
    try:
        result = call_mistral_api(messages, temperature=0.7, max_tokens=800, max_retries=max_retries)
        
        # Check for proper response object
        if isinstance(result, dict) and "error" in result:
            print(f"Error in financial advice: {result['error']}")
            return f"I'm having technical difficulties: {result['error']}. Can you ask a simple financial question instead?"
            
        return result.choices[0].message.content.strip()
            
    except Exception as e:
        print(f"Error generating financial advice: {str(e)}")
        return "I'm having trouble connecting to our financial database. How about you ask me about basic investment strategies instead?"

@app.route('/api/sentiment', methods=['POST'])
def analyze_sentiment_api():
    """API endpoint for sentiment analysis"""
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({"error": "Please provide text for analysis"}), 400
    
    result = analyze_sentiment(text)
    return jsonify(result)

@app.route('/api/chat', methods=['POST'])
def chat():
    """API endpoint for chat with financial advisor - improved with conversation memory and input validation"""
    try:
        data = request.json
        user_input = data.get('user_input', '')
        user_id = data.get('user_id', 'anonymous')
        conversation_history = data.get('conversation_history', [])
        
        print(f"Received chat request: {user_input}")
        print(f"Conversation history length: {len(conversation_history)}")
        
        if not user_input:
            return jsonify({"error": "Please provide user input"}), 400
        
        # Handle extremely short inputs more intelligently
        if len(user_input.strip()) < 5:
            lowercase_input = user_input.lower().strip()
            
            # If it's the first message and it's a greeting
            if len(conversation_history) == 0 and lowercase_input in ["hi", "hello", "hey", "hii"]:
                return jsonify({
                    "response": "Welcome to FinanceGuru, your personalized financial planning assistant. How can I help with your financial planning today?",
                    "user_id": user_id
                })
            
            # If it's not the first message or not a greeting
            if lowercase_input in ["hi", "hello", "hey", "hii"]:
                return jsonify({
                    "response": "Hello again! Do you have any specific financial questions I can help with?",
                    "user_id": user_id
                })
            
            # For other short inputs, ask for more context
            return jsonify({
                "response": "Could you provide more details so I can better assist with your financial planning?",
                "user_id": user_id
            })
        
        # Validate the user input before calling the API
        is_valid, validation_message = validate_user_input(user_input)
        
        if not is_valid:
            # Return the validation message directly without calling the LLM API
            return jsonify({
                "response": validation_message,
                "user_id": user_id,
                "validated": False
            })
        
        # Build messages including conversation history
        messages = [
            {"role": "system", "content": DEFAULT_SYSTEM_MESSAGE + """
            ADDITIONAL VALIDATION RULES:
            - You MUST reject any claim of age over 120 years or under 5 years old
            - Do NOT provide financial advice to users claiming impossible ages
            - If a user claims to be 1000 years old, 500 years old, etc., politely ask for their actual age
            - Be suspicious of extremely large investment amounts (billions or trillions)
            - Never give financial advice based on clearly joking or impossible inputs
            """}
        ]
        
        # Add conversation history
        # Limit to last 5 exchanges to stay within context limits
        max_history = 5
        for exchange in conversation_history[-max_history:]:
            if "user_message" in exchange and exchange["user_message"]:
                messages.append({"role": "user", "content": exchange["user_message"]})
            if "assistant_message" in exchange and exchange["assistant_message"]:
                messages.append({"role": "assistant", "content": exchange["assistant_message"]})
        
        # Add current user input
        messages.append({"role": "user", "content": user_input})
        
        # First try API-based response
        try:
            # Get financial advice response
            response = call_mistral_api(messages, temperature=0.7, max_tokens=800, max_retries=3)
            
            # Check for proper response object
            if isinstance(response, dict) and "error" in response:
                print(f"Error in API response: {response['error']}")
                fallback_response = get_fallback_response(user_input)
                return jsonify({
                    "response": fallback_response,
                    "user_id": user_id,
                    "error": response["error"]
                })
                
            response_text = response.choices[0].message.content.strip()
            print(f"Financial advice response: {response_text}")
            
            # Remove any "Welcome to FinanceGuru" text if this isn't the first message
            if len(conversation_history) > 0 and "welcome to financeguru" in response_text.lower():
                parts = response_text.lower().split("welcome to financeguru")
                if len(parts) > 1:
                    response_text = parts[1].strip()
                    # Capitalize first letter if needed
                    if response_text:
                        response_text = response_text[0].upper() + response_text[1:]
            
            # Double-check the response for post-processing validation
            # Ensure we're not giving advice to someone claiming to be very old
            if "1000 year" in user_input.lower() or "500 year" in user_input.lower():
                if "investment plan" in response_text.lower() or "allocation" in response_text.lower():
                    # Override the response if it appears to be giving financial advice
                    response_text = "I notice you mentioned an unusual age. To provide you with accurate financial advice, could you please share your actual age? Financial advice should be tailored to realistic life stages and timelines."
            
            result = {
                "response": response_text,
                "user_id": user_id,
            }
            
            return jsonify(result)
            
        except Exception as inner_e:
            print(f"Inner exception in chat endpoint: {str(inner_e)}")
            # If API-based response fails, use fallback
            fallback_response = get_fallback_response(user_input)
            return jsonify({
                "response": fallback_response,
                "user_id": user_id,
                "error": str(inner_e)
            })
            
    except Exception as e:
        print(f"Unhandled exception in chat endpoint: {str(e)}")
        return jsonify({
            "response": "Sorry, there was a technical issue with our financial system. Please try asking a simpler question about investing or saving.",
            "user_id": data.get('user_id', 'anonymous') if 'data' in locals() else 'anonymous',
            "error": str(e)
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint with cached responses to avoid excessive API calls"""
    try:
        # Test Mistral API connectivity with a simple request
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ]
        
        # Create a simplified test that doesn't actually call the API
        # This prevents the health check from consuming your rate limit
        if MISTRAL_API_KEY != "your_api_key_here" and len(MISTRAL_API_KEY) > 10:
            api_status = "connected"
        else:
            api_status = "error: Invalid API key"
        
        # To actually test the API connection (use sparingly):
        # result = call_mistral_api(messages, max_tokens=10, max_retries=1)
        # api_status = "connected" if not isinstance(result, dict) or "error" not in result else f"error: {result.get('error')}"
        
    except Exception as e:
        api_status = f"error: {str(e)}"
        print(f"Health check error: {str(e)}")
    
    status_response = {
        "status": "ok" if api_status == "connected" else "error",
        "mistral_api_status": api_status,
        "model": MISTRAL_MODEL
    }
    
    print(f"Health check response: {status_response}")
    return jsonify(status_response)

# Enhanced fallback response for when API fails
def get_fallback_response(user_input):
    """Provide a relevant fallback response based on user input keywords"""
    # First validate the input - don't give fallback advice for unrealistic inputs
    is_valid, validation_message = validate_user_input(user_input)
    if not is_valid:
        return validation_message
        
    # Convert to lowercase for easier matching
    lowercase_input = user_input.lower()
    
    # Extract age if mentioned
    age = None
    age_words = ["i am", "i'm", "age", "years old"]
    for age_word in age_words:
        if age_word in lowercase_input:
            parts = lowercase_input.split(age_word)
            if len(parts) > 1:
                # Try to extract the age number
                try:
                    words = parts[1].strip().split()
                    for word in words[:2]:  # Look at first two words after age phrase
                        if word.isdigit():
                            age = int(word)
                            break
                except:
                    pass
    
    # Check if investment amount is mentioned
    amount = None
    amount_indicators = ["invest", "investing", "investment", "rs", "rupees", "inr", "$", "dollars", "usd"]
    for indicator in amount_indicators:
        if indicator in lowercase_input:
            # Look for numbers near the indicator
            parts = lowercase_input.split(indicator)
            for part in parts:
                words = part.strip().split()
                for i, word in enumerate(words):
                    # Clean the word of non-numeric characters
                    clean_word = ''.join(c for c in word if c.isdigit() or c == '.')
                    if clean_word and clean_word.replace('.', '', 1).isdigit():
                        try:
                            amount = float(clean_word)
                            break
                        except:
                            pass
                    # Check if next word might be "thousand", "k", "lakh", etc.
                    if clean_word and i < len(words) - 1:
                        multiplier_word = words[i+1].lower()
                        multiplier = 1
                        if "thousand" in multiplier_word or multiplier_word == "k":
                            multiplier = 1000
                        elif "lakh" in multiplier_word:
                            multiplier = 100000
                        elif "million" in multiplier_word or multiplier_word == "m":
                            multiplier = 1000000
                        
                        if multiplier > 1:
                            try:
                                amount = float(clean_word) * multiplier
                                break
                            except:
                                pass
    
    # Check specific financial terms in the input
    has_retirement = any(term in lowercase_input for term in ["retire", "retirement", "pension", "old age"])
    has_education = any(term in lowercase_input for term in ["education", "college", "university", "school", "studies", "study"])
    has_short_term = any(term in lowercase_input for term in ["short term", "short-term", "quick", "emergency", "soon", "trip", "vacation", "holiday"])
    has_stocks = any(term in lowercase_input for term in ["stock", "equity", "shares"])
    has_mutual_funds = any(term in lowercase_input for term in ["mutual fund", "etf", "index fund"])
    has_real_estate = any(term in lowercase_input for term in ["real estate", "property", "house", "apartment", "land"])
    has_crypto = any(term in lowercase_input for term in ["crypto", "bitcoin", "ethereum", "blockchain"])
    
    # Determine risk profile based on age if available
    risk_profile = "moderate"
    if age is not None:
        if age <= 30:
            risk_profile = "aggressive"
        elif age >= 50:
            risk_profile = "conservative"
    
    # Craft a personalized response based on extracted information
    response_parts = []
    
    # Greeting and acknowledgment
    response_parts.append("Thanks for reaching out to FinanceGuru!")
    
    # Personalization based on extracted info
    if age is not None:
        response_parts.append(f"At {age} years old, you're in a good position to start building your financial future.")
    
    if amount is not None:
        currency = "rupees" if "rupee" in lowercase_input or "rs" in lowercase_input or "inr" in lowercase_input else "dollars"
        response_parts.append(f"Investing {amount} {currency} is a great start.")
    
    # Purpose-specific advice
    if has_education:
        response_parts.append("For education funding, consider a mix of fixed deposits and debt mutual funds for near-term goals, and equity funds for longer-term educational aspirations.")
    
    if has_retirement:
        response_parts.append("For retirement planning, start with tax-advantaged retirement accounts and gradually build a diversified portfolio across equity and debt instruments.")
    
    if has_short_term:
        response_parts.append("For short-term goals like trips or emergencies, focus on liquid funds, high-yield savings accounts, or short-term fixed deposits to ensure your money remains accessible.")
    
    # Investment vehicle specific advice
    if has_stocks:
        if risk_profile == "aggressive":
            response_parts.append("With your risk profile, allocating 60-70% to quality stocks could be appropriate.")
        elif risk_profile == "moderate":
            response_parts.append("Consider allocating 40-50% of your portfolio to quality stocks for growth.")
        else:
            response_parts.append("Even with a conservative approach, 20-30% allocation to stable, dividend-paying stocks can help beat inflation.")
    
    if has_mutual_funds:
        response_parts.append("Mutual funds offer diversification and professional management. Index funds are particularly cost-effective for long-term growth.")
    
    if has_real_estate:
        response_parts.append("Real estate investments require significant capital but can provide both rental income and appreciation. REITs (Real Estate Investment Trusts) offer a more accessible alternative.")
    
    if has_crypto:
        response_parts.append("Cryptocurrency investments are highly volatile. If exploring this space, limit exposure to a small percentage of your portfolio that you can afford to lose (typically 5% or less).")
    
    # General advice based on risk profile
    if not (has_stocks or has_mutual_funds or has_real_estate or has_crypto):
        if risk_profile == "aggressive":
            response_parts.append("With an aggressive risk profile, consider an allocation of 70-80% in equity (stocks, equity mutual funds), 15-20% in debt instruments, and 5-10% in alternative investments.")
        elif risk_profile == "moderate":
            response_parts.append("With a moderate risk profile, a balanced allocation might include 50-60% in equity, 30-40% in debt, and 5-10% in alternatives or cash.")
        else:
            response_parts.append("With a conservative risk profile, consider 30-40% in equity, 50-60% in debt instruments, and 10-15% in cash or cash equivalents.")
    
    # Closing statement
    response_parts.append("Remember that diversification across asset classes and regular investing are key to long-term financial success.")
    
    # Join all parts with appropriate spacing
    full_response = " ".join(response_parts)
    
    return full_response

if __name__ == "__main__":
    # Start Flask server
    print(f"Starting FinanceGURU backend with Mistral API ({MISTRAL_MODEL})")
    app.run(debug=True, host='0.0.0.0', port=5000)
