import logging
import os
import random
import re
from dataclasses import dataclass, asdict
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import pyttsx3
import requests
import speech_recognition as sr
from django.utils import timezone
from sentence_transformers import SentenceTransformer, util
from thefuzz import fuzz, process

from FYP_APP.APS.StockAPI import get_stock_data
from FYP_APP.models import Portfolio, Transaction
from FYP_APP.prediction.ai_suggestion import generate_ai_suggestion
from FYP_APP.prediction.predict_system import predict

logger = logging.getLogger(__name__)

STOCK_STOPWORDS = {
    "i", "me", "my", "myself", "mine", "we", "our", "ours",
    "share", "shares", "stock", "stocks", "portfolio", "profit", "loss",
    "sell", "buy", "current", "price", "all", "total", "owned",
    "have", "has", "had", "from", "if", "then", "that", "what", "how",
    "much", "do", "make", "get", "cr",
}

VALID_TICKER_OVERRIDES = set(company_map.values()) if "company_map" in globals() else set()

# -----------------------------
# Formatting Layer
# -----------------------------

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fmt_currency(value: Any) -> str:
    return f"${safe_float(value):,.2f}"


def fmt_percent(value: Any, from_fraction: bool = False) -> str:
    v = safe_float(value)
    if from_fraction:
        v *= 100.0
    return f"{v:.2f}%"


def normalize_symbol(symbol: Optional[str]) -> Optional[str]:
    if not symbol:
        return None
    return symbol.strip().upper()


# -----------------------------
# NLP Layer + Entity Extraction
# -----------------------------

intent_model: Optional[SentenceTransformer] = None
intent_model_failed = False

intent_prototypes = {
    "GREETING": ["hello", "hi", "good morning", "hey there"],
    "BUY_ANALYSIS": ["should i buy", "good time to buy", "worth buying", "enter position"],
    "SELL_ANALYSIS": ["should i sell", "exit this stock", "sell now"],
    "HOLD_ANALYSIS": ["should i hold", "keep holding", "hold this position"],
    "PRICE_QUERY": ["price", "quote", "current price", "trading at"],
    "PROFIT_ANALYSIS": ["profit", "gain", "if i sell", "unrealized profit"],
    "LOSS_ANALYSIS": ["loss", "drawdown", "down how much"],
    "PORTFOLIO_QUERY": ["my portfolio", "my holdings", "what do i own"],
    "BUY_PRICE_QUERY": ["buy price", "average price", "entry price"],
    "CURRENT_VALUE_QUERY": ["current value", "position value", "worth now"],
    "STOCK_NEWS_QUERY": ["news", "latest update", "headline"],
    "TECHNICAL_ANALYSIS": ["technical analysis", "rsi", "macd", "trend analysis"],
    "FORECAST_QUERY": ["forecast", "prediction", "next week", "future price"],
    "WATCHLIST_QUERY": ["watchlist", "tracked stocks"],
    "MARKET_SENTIMENT": ["market sentiment", "bullish or bearish", "market mood"],
    "RISK_ANALYSIS": ["risk", "volatility", "safer", "which is safer"],
    "TRANSACTIONS": ["transactions", "trade history", "recent trades"],
    "GENERAL_FINANCE_QUERY": ["finance", "investing", "stocks"],
}

company_map = {
    "apple": "AAPL",
    "tesla": "TSLA",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "microsoft": "MSFT",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "nvidia": "NVDA",
    "intel": "INTC",
    "amd": "AMD",
    "uber": "UBER",
    "paypal": "PYPL",
    "adobe": "ADBE",
    "salesforce": "CRM",
}
VALID_TICKER_OVERRIDES = set(company_map.values())

SYMBOL_ALIASES = {
    "GOOGLE": "GOOGL",
    "FACEBOOK": "META",
}


def get_intent_model() -> Optional[SentenceTransformer]:
    global intent_model, intent_model_failed
    if intent_model is not None:
        return intent_model
    if intent_model_failed:
        return None
    try:
        intent_model = SentenceTransformer("all-MiniLM-L6-v2")
        return intent_model
    except Exception:
        intent_model_failed = True
        logger.exception("Intent model load failed")
        return None


def _keyword_intent(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["hello", "hi", "hey"]):
        return "GREETING"
    if "buy price" in t or "avg price" in t or "average price" in t:
        return "BUY_PRICE_QUERY"
    if "current value" in t or "worth" in t:
        return "CURRENT_VALUE_QUERY"
    if "profit" in t or "gain" in t:
        return "PROFIT_ANALYSIS"
    if "loss" in t:
        return "LOSS_ANALYSIS"
    if "forecast" in t or "predict" in t:
        return "FORECAST_QUERY"
    if "should i buy" in t or "buy" in t:
        return "BUY_ANALYSIS"
    if "should i sell" in t or "sell" in t:
        return "SELL_ANALYSIS"
    if "hold" in t:
        return "HOLD_ANALYSIS"
    if "price" in t or "quote" in t:
        return "PRICE_QUERY"
    if "portfolio" in t or "holding" in t or "own" in t:
        return "PORTFOLIO_QUERY"
    if "transaction" in t or "trade history" in t:
        return "TRANSACTIONS"
    if "risk" in t or "safer" in t:
        return "RISK_ANALYSIS"
    if "technical" in t or "rsi" in t or "macd" in t:
        return "TECHNICAL_ANALYSIS"
    if "watchlist" in t:
        return "WATCHLIST_QUERY"
    if "sentiment" in t:
        return "MARKET_SENTIMENT"
    if "news" in t:
        return "STOCK_NEWS_QUERY"
    return "GENERAL_FINANCE_QUERY"


def detect_intent(text: str) -> str:
    model = get_intent_model()
    if not model:
        return _keyword_intent(text)

    try:
        text_embedding = model.encode(text, convert_to_tensor=True)
        best_intent = "GENERAL_FINANCE_QUERY"
        best_score = 0.0
        for intent, phrases in intent_prototypes.items():
            proto = model.encode(phrases, convert_to_tensor=True)
            score = util.cos_sim(text_embedding, proto)[0].max().item()
            if score > best_score:
                best_score = score
                best_intent = intent
        if best_score < 0.35:
            return _keyword_intent(text)
        return best_intent
    except Exception:
        logger.exception("Intent detection failed")
        return _keyword_intent(text)


def extract_days(user_input: str) -> int:
    t = user_input.lower()
    m = re.search(r"(\d+)\s*day", t)
    if m:
        return max(1, min(365, int(m.group(1))))
    if "tomorrow" in t:
        return 1
    if "next week" in t or "week" in t:
        return 7
    if "next month" in t or "month" in t:
        return 30
    return 7


def extract_symbols(user_input: str) -> List[str]:
    text = (user_input or "").strip()
    lower_text = text.lower()
    symbol_candidates: List[Tuple[str, int]] = []

    # company direct match first (high confidence)
    for cname, ticker in company_map.items():
        if re.search(rf"\b{re.escape(cname)}\b", lower_text):
            symbol_candidates.append((ticker, 100))

    # ticker regex: min 2 chars, max 5 chars (prevents pronoun "I")
    for s in re.findall(r"\b[A-Z]{2,5}\b", text):
        normalized = normalize_symbol(s)
        if not normalized:
            continue
        if normalized.lower() in STOCK_STOPWORDS:
            continue
        normalized = SYMBOL_ALIASES.get(normalized, normalized)
        # Allow common tickers from map immediately, keep others with lower confidence.
        confidence = 95 if normalized in VALID_TICKER_OVERRIDES else 75
        symbol_candidates.append((normalized, confidence))

    # fuzzy company resolution for noisy STT input
    tokens = re.findall(r"[A-Za-z]{2,}", lower_text)
    clean_tokens = [t for t in tokens if t not in STOCK_STOPWORDS]
    logger.info("NLP tokens=%s clean_tokens=%s", tokens, clean_tokens)

    if clean_tokens:
        phrase = " ".join(clean_tokens)
        best = process.extract(phrase, list(company_map.keys()), scorer=fuzz.partial_ratio, limit=3)
        for name, score in best:
            if score >= 82:
                symbol_candidates.append((company_map[name], score))

        # token-level fuzzy as fallback (helps "microsft", "aple")
        for token in clean_tokens:
            b = process.extractOne(token, list(company_map.keys()), scorer=fuzz.ratio)
            if b:
                name, score = b
                if score >= 85:
                    symbol_candidates.append((company_map[name], score))

    # rank by confidence and deduplicate
    symbol_candidates.sort(key=lambda x: x[1], reverse=True)
    seen = set()
    resolved = []
    for sym, _score in symbol_candidates:
        ns = normalize_symbol(sym)
        if not ns or ns in seen:
            continue
        seen.add(ns)
        resolved.append(ns)

    logger.info("Extracted symbol candidates=%s resolved=%s", symbol_candidates, resolved)
    return resolved


# -----------------------------
# Memory Layer
# -----------------------------

@dataclass
class ConversationMemory:
    last_intent: Optional[str] = None
    active_symbol: Optional[str] = None
    compared_symbols: Optional[List[str]] = None
    last_user_portfolio_symbol: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["compared_symbols"] is None:
            d["compared_symbols"] = []
        return d

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "ConversationMemory":
        d = d or {}
        return cls(
            last_intent=d.get("last_intent"),
            active_symbol=d.get("active_symbol"),
            compared_symbols=d.get("compared_symbols") or [],
            last_user_portfolio_symbol=d.get("last_user_portfolio_symbol"),
        )


# -----------------------------
# Portfolio Intelligence Layer
# -----------------------------

def get_portfolio_position(user, symbol: str) -> Optional[Portfolio]:
    if not user:
        return None
    return Portfolio.objects.filter(user=user, symbol=symbol, quantity__gt=0).first()


def estimate_position_metrics(user, symbol: str) -> Optional[Dict[str, float]]:
    position = get_portfolio_position(user, symbol)
    if not position:
        return None

    price_data = get_stock_data(symbol)
    current_price = safe_float(price_data.get("close_price") if price_data else 0)

    qty = safe_float(position.quantity)
    avg_price = safe_float(position.avg_price)
    invested = qty * avg_price
    current_value = qty * current_price
    unrealized = current_value - invested
    gain_pct = (unrealized / invested * 100) if invested > 0 else 0

    return {
        "quantity": qty,
        "avg_price": avg_price,
        "current_price": current_price,
        "invested": invested,
        "current_value": current_value,
        "unrealized": unrealized,
        "gain_pct": gain_pct,
    }


def summarize_transactions(user, days: int = 7) -> str:
    since = timezone.now() - timedelta(days=days)
    txs = Transaction.objects.filter(user=user, created_at__gte=since).order_by("-created_at")
    if not txs.exists():
        return f"No transactions found in the last {days} days."

    lines = [f"Recent transactions ({days} days):"]
    for tx in txs[:8]:
        lines.append(
            f"- {tx.transaction_type} {tx.quantity} {tx.symbol} at {fmt_currency(tx.price)} on {tx.created_at.strftime('%Y-%m-%d')}"
        )
    return "\n".join(lines)


# -----------------------------
# Financial Reasoning Layer
# -----------------------------

def safe_ai_suggestion(symbol: str, user_has_stock: bool) -> Dict[str, Any]:
    try:
        result = generate_ai_suggestion(symbol, user_has_stock)
        return {
            "action": result.get("action", "HOLD"),
            "confidence_score": safe_float(result.get("confidence_score", 50)),
            "trend": result.get("trend", "Neutral"),
            "strength": result.get("strength", "Moderate"),
            "reason": result.get("reason", "Model and momentum signals are mixed."),
        }
    except Exception:
        logger.exception("AI suggestion failed for %s", symbol)
        return {
            "action": "HOLD",
            "confidence_score": 52.0,
            "trend": "Neutral",
            "strength": "Moderate",
            "reason": "Technical indicators are incomplete right now; using conservative fallback.",
        }


def safe_forecast(symbol: str, days: int) -> Optional[Dict[str, Any]]:
    try:
        return predict(symbol, future_days=days)
    except Exception:
        logger.exception("Forecast failed for %s", symbol)
        return None


def explain_risk(volatility_hint: str, gain_pct: Optional[float] = None) -> str:
    risk_text = {
        "Strong": "Risk remains elevated due to stronger price swings.",
        "Weak": "Risk is relatively moderate but trend conviction is weaker.",
        "Moderate": "Risk is balanced with no extreme warning from the model.",
    }
    base = risk_text.get(volatility_hint, risk_text["Moderate"])
    if gain_pct is None:
        return base
    if gain_pct < -10:
        return base + " Your position is currently under pressure, so capital protection matters."
    if gain_pct > 10:
        return base + " You are in a healthy unrealized gain zone; consider trailing-risk discipline."
    return base


# -----------------------------
# Response Generation Layer
# -----------------------------

def respond_price(symbol: str, price_data: Dict[str, Any]) -> str:
    p = fmt_currency(price_data.get("close_price", 0))
    templates = [
        f"{symbol} is currently trading around {p}.",
        f"Latest quote for {symbol} is near {p}.",
        f"Right now {symbol} is priced at approximately {p}.",
    ]
    return random.choice(templates)


def respond_analysis(symbol: str, suggestion: Dict[str, Any], position_metrics: Optional[Dict[str, float]]) -> str:
    action = suggestion["action"]
    confidence = fmt_percent(suggestion["confidence_score"])
    trend = suggestion["trend"]
    reason = suggestion["reason"]
    strength = suggestion.get("strength", "Moderate")

    opening = f"{symbol} currently shows a {trend.lower()} profile."
    rec = f"Recommendation: {action} (confidence {confidence})."
    rationale = f"Why: {reason}."

    if position_metrics:
        pnl = fmt_currency(position_metrics["unrealized"])
        gp = fmt_percent(position_metrics["gain_pct"])
        pos = f"Your current position: {int(position_metrics['quantity'])} shares, average cost {fmt_currency(position_metrics['avg_price'])}, unrealized P/L {pnl} ({gp})."
    else:
        pos = "You do not currently hold this position, so this is an entry-focused view."

    risk = explain_risk(strength, position_metrics["gain_pct"] if position_metrics else None)
    return " ".join([opening, rec, rationale, pos, risk])


def respond_forecast(symbol: str, forecast_data: Optional[Dict[str, Any]], days: int) -> str:
    if not forecast_data:
        return f"I could not run the full {days}-day forecast for {symbol} right now, but I can still provide technical and risk-based guidance."

    current_price = fmt_currency(forecast_data.get("current_price", 0))
    future = forecast_data.get("future_days") or []
    target = fmt_currency(future[-1] if future else forecast_data.get("predicted_price", 0))
    acc = fmt_percent(max(0.0, 100 - safe_float(forecast_data.get("mape", 100))))

    return (
        f"My {days}-day projection for {symbol} starts from {current_price} and points toward about {target}. "
        f"Model confidence proxy is around {acc}; treat this as probabilistic guidance, not certainty."
    )


def respond_position_metrics(symbol: str, metrics: Optional[Dict[str, float]]) -> str:
    if not metrics:
        return f"I could not find an active {symbol} position in your portfolio."
    return (
        f"You hold {int(metrics['quantity'])} shares of {symbol} at an average buy price of {fmt_currency(metrics['avg_price'])}. "
        f"Current price is about {fmt_currency(metrics['current_price'])}, position value is {fmt_currency(metrics['current_value'])}, "
        f"and unrealized P/L is {fmt_currency(metrics['unrealized'])} ({fmt_percent(metrics['gain_pct'])})."
    )


def respond_sell_profit(symbol: str, metrics: Optional[Dict[str, float]]) -> str:
    if not metrics:
        return (
            f"I could not find an active {symbol} position in your portfolio. "
            "If you meant another stock, please share the company name or ticker."
        )
    return (
        f"You currently own {int(metrics['quantity'])} shares of {symbol} at an average buy price of {fmt_currency(metrics['avg_price'])}. "
        f"At the current market price near {fmt_currency(metrics['current_price'])}, selling all shares would result in an estimated "
        f"{'profit' if metrics['unrealized'] >= 0 else 'loss'} of {fmt_currency(metrics['unrealized'])} "
        f"({fmt_percent(metrics['gain_pct'])})."
    )


# -----------------------------
# Voice utilities
# -----------------------------

def initialize_engine():
    engine = pyttsx3.init("sapi5")
    voices = engine.getProperty("voices")
    engine.setProperty("voice", voices[1].id)
    engine.setProperty("rate", engine.getProperty("rate") - 40)
    return engine


def Speak(text: str):
    try:
        engine = initialize_engine()
        engine.say(text)
        engine.runAndWait()
    except Exception:
        logger.exception("Text-to-speech failed")


def Listen() -> str:
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        audio = r.listen(source, phrase_time_limit=8)
    try:
        return r.recognize_google(audio, language="en-NP").lower()
    except Exception:
        return ""


# -----------------------------
# Orchestration Layer
# -----------------------------

def _resolve_symbols(user_input: str, memory: ConversationMemory) -> List[str]:
    symbols = extract_symbols(user_input)
    if not symbols and memory.active_symbol:
        symbols = [memory.active_symbol]
    logger.info("Resolved symbols=%s active_symbol=%s", symbols, memory.active_symbol)
    return symbols


def _compare_risk(symbols: List[str], user=None) -> str:
    if len(symbols) < 2:
        return "Please mention two stocks for a risk comparison."
    scores = []
    for s in symbols[:2]:
        sug = safe_ai_suggestion(s, bool(get_portfolio_position(user, s)) if user else False)
        risk_score = 100 - safe_float(sug.get("confidence_score", 50))
        if sug.get("trend", "").lower() == "bearish":
            risk_score += 8
        scores.append((s, risk_score, sug))
    scores.sort(key=lambda x: x[1])
    safer, riskier = scores[0], scores[1]
    return (
        f"Between {safer[0]} and {riskier[0]}, {safer[0]} looks relatively safer right now based on trend stability and model confidence. "
        f"{safer[0]}: {safer[2].get('trend')} trend, confidence {fmt_percent(safer[2].get('confidence_score', 50))}. "
        f"{riskier[0]}: {riskier[2].get('trend')} trend, confidence {fmt_percent(riskier[2].get('confidence_score', 50))}."
    )


def chatbot_logic(
    user_input: str,
    user=None,
    memory_state: Optional[Dict[str, Any]] = None,
    return_state: bool = False,
):
    text = (user_input or "").strip()
    if not text:
        response = "Please share a stock question, for example: 'Should I buy MSFT?'"
        return (response, memory_state or {}) if return_state else response

    memory = ConversationMemory.from_dict(memory_state)
    intent = detect_intent(text)
    symbols = _resolve_symbols(text, memory)
    symbol = symbols[0] if symbols else None
    logger.info("Detected intent=%s raw_text=%s", intent, text)

    # follow-up intent continuity
    if intent == "GENERAL_FINANCE_QUERY" and memory.last_intent and symbol:
        intent = memory.last_intent

    if symbol:
        memory.active_symbol = symbol
    if len(symbols) >= 2:
        memory.compared_symbols = symbols[:2]

    try:
        if intent == "GREETING":
            response = random.choice([
                "Hello. I can help with stock analysis, portfolio insights, and trade decisions.",
                "Hi. Ask me about price, forecast, risk, or your portfolio positions.",
            ])

        elif intent == "TRANSACTIONS":
            response = "Please log in to view transactions." if user is None else summarize_transactions(user, days=7)

        elif intent in {"PORTFOLIO_QUERY", "BUY_PRICE_QUERY", "CURRENT_VALUE_QUERY", "PROFIT_ANALYSIS", "LOSS_ANALYSIS"}:
            if user is None:
                response = "Please log in so I can analyze your portfolio and transaction history."
            else:
                if not symbol and memory.last_user_portfolio_symbol:
                    symbol = memory.last_user_portfolio_symbol
                if symbol:
                    metrics = estimate_position_metrics(user, symbol)
                    if intent in {"PROFIT_ANALYSIS", "LOSS_ANALYSIS"} and any(
                        k in text.lower() for k in ["sell", "exit", "profit", "gain", "loss"]
                    ):
                        response = respond_sell_profit(symbol, metrics)
                    else:
                        response = respond_position_metrics(symbol, metrics)
                    if metrics:
                        memory.last_user_portfolio_symbol = symbol
                else:
                    holdings = Portfolio.objects.filter(user=user, quantity__gt=0)
                    if not holdings.exists():
                        response = "Your portfolio is currently empty."
                    else:
                        response = (
                            "I couldn't determine which stock you're referring to. "
                            "Please specify the company or ticker symbol."
                        )
                        lines = ["Your active holdings (for quick reference):"]
                        for p in holdings[:8]:
                            lines.append(f"- {p.symbol}: {p.quantity} shares, avg {fmt_currency(p.avg_price)}")
                        response = response + "\n" + "\n".join(lines)

        elif intent == "PRICE_QUERY":
            if not symbol:
                response = "Please specify the stock symbol you want to price-check."
            else:
                price_data = get_stock_data(symbol) or {}
                if not price_data:
                    response = f"I could not fetch a live quote for {symbol} right now."
                else:
                    response = respond_price(symbol, price_data)

        elif intent in {"BUY_ANALYSIS", "SELL_ANALYSIS", "HOLD_ANALYSIS", "TECHNICAL_ANALYSIS", "RISK_ANALYSIS", "MARKET_SENTIMENT"}:
            if intent == "RISK_ANALYSIS" and len(symbols) < 2 and memory.compared_symbols and "which" in text.lower():
                symbols = memory.compared_symbols
            if intent == "RISK_ANALYSIS" and len(symbols) >= 2:
                response = _compare_risk(symbols, user=user)
            elif not symbol:
                response = "Tell me which stock you want analyzed, for example: 'Analyze MSFT'."
            else:
                user_has_stock = bool(get_portfolio_position(user, symbol)) if user else False
                suggestion = safe_ai_suggestion(symbol, user_has_stock)
                metrics = estimate_position_metrics(user, symbol) if user else None
                response = respond_analysis(symbol, suggestion, metrics)

        elif intent == "FORECAST_QUERY":
            if not symbol:
                response = "Please provide a stock symbol for forecasting."
            else:
                days = extract_days(text)
                forecast = safe_forecast(symbol, days)
                response = respond_forecast(symbol, forecast, days)

        elif intent == "WATCHLIST_QUERY":
            response = "Watchlist insights are available on your dashboard cards; I can analyze any symbol from that list if you name it."

        elif intent == "STOCK_NEWS_QUERY":
            response = "I do not have a dedicated news feed connected yet, but I can still provide technical and portfolio-driven analysis for your stock."

        else:
            response = "I can help with stock prices, buy/sell analysis, forecasts, and portfolio profit/loss. Ask me about any ticker."

    except Exception:
        logger.exception("chatbot_logic failed")
        response = (
            "I could not complete the full analysis right now due to a temporary processing issue. "
            "I can still provide a conservative view if you share the stock symbol again."
        )

    memory.last_intent = intent
    if return_state:
        return response, memory.to_dict()
    return response


if __name__ == "__main__":
    Speak("AI assistant started. Ask your market question.")
    while True:
        q = input("You: ").strip()
        if q.lower() in {"exit", "stop", "quit"}:
            print("AI: Goodbye")
            break
        r = chatbot_logic(q)
        print("AI:", r)
        Speak(r)
