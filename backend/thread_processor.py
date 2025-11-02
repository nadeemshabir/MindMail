"""
This is a new helper file (a "module") for all thread-related logic.
It is imported and used by app.py.
"""
import base64
import json
import google.generativeai as genai
from googleapiclient.errors import HttpError

def _get_full_thread_text(service, thread_id):
    """
    Fetches all messages in a thread and combines them into one text block.
    """
    print(f"--- Thread Logic: Fetching all messages for thread {thread_id} ---")
    try:
        thread = service.users().threads().get(
            userId='me', 
            id=thread_id,
            format='full' # We need the full payload
        ).execute()
        
        messages = thread.get('messages', [])
        
        # We will combine all plain-text parts into one giant string
        full_conversation_text = ""
        
        for i, message in enumerate(messages):
            # We add a separator to help the AI know where messages begin
            full_conversation_text += f"\n\n--- MESSAGE {i+1} ---\n\n"
            
            payload = message.get('payload', {})
            parts = payload.get('parts', [])
            email_body = ""

            if 'data' in payload.get('body', {}):
                email_body = payload['body']['data']
            elif parts:
                for part in parts:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part.get('body', {}):
                            email_body = part['body']['data']
                            break
                    elif part['mimeType'] == 'multipart/alternative':
                        for sub_part in part.get('parts', []):
                            if sub_part['mimeType'] == 'text/plain':
                                if 'data' in sub_part.get('body', {}):
                                    email_body = sub_part['body']['data']
                                    break
                        if email_body:
                            break
            
            if email_body:
                # Decode the email body and add it to our string
                clean_body = base64.urlsafe_b64decode(email_body.encode('ASCII')).decode('utf-8')
                full_conversation_text += clean_body
            else:
                # Fallback to snippet if we can't find a text/plain part
                full_conversation_text += message.get('snippet', '(No content found for this message)')
        
        print(f"--- Thread Logic: Combined {len(messages)} messages into one text block ---")
        return full_conversation_text

    except Exception as e:
        print(f"An error occurred fetching thread: {e}")
        return None
def _get_gemini_thread_analysis(thread_text):
    """
    Sends the entire conversation to Gemini with a new "thread summarizer" prompt.
    (Updated for google-generativeai v0.8.x+)
    """
    if not genai:
        return {"error": "Gemini AI is not configured."}
        
    print("--- Thread Logic: Sending full conversation to Gemini for summary ---")
    
    # 1. Define schema as a simple dict
    thread_schema = {
        "type": "object",
        "properties": {
            "thread_summary": {
                "type": "string",
                "description": "A concise, one-paragraph summary of the entire conversation, focusing on the latest message or outcome."
            },
            "latest_action_item": {
                "type": "string",
                "nullable": True,
                "description": "The single most important action item from the last message, or null if none."
            }
        },
        "required": ["thread_summary"]
    }
    
    # 2. System prompt
    system_prompt = """
    You are 'MailMind', a hyper-efficient email assistant.
    You will read an entire email conversation separated by '--- MESSAGE X ---'.
    
    Your job:
    - Summarize the conversation briefly in 'thread_summary', focusing on the latest information.
    - Identify the single most important actionable point from the final message, if any.
    - Return strict JSON according to the schema.
    """
    
    # 3. Configure and call Gemini
    try:
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": thread_schema
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-09-2025",
            system_instruction=system_prompt,
            generation_config=generation_config
        )
        
        response = model.generate_content(thread_text)
        return json.loads(response.text)

    except Exception as e:
        print(f"Error calling Gemini for thread: {e}")
        return {"error": f"Failed to get AI analysis: {e}"}

# --- This is the MAIN function that app.py will call ---
def summarize_thread(service, thread_id):
    """
    Public-facing function to process a thread.
    """
    
    # Step 1: Get the combined text of all messages in the thread
    full_text = _get_full_thread_text(service, thread_id)
    
    if not full_text:
        return {"error": f"Could not retrieve or process thread {thread_id}"}
    
    # Step 2: Send that combined text to Gemini for analysis
    ai_analysis = _get_gemini_thread_analysis(full_text)
    
    return {
        'thread_id': thread_id,
        'ai_analysis': ai_analysis,
        'full_conversation_text': full_text # We include this for debugging
    }
