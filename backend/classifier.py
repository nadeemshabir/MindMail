import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
load_dotenv()

# --- Gemini AI Configuration ---
try:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("❌ Missing GEMINI_API_KEY in .env file")

    genai.configure(api_key=GEMINI_API_KEY)

    print("=" * 50)
    print("✅ SUCCESS: Gemini AI has been configured using environment variables.")
    print("=" * 50)

except Exception as e:
    print(f"⚠️ Error configuring Gemini: {e}")
    genai = None

# --- Configuration ---
# (Make sure genai is configured in your main app.py or here)
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Define your custom categories
# These are the "labels" our model will learn.
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
            "response_schema": classification_schema
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-09-2025",
            system_instruction=system_prompt,
            generation_config=generation_config
        )
        
        response = model.generate_content(email_text)
        # Try parsing JSON safely
        try:
            if hasattr(response, "text") and response.text:
                return json.loads(response.text)
            elif hasattr(response, "candidates") and response.candidates:
                # fallback: extract JSON from first candidate text
                text = response.candidates[0].content.parts[0].text
                return json.loads(text)
            else:
                return {"error": "No valid JSON returned from Gemini."}
        except Exception as parse_error:
            print(f"⚠️ Gemini classification parse error: {parse_error}")
            print(f"Raw response: {getattr(response, 'text', str(response))}")
            return {"error": f"Failed to parse Gemini response: {parse_error}"}

    except Exception as e:
        print(f"Error calling Gemini for classification: {e}")
        return {"error": f"Failed to get AI classification: {e}"}

# --- Example of how to call it (you would do this in app.py) ---
if __name__ == "__main__":
    # A test email
    test_email = """
    Subject: Action Required: Your library books are overdue
    
    Dear Nadeem,
    
    This is a final reminder that your books are now 7 days overdue. 
    Please return them by tomorrow, Nov 3rd, to avoid a fine.
    
    Thank you,
    University Library
    """
    
    classification = _get_email_classification(test_email)
    print("--- Classification Result ---")
    print(json.dumps(classification, indent=2))
    
    test_email_2 = "Hey bro, you free for dinner tonight? Let me know."
    classification_2 = _get_email_classification(test_email_2)
    print("\n--- Classification Result 2 ---")
    print(json.dumps(classification_2, indent=2))