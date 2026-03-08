def generate_decision(aps_result):
    current = aps_result["current_price"]
    predicted = aps_result["predicted_price"]
    confidence = min(aps_result["accuracy"] / 100, 1.0)
    symbol = aps_result["symbol"]

    if predicted > current and confidence > 0.8:
        decision = "BUY"
        risk = "LOW"
    elif predicted < current and confidence > 0.8:
        decision = "SELL"
        risk = "LOW"
    else:
        decision = "HOLD"
        risk = "MEDIUM"

    return {
        "decision": decision,
        "reason": f"Predicted: {predicted}, Current: {current}",
        "risk_level": risk
    }

