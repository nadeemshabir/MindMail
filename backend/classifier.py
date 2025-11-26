import google.generativeai as genai
import json
import os
from utils import safe_json_parse


CLASSIFICATION_CATEGORIES = [
    "University Notice",     # Official announcements, schedules, exam info
    "Urgent / Action Required", # Bills, deadlines, must-reply
    "Personal / Social",     # Friends, family, social plans
    "Spam / Promotion",      # Newsletters, marketing, unwanted
    "Other"                  # Anything that doesn't fit
]

def _get_email_classification(email_text):
    """
    Sends a single email's text to Gemini for classification.
    (Prototype using gemini-2.5-flash)
    """
    
    # 1. Define the schema
    # We force the model to *only* choose from our list.
    classification_schema = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": CLASSIFICATION_CATEGORIES,
                "description": "The single best category for the email."
            },
            "is_urgent": {
                "type": "boolean",
                "description": "True if the email requires an urgent reply or action, False otherwise."
            }
        },
        "required": ["category", "is_urgent"]
    }
    
    # 2. System prompt
    system_prompt = f"""
    You are 'MailMind', a hyper-efficient email classification agent.
    You will read an email and classify it into ONE of the following categories:
    {', '.join(CLASSIFICATION_CATEGORIES)}

    - Prioritize 'Urgent / Action Required' if the email contains a specific deadline,
      a bill, or a direct question needing a reply.
    - Classify based on the content.
    - Return strict JSON according to the schema.
    """
    
    # 3. Configure and call Gemini
    try:
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": classification_schema,
            
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-09-2025",
            system_instruction=system_prompt,
            generation_config=generation_config
        )
        
        response = model.generate_content(email_text[:4000])  # Limit input size for performance
        # Try parsing JSON safely
        return safe_json_parse(response.text)
    
    except Exception as e:
        print(f"Error calling Gemini for classification: {e}")
        return {"error": f"Failed to get AI classification: {e}"}

