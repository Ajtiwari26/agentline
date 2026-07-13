import os
import sys
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.prompts import load_kb

logger = logging.getLogger(__name__)

def get_product_details(query: str) -> str:
    """
    Queries the product knowledge base for details.
    Examples of queries: 'fees', 'duration', 'curriculum', 'GPU requirements', 'pricing'.
    """
    logger.info(f"Triggering product tool with query: {query}")
    kb = load_kb()
    
    query_lower = query.lower()
    
    # 1. Check Fees & Price
    if any(k in query_lower for k in ("fees", "price", "cost", "emi", "charge", "payment", "pricing")):
        objection_cost = kb.get("objections", {}).get("cost_price", {}).get("response", "")
        return f"Pricing/fees details: INR 14,999 combined. Details: {objection_cost}"
        
    # 2. Check GPU/Hardware requirements
    if any(k in query_lower for k in ("gpu", "graphics card", "hardware", "laptop", "pc", "computer")):
        objection_gpu = kb.get("objections", {}).get("no_gpu_or_hardware", {}).get("response", "")
        return f"Hardware requirements: {objection_gpu}"
        
    # 3. Check level/difficulty
    if any(k in query_lower for k in ("beginner", "easy", "hard", "coding", "prior knowledge")):
        objection_diff = kb.get("objections", {}).get("difficult_for_beginners", {}).get("response", "")
        return f"Difficulty level: {objection_diff}"
        
    # Default info return: Nukkad Tech Solutions services instead of Course Summary
    services = [
        "- WhatsApp AI Automation: Automated customer support and lead nurturing bots.",
        "- Voice AI Agents: Real-time human-like voice agents for inbound and outbound calling.",
        "- Web & App Development: Custom full-stack web and mobile application development.",
        "- Social Media Automation: Automatic post scheduling and lead generation tools."
    ]
    return "Services and Products offered by Nukkad Tech Solutions:\n" + "\n".join(services)

