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
    Examples of queries: 'fees', 'duration', 'curriculum', 'GPU requirements', 'pricing', 'scent', 'perfume'.
    """
    logger.info(f"Triggering product tool with query: {query}")
    kb = load_kb()
    
    import config
    company = getattr(config, "COMPANY", "nukkad").lower()
    
    query_lower = query.lower()
    
    if company == "bla_bli_blu":
        # Check Pricing & Trial Packs
        if any(k in query_lower for k in ("fees", "price", "cost", "charge", "payment", "pricing", "trial", "cashback")):
            objection_cost = kb.get("objections", {}).get("cost_price", {}).get("response", "")
            return (
                "Bla Bli Blu Pricing/Offers:\n"
                "- 100% Refundable Scent Trial (Discovery Set): Pay for a trial set, get 100% cashback on delivery to use towards a 100ml full bottle (trial becomes free).\n"
                "- Trial Pack of 3 @ 999: Value pack of 3 trials (cashback excluded).\n"
                "- Perfume Gift Sets (Men/Women) @ 825: 3 x 30ml best-sellers.\n"
                "- Main Character Combo @ 999: Love Drunk (75ml+8ml) + By the Beach (75ml+8ml).\n"
                "- Build Your Own Box @ 1700: Customize any three 30ml bottles.\n"
                f"Objection handling / policy details: {objection_cost}"
            )
            
        # Check Perfumes / Scents / Recommendations
        if any(k in query_lower for k in ("scent", "perfume", "fragrance", "recommend", "option", "smell", "note")):
            return (
                "Bla Bli Blu Perfumes and Notes:\n"
                "- Old Money: Office/Professional (Crisp green apple, damask rose, cedar, tonka).\n"
                "- Love Drunk: Romantic/Night out (Warm cinnamon, sweet dates, praline, vanilla).\n"
                "- By the Beach: Gym/Hot summer (Fresh lemon, bergamot, crisp apple, musk).\n"
                "- Lights Off: Seductive/Late night (Passionfruit, sweet caramel, rich amber)."
            )
            
        # Check longevity/objection responses
        if any(k in query_lower for k in ("last", "longevity", "durability", "synthetic", "chemical")):
            objection_longevity = kb.get("objections", {}).get("longevity", {}).get("response", "")
            objection_synthetic = kb.get("objections", {}).get("synthetic_smell", {}).get("response", "")
            return (
                f"Longevity response: {objection_longevity}\n"
                f"Synthetic smell response: {objection_synthetic}"
            )
            
        return (
            "Bla Bli Blu is a premium local fragrance brand. We offer 100% refundable scent trials, "
            "value combos (like Pack of 3 @ 999 or Gift Sets @ 825), and custom recommendation profiles "
            "(Old Money, Love Drunk, By the Beach, Lights Off)."
        )
        
    # 1. Check Fees & Price (Default Nukkad / CourseWallah)
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

