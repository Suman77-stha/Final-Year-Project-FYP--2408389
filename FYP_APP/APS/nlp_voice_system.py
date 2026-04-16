# ===================== IMPORTS =====================
import datetime
import os
import django
import pyttsx3
import re
import speech_recognition as sr
import requests
from django.utils import timezone
from datetime import timedelta
from transformers import AutoTokenizer, AutoModelForCausalLM

# ---------------- DJANGO SETUP ----------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FYP.settings")
django.setup()  # must come before importing models

# ---------------- HF TOKEN (optional) ----------------
HF_TOKEN = os.getenv("HF_TOKEN")
if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN

# Now import Django models
from FYP_APP.models import Portfolio, Transaction

from FYP_APP.APS.lstm_model import predict
from FYP_APP.APS.API_Data import (
    calculate_indicators,
    get_news_sentiment,
    decision_engine,
)
from FYP_APP.APS.StockAPI import get_stock_data

# ===================== MEMORY =====================
conversation_memory = []

def update_memory(user, ai):
    conversation_memory.append(f"User: {user}")
    conversation_memory.append(f"AI: {ai}")
    if len(conversation_memory) > 20:
        conversation_memory.pop(0)

def get_memory_context():
    return "\n".join(conversation_memory)

# ===================== VOICE =====================
def initialize_engine():
    engine = pyttsx3.init("sapi5")
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    engine.setProperty('rate', engine.getProperty('rate') - 50)
    engine.setProperty('volume', min(engine.getProperty('volume') + 0.25, 1.0))
    return engine

def Speak(text):
    engine = initialize_engine()
    engine.say(text)
    engine.runAndWait()

# ===================== LISTEN =====================
def Listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        print("Listening...", end="", flush=True)
        audio = r.listen(source, phrase_time_limit=8)
    try:
        print("\rRecognizing...", end="", flush=True)
        query = r.recognize_google(audio, language='en-NP')
        print(f"\nUser said: {query}\n")
    except:
        Speak("Say that again please")
        return "none"
    return query.lower()

# ===================== LOAD LLM =====================
print("Loading AI model...")
MODEL_NAME = "distilgpt2"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
model.eval()

# ===== FIX PAD TOKEN ISSUE =====
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = tokenizer.eos_token_id

# ===================== LLM RESPONSE =====================
def generate_llm_response(prompt):
    context = get_memory_context()
    full_prompt = f"{context}\nUser: {prompt}\nAI:"
    inputs = tokenizer.encode(full_prompt, return_tensors="pt")
    attention_mask = (inputs != tokenizer.pad_token_id).long()  # fix attention mask warning
    outputs = model.generate(
        inputs,
        attention_mask=attention_mask,
        max_new_tokens=80,
        temperature=0.6,
        top_p=0.85,
        do_sample=True,
        repetition_penalty=1.2,      
        pad_token_id=tokenizer.eos_token_id
        )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response.split("AI:")[-1].strip()

# ===================== HELPERS =====================
def extract_days(user_input):
    user_input = user_input.lower()
    match = re.search(r'(\d+)\s*day', user_input)
    if match:
        return int(match.group(1))
    if "tomorrow" in user_input:
        return 1
    if "next week" in user_input:
        return 7
    if "next month" in user_input:
        return 30
    if "today" in user_input:
        return 1
    if "yesterday" in user_input:
        return 2
    if "week" in user_input:
        return 7
    if "month" in user_input:
        return 30
    return None

def get_symbol_from_api(query):
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={query}"
        data = requests.get(url).json()
        quotes = data.get("quotes", [])
        if quotes:
            return quotes[0].get("symbol")
    except:
        return None
    return None

# ===================== COMPANY MAP =====================
company_map = {
    "apple": "AAPL",
    "tesla": "TSLA",
    "google": "GOOGL",
    "amazon": "AMZN",
    "microsoft": "MSFT",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "nvidia": "NVDA",
    "intel": "INTC",
    "amd": "AMD",
    "uber": "UBER",
    "lyft": "LYFT",
    "paypal": "PYPL",
    "adobe": "ADBE",
    "salesforce": "CRM",
    "twitter": "X",
}

def extract_symbol(user_input):
    words = user_input.split()
    # ticker detection (TSLA, AAPL)
    for word in words:
        if word.isupper() and len(word) <= 5:
            return word
    # company name detection
    for name, sym in company_map.items():
        if name in user_input:
            return sym
    # fallback API
    return get_symbol_from_api(user_input)

def get_user_transactions(user, days=5):
    try:
        since_date = timezone.now() - timedelta(days=days)

        transactions = Transaction.objects.filter(
            user=user,
            created_at__date__gte=since_date.date()
        ).order_by('-created_at')

        if not transactions.exists():
            return f"No transactions found in last {days} days."

        result = f"\nLast {days} Days Transactions:\n"
        result += "-" * 70 + "\n"
        result += f"{'Type':<8}{'Symbol':<10}{'Qty':<8}{'Price':<12}{'Date':<12}\n"
        result += "-" * 70 + "\n"

        for t in transactions:
            result += (
                f"{t.transaction_type.upper():<8}"
                f"{t.symbol:<10}"
                f"{t.quantity:<8}"
                f"{float(t.price):<12.2f}"
                f"{t.created_at.strftime('%Y-%m-%d')}\n"
            )

        return result

    except Exception as e:
        print("Transaction error:", e)
        return "Unable to fetch transaction history."

def get_user_portfolio(user):
    try:
        portfolio = Portfolio.objects.filter(user=user)

        if not portfolio.exists():
            return "Your portfolio is empty."

        result = "\nYour Portfolio:\n"
        result += "-" * 60 + "\n"
        result += f"{'Symbol':<10}{'Quantity':<12}{'Avg Price':<15}\n"
        result += "-" * 60 + "\n"

        for p in portfolio:
            result += (
                f"{p.symbol:<10}"
                f"{p.quantity:<12}"
                f"{float(p.avg_price):<15.2f}\n"
            )

        return result

    except Exception as e:
        print("Portfolio error:", e)
        return "Unable to fetch portfolio."
    
def get_single_stock(user, symbol):
    try:
        stock = Portfolio.objects.filter(user=user, symbol=symbol).first()

        if stock:
            return f"You have {stock.quantity} shares of {symbol}."
        else:
            return f"You do not own {symbol}."

    except Exception as e:
        print("Stock error:", e)
        return "Error fetching stock data."

# ===================== CHATBOT LOGIC =====================
def chatbot_logic(user_input, user=None):
    user_input = user_input.lower().strip()

    # ===== GREETING =====
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    if user_input in greetings:
        hour = datetime.datetime.now().hour
        if hour < 12:
            return "Good morning Suman, how can I help you?"
        elif hour < 17:
            return "Good afternoon Suman, how can I help you?"
        else:
            return "Good evening Suman, how can I help you?"
    if "how are you" in user_input:
        return "I'm doing great! How can I help you?"
    if "your name" in user_input:
        return "I am your AI stock assistant."

    # ===== SYMBOL =====
    symbol = extract_symbol(user_input)

    # ===== PREDICTION =====
    if symbol and any(x in user_input for x in ["prediction", "forecast", "future price", "predict"]):
        future_days = extract_days(user_input)
        if not future_days:
            return "Please specify how many days (e.g., 5 days or next week)."
        try:
            prediction = predict(symbol, future_days)
            # fix: access dict instead of attribute
            future_data = prediction.get("future_days", "Data not available")
            return f"The prediction data of {symbol} for {future_days} days is {future_data}."
        except Exception as e:
            print("Prediction error:", e)
            return "Unable to generate prediction right now."
    
    # ===== PRICE =====
    if symbol and any(x in user_input for x in [
        "what is the price","what's the price","whats the price","how much is",
        "stock price","share price","quote","latest price","market price","how much does","how much for",
        "value of","trading price","cost of","how is the stock","how much money is","current share price","latest quote","current price"
        ""
    ]):
        try:
            price_data = get_stock_data(symbol)
            current_price = price_data.get('close_price')
            return f"The current price of {symbol} is {current_price}."
        except Exception as e:
            print("Price error:", e)
            return "Unable to fetch price right now."

    # ===== TRANSACTIONS =====
    if any(x in user_input for x in [
        "transaction","transactions","transaction history","show my transactions","show my transaction history",
        "my trading history","my trades","recent transactions","recent trades","what did I buy","what did I sell",
        "my stock activity","trade history","trading activity","show my trades","latest transactions",
        "recent stock activity","recent stock activity","my trading summary","trading history"
    ]):
        if user is None:
            return "User not authenticated."
        days = extract_days(user_input)
        if not days:
            days = 5  # default
        return get_user_transactions(user, days)

    # ===== BUY / ANALYSIS =====
    if symbol and any(x in user_input for x in ["should i buy", "what if buy", "buy or not", "is it good to buy"]):
        try:
            price_data = get_stock_data(symbol)
            indicators = calculate_indicators(symbol)
            news = get_news_sentiment(symbol)
            decision = decision_engine(price_data, indicators, news)

            current_price = price_data.get("close_price")
            action = decision.get("action")
            confidence = decision.get("confidence_score")
            trend = decision.get("trend")
            strength = decision.get("strength")
            reason = decision.get("reason")

            if action == "BUY":
                suggestion = f"The trend is {trend} ({strength}). Indicators: {reason}. Confidence: {confidence}%. It looks like a good time to buy."
            else:
                suggestion = f"The trend is {trend} ({strength}). Indicators: {reason}. Confidence: {confidence}%. Hold for now."

            return f"The current price of {symbol} is {current_price}. {suggestion}"

        except Exception as e:
            print("Analysis error:", e)
            return "Unable to analyze stock right now."

    # ===== SELL =====
    if symbol and any(x in user_input for x in ["sell", "should i sell", "sell or not"]):
        try:
            exists = Portfolio.objects.filter(symbol=symbol).exists()
            if not exists:
                return f"You do not own {symbol} in your portfolio."

            price_data = get_stock_data(symbol)
            indicators = calculate_indicators(symbol)
            news = get_news_sentiment(symbol)
            decision = decision_engine(price_data, indicators, news)

            current_price = price_data.get("close_price")
            action = decision.get("action")
            confidence = decision.get("confidence_score")
            trend = decision.get("trend")
            strength = decision.get("strength")
            reason = decision.get("reason")

            if action == "SELL":
                suggestion = f"The trend is {trend} ({strength}). Indicators: {reason}. Confidence: {confidence}%. It is a good time to sell."
            elif action == "BUY":
                suggestion = f"The trend is {trend} ({strength}). Indicators: {reason}. Confidence: {confidence}%. Selling now may not be ideal; the stock still shows positive signals."
            else:
                suggestion = f"The trend is {trend} ({strength}). Indicators: {reason}. Confidence: {confidence}%. Hold for now."

            return f"The current price of {symbol} is {current_price}. {suggestion}"

        except Exception as e:
            print("Sell error:", e)
            return "Unable to analyze selling decision."
    
    
    # ===== PORTFOLIO =====
    # ===== PORTFOLIO =====
    if any(x in user_input for x in ["portfolio","my portfolio","show my portfolio","what do I own","what stocks do I have","my holdings"]):
        
        if user is None:
            return "User not authenticated."
    
        # 👉 If user is asking about specific stock
        if any(x in user_input for x in ["how many", "quantity", "qty", "shares"]):
            symbol = extract_symbol(user_input)
    
            if symbol:
                return get_single_stock(user, symbol)
    
        # 👉 Otherwise show full portfolio
        return get_user_portfolio(user)
    
        # ===== DEFAULT LLM =====
    return generate_llm_response(user_input)
    
# ===================== MAIN =====================
if __name__ == "__main__":
    Speak("AI assistant started. How can I help you?")

    # Option to choose Text or Voice
    mode = input("Choose mode: (1) Voice, (2) Text: ").strip()
    while True:
        if mode == "1":
            query = Listen()
        else:
            query = input("You: ").strip().lower()

        if query == "none" or query == "":
            continue
        if "exit" in query or "stop" in query:
            Speak("Goodbye")
            print("AI: Goodbye")
            break

        response = chatbot_logic(query)
        update_memory(query, response)
        print("AI:", response)
        Speak(response)