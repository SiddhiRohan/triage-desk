def rule_based_classify(text: str):
    """
    Pure function to classify messages based on keywords.
    Returns: (category, priority, confidence, reason)
    Confidence is always <= 0.5 so it goes to 'Needs human'.
    """
    text = text.lower()
    
    # Billing keywords
    if any(k in text for k in ["payment", "charge", "invoice", "refund", "billing", "subscription"]):
        return "billing", "normal", 0.4, "Keyword match: billing"
    
    # Bug keywords
    if any(k in text for k in ["crash", "bug", "error", "timeout", "broken", "not working", "slow"]):
        return "bug", "high", 0.4, "Keyword match: bug"
    
    # Sales keywords
    if any(k in text for k in ["enterprise", "pricing", "demo", "quote", "buy", "sales"]):
        return "sales", "normal", 0.4, "Keyword match: sales"
    
    # Support keywords
    if any(k in text for k in ["how to", "help", "question", "account", "setup", "integration"]):
        return "support", "normal", 0.4, "Keyword match: support"
    
    # Default / Vague
    return "other", "low", 0.2, "No strong keyword match"
