import google.generativeai as genai
import base64
import os
import json
# Ensure backend/utils.py exists and contains safe_json_parse
from utils import safe_json_parse 

# --- 1. Helper to clean email text ---
def clean_email_body(text):
    """
    Removes extra whitespace, invisible characters, and common junk.
    """
    if not text: 
        return ""
    # Remove invisible separator chars (\u034f) often found in automated emails
    text = text.replace('\u034f', '') 
    # Remove extra spaces/newlines to make it compact for the AI context window
    return " ".join(text.split())

# --- 2. Helper to extract text from complex Gmail payloads ---
def extract_body_from_payload(payload):
    """
    Recursively finds the plain text body in a Gmail message payload.
    Prioritizes text/plain, then falls back to extracting from parts.
    """
    body = ""
    
    # 1. Check if the body is directly in the payload (rare for multipart, common for simple)
    if 'body' in payload and 'data' in payload['body']:
        body = payload['body']['data']
    
    # 2. Check for 'parts' (Multipart emails)
    if not body and 'parts' in payload:
        for part in payload['parts']:
            mime_type = part.get('mimeType')
            
            # Case A: Plain Text found directly
            if mime_type == 'text/plain':
                if 'data' in part['body']:
                    body = part['body']['data']
                    break
            
            # Case B: Nested Multipart (common in modern emails)
            elif mime_type == 'multipart/alternative':
                for subpart in part.get('parts', []):
                    if subpart.get('mimeType') == 'text/plain':
                        if 'data' in subpart.get('body', {}):
                            body = subpart['body']['data']
                            break
    
    # 3. Decode logic
    if body:
        try:
            # valid string needs to be urlsafe base64 decoded
            return base64.urlsafe_b64decode(body).decode('utf-8')
        except Exception as e:
            print(f"Error decoding email body: {e}")
            return "" 
            
    return ""

# --- 3. Main Function called by app.py ---
def summarize_thread(service, thread_id):
    """
    Fetches a thread, combines all messages, cleans them, and gets an AI summary.
    Returns a dict containing the summary, action items, and the full raw text.
    """
    try:
        # A. Fetch the Thread details from Gmail
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages = thread.get('messages', [])
        
        full_conversation = []
        
        # B. Combine all messages into one long text block
        for msg in messages:
            payload = msg.get('payload', {})
            headers = payload.get('headers', [])
            
            # Extract Sender for context
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
            
            # Extract Body
            raw_body = extract_body_from_payload(payload) or msg.get('snippet', '')
            clean_body = clean_email_body(raw_body)
            
            if clean_body:
                full_conversation.append(f"--- From: {sender} ---\n{clean_body}\n")
            
        full_text = "\n".join(full_conversation)
        
        # If text is empty (e.g. image-only emails), handle gracefully
        if not full_text.strip():
            return {"error": "Could not extract text from email body."}

        # C. Send to Gemini for Summarization
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
             return {"error": "API Key missing in thread_processor"}
        
        genai.configure(api_key=api_key)

        # Strict Schema for the Summary Agent
        summary_schema = {
            "type": "object",
            "properties": {
                "thread_summary": {"type": "string"},
                "latest_action_item": {"type": "string", "nullable": True}
            },
            "required": ["thread_summary"]
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-09-2025", # Ensure your API key has access to 2.0 Flash
            system_instruction="You are an email assistant. Summarize this thread in 1-2 sentences. Extract one key action item if present.",
            generation_config={
                "response_mime_type": "application/json", 
                "response_schema": summary_schema,
                "temperature": 0.3 # Keep it factual
            }
        )
        
        # Generate content
        response = model.generate_content(full_text)
        
        # D. Use Safe Parse (Handles Markdown/Errors from utils.py)
        ai_result = safe_json_parse(response.text)
        
        # Check if parsing failed or returned garbage
        if "error" in ai_result and "thread_summary" not in ai_result:
            # Fallback: If JSON fails, just return the raw text as summary (rare case)
            return {
                "full_conversation_text": full_text,
                "thread_summary": "AI processing error. Raw text available.",
                "latest_action_item": None
            }

        # E. Return the Clean Bundle
        # We include full_conversation_text so the 'Classifier' module can use it next
        return {
            "full_conversation_text": full_text, 
            "thread_summary": ai_result.get("thread_summary"),
            "latest_action_item": ai_result.get("latest_action_item")
        }

    except Exception as e:
        print(f"Error in thread_processor: {e}")
        return {"error": str(e)}