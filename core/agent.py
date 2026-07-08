import os
import json
import logging
from typing import List, Dict, Any, Callable
from google import genai
from google.genai import types

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from core.prompts import build_system_prompt
from tools.email_tool import send_template_email
from tools.callback_tool import schedule_manager_callback
from tools.lead_tool import update_lead_status
from tools.product_tool import get_product_details

logger = logging.getLogger(__name__)

# Define wrapper functions matching expected tool signatures for Gemini Auto-Function Calling
def send_email(to_email: str, template_name: str = "syllabus") -> str:
    """
    Sends a template-based email to the user (e.g. syllabus, pricing, course brochures).
    
    Args:
        to_email: The recipient email address.
        template_name: The name of the template ('syllabus' or 'pricing'). Defaults to 'syllabus'.
    """
    # Phone number is fetched from the current agent context or set to dummy for now
    # We will let the agent manage the current phone number context
    phone = getattr(GeminiAgent, "_current_phone", "unknown")
    return send_template_email(phone=phone, to_email=to_email, template_name=template_name)

def schedule_callback(time_str: str, reason: str) -> str:
    """
    Schedules a callback for the human manager to call the lead back later.
    Use this if the lead asks for a call tomorrow, or next morning, or has query about pricing/payment.
    
    Args:
        time_str: The requested callback time ('morning', 'afternoon', 'tomorrow', or specific hour like '11:00 AM').
        reason: The reason for scheduling the callback (e.g. 'payment discussion', 'detailed syllabus review').
    """
    phone = getattr(GeminiAgent, "_current_phone", "unknown")
    return schedule_manager_callback(phone=phone, time_str=time_str, reason=reason)

def log_lead_interest(interest_level: str, notes: str, name: str = "") -> str:
    """
    Updates the lead's status (hot, warm, cold) and records conversation notes or objections in the database.
    Call this whenever you understand the user's name, interest level, or specific requirements.
    
    Args:
        interest_level: The user's interest level ('hot', 'warm', 'cold').
        notes: Concise summary of what they want, study, work, or their objection.
        name: The user's name if they shared it. Optional.
    """
    phone = getattr(GeminiAgent, "_current_phone", "unknown")
    return update_lead_status(phone=phone, interest_level=interest_level, notes=notes, name=name)

def query_product_info(query: str) -> str:
    """
    Queries the course catalog, pricing details, GPU requirements, or FAQ for relevant answers.
    Use this to get accurate details before answering fees or hardware questions.
    
    Args:
        query: What the customer is asking (e.g., 'fees', 'graphics card requirements', 'beginner difficulty').
    """
    return get_product_details(query=query)


class GeminiAgent:
    _current_phone = "unknown"  # Thread-local/class-level storage for current active session phone
    
    def __init__(self, phone: str):
        self.phone = phone
        self.history: List[types.Content] = []
        self.system_prompt = build_system_prompt()
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        
        # Keep track of active phone number in class-level context for tool access
        GeminiAgent._current_phone = phone
        
        # Initialize conversation session
        self.chat = self.client.chats.create(
            model="gemini-2.5-flash", # Latest flash model for low latency
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                tools=[send_email, schedule_callback, log_lead_interest, query_product_info],
                temperature=0.7,
                max_output_tokens=150,
            )
        )
        logger.info(f"Gemini Conversational Agent initialized for phone: {phone}")

    async def generate_response(self, user_text: str) -> str:
        """Sends user message to Gemini and handles automatic function execution."""
        logger.info(f"Sending to Gemini: '{user_text}'")
        
        # Store current phone context
        GeminiAgent._current_phone = self.phone
        
        try:
            # We run in a threadpool to avoid blocking if the API call is synchronous
            response = await asyncio.to_thread(
                self.chat.send_message,
                user_text
            )
            
            logger.info(f"Gemini response: '{response.text}'")
            return response.text
        except Exception as e:
            logger.error(f"Error querying Gemini: {e}")
            return "Arey, thoda network issue lag raha hai. Kya aap sun pa rahe hain?"

    def get_history(self) -> List[Dict[str, str]]:
        """Returns the conversation history formatted for logging."""
        formatted_history = []
        # Get history from the chat object
        chat_history = self.chat.get_history()
        for content in chat_history:
            role = "assistant" if content.role == "model" else "user"
            text_parts = []
            for part in content.parts:
                if part.text:
                    text_parts.append(part.text)
                elif part.function_call:
                    text_parts.append(f"[Called Tool: {part.function_call.name}]")
                elif part.function_response:
                    text_parts.append(f"[Tool Response: {part.function_response.response}]")
            
            if text_parts:
                formatted_history.append({
                    "role": role,
                    "content": " ".join(text_parts)
                })
        return formatted_history
