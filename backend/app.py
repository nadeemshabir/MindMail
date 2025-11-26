import os
import json
import base64
import google.generativeai as genai
from flask import Flask, request, redirect, session, url_for, jsonify
from flask_cors import CORS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# NOTE: These modules are expected to be in your local directory.
# If they are missing, the server will fail to start.
try:
    import thread_processor
    import classifier
    from utils import safe_json_parse
except ImportError as e:
    print(f"⚠️ Warning: Could not import local modules: {e}")
    # Mocking for standalone analysis if files are missing
    safe_json_parse = lambda x: json.loads(x) if isinstance(x, str) else x

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a-very-bad-default-secret-key-for-dev')
# CORS(app)
CORS(app, supports_credentials=True, origins=['http://localhost:3000']) #change for frontend dev server

# --- Google API Configuration ---
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

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

# -----------------------------------------------------------------
# --- HELPER FUNCTIONS (Auth) ---
# -----------------------------------------------------------------

def credentials_to_dict(credentials):
    """Converts a Google Credentials object to a dictionary for session storage."""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def get_gmail_service():
    """Builds and returns a Gmail service object if user is authenticated."""
    credentials = None
    if 'credentials' in session:
        credentials_dict = session['credentials']
        credentials = Credentials.from_authorized_user_info(credentials_dict, SCOPES)
    
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                print('Refreshing expired token...')
                credentials.refresh(Request())
                session['credentials'] = credentials_to_dict(credentials) 
            except Exception as e:
                print(f'Error refreshing token: {e}')
                session.pop('credentials', None)
                return None
        else:
            return None
            
    try:
        service = build('gmail', 'v1', credentials=credentials)
        return service
    except HttpError as error:
        print(f'An error occurred building the service: {error}')
        return None

# -----------------------------------------------------------------
# --- HELPER FUNCTIONS (AI Functions) ---
# -----------------------------------------------------------------

def get_full_email_body(service, message_id):
    """
    Fetches the full email body for a given message_id.
    It handles multipart messages and base64url decoding.
    """
    try:
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
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
        
        if not email_body:
            return message.get('snippet', 'No content found.')

        clean_body = base64.urlsafe_b64decode(email_body.encode('ASCII')).decode('utf-8')
        return clean_body

    except Exception as e:
        print(f'An error occurred decoding body: {e}')
        return None

def get_gemini_analysis(email_text):
    """
    (Phase 3 "Action Engine" for a SINGLE email)
    """
    if not genai:
        return {"error": "Gemini AI is not configured. (Check .env file)"}
    
    print("Sending email text to Gemini for PHASE 3 (Action Engine) analysis...")
    
    # --- 1. Define the Schema ---
    mailmind_schema = {
        "type": "object",
        "properties": {
            "priority": {
                "type": "string",
                "description": "Must be one of: 'High', 'Medium', 'Low'"
            },
            "summary": {
                "type": "string",
                "description": "A concise, one-sentence summary"
            },
            "category": {
                "type": "string",
                "description": "Must be one of: 'Finance', 'Work', 'Personal', 'Purchases', 'Promotions', 'Travel', 'Other'"
            },
            "actionable_data": {
                "type": "object",
                "nullable": True,
                "description": "Contains extracted data if relevant, otherwise null",
                "properties": {
                    "is_bill": {"type": "boolean", "description": "Is this a bill or invoice?"},
                    "amount_due": {"type": "string", "description": "The amount due, e.g., '120.50'", "nullable": True},
                    "due_date": {"type": "string", "description": "The due date in YYYY-MM-DD format", "nullable": True},
                    "is_transaction": {"type": "boolean", "description": "Is this a transaction receipt?"},
                    "amount": {"type": "string", "description": "The transaction amount, e.g., '45.00'", "nullable": True},
                    "vendor": {"type": "string", "description": "The vendor name, e.g., 'Amazon'", "nullable": True},
                    "is_shipping": {"type": "boolean", "description": "Is this a shipping confirmation?"},
                    "tracking_number": {"type": "string", "description": "The tracking number", "nullable": True}
                }
            }
        }
    }

    # --- 2. Define the System Prompt ---
    system_prompt = """
    You are 'MailMind', a hyper-efficient email assistant.
    Read the following email and return a JSON object that strictly follows the provided schema.
    Your goal is to extract key data.
    - If an email is not a bill, set 'is_bill' to false and its fields to null.
    - If an email is not a transaction, set 'is_transaction' to false and its fields to null.
    - If an email is not a shipping notice, set 'is_shipping' to false and its fields to null.
    - 'summary' and 'priority' are mandatory.
    - Be precise.
    """
    
    try:
        # --- 3. Configure the Model ---
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": mailmind_schema,
        }
        
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash-preview-09-2025',
            system_instruction=system_prompt,
            generation_config=generation_config
        )
        
        # --- 4. Generate Content ---
        response = model.generate_content(email_text)
        analysis_json = safe_json_parse(response.text)
        return analysis_json

    except Exception as e:
        print(f"Error calling Gemini: {e}")
        try:
            return {"error": f"Failed to get AI analysis: {e}", "details": response.prompt_feedback}
        except:
            return {"error": f"Failed to get AI analysis: {e}"}


# -----------------------------------------------------------------
# --- FLASK ROUTES (Authentication) ---
# -----------------------------------------------------------------

@app.route('/')
def index():
    return "Python backend server is running! Go to /auth/google to log in."

@app.route('/auth/google')
def auth_google():
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/auth/google/callback')
def oauth2callback():
    state = session.get('state')
    if not state or state != request.args.get('state'):
        return 'Invalid state. Authentication failed.', 400

    try:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_PATH,
            scopes=SCOPES,
            redirect_uri=url_for('oauth2callback', _external=True)
        )
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        session['credentials'] = credentials_to_dict(credentials) 
        print('Authentication successful!')
        return 'Authentication successful! You can close this tab and go back to the app.'

    except Exception as e:
        print(f'Error during token fetch: {e}')
        return 'Authentication failed.', 500


# Add this NEW route after the oauth2callback function
@app.route('/api/check-auth')
def check_auth():
    """
    API route to check if user is authenticated.
    Returns {"authenticated": true/false}
    """
    if 'credentials' in session:
        credentials_dict = session['credentials']
        credentials = Credentials.from_authorized_user_info(credentials_dict, SCOPES)
        
        # Check if credentials are valid
        if credentials and credentials.valid:
            return jsonify({'authenticated': True}), 200
        elif credentials and credentials.expired and credentials.refresh_token:
            # Try to refresh
            try:
                credentials.refresh(Request())
                session['credentials'] = credentials_to_dict(credentials)
                return jsonify({'authenticated': True}), 200
            except:
                session.pop('credentials', None)
                return jsonify({'authenticated': False}), 200
    
    return jsonify({'authenticated': False}), 200

# -----------------------------------------------------------------
# --- FLASK ROUTES (API) --
# -----------------------------------------------------------------

@app.route('/api/fetch-emails')
def fetch_emails():
    """
    API route to get the list of recent emails.
    """
    service = get_gmail_service()
    if not service:
        return jsonify({'error': 'User not authenticated. Please authenticate first.'}), 401
    
    print("\n--- Running fetch_emails (w/ threadId) ---")
    
    try:
        list_response = service.users().messages().list(
            userId='me',
            maxResults=10,
            q='' #search all
        ).execute()
        
        messages = list_response.get('messages', [])
        
        if not messages:
            print('No messages found in list_response. Returning [].')
            return jsonify([])

        print(f"Found {len(messages)} message IDs. Now fetching details one-by-one...")
        
        formatted_emails = []
        
        for message in messages:
            msg_id = message['id']
            try:
                msg = service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='metadata',
                    metadataHeaders=['Subject', 'From']
                ).execute()
                
                headers = msg.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                from_sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                
                formatted_emails.append({
                    'id': msg_id,
                    'threadId': msg.get('threadId'), 
                    'snippet': msg.get('snippet', ''),
                    'subject': subject,
                    'from': from_sender,
                })

            except Exception as e:
                print(f"ERROR: Could not process message {msg_id}: {e}")
        
        print(f"\nSuccessfully formatted {len(formatted_emails)} emails. Returning JSON.")
        return jsonify(formatted_emails)

    except HttpError as error:
        print(f'An error occurred: {error}')
        session.pop('credentials', None)
        return jsonify({'error': 'Token expired or revoked. Please authenticate again.'}), 401
    except Exception as e:
        print(f'An error occurred: {e}')
        return jsonify({'error': 'Failed to fetch emails.'}), 500


@app.route('/api/process-email/<message_id>')
def process_email(message_id):
    """
    API route to get the full body of a specific email
    and run Gemini analysis on it.
    """
    service = get_gmail_service()
    if not service:
        return jsonify({'error': 'User not authenticated. Please authenticate first.'}), 401
    
    if not message_id:
        return jsonify({'error': 'No message_id provided.'}), 400
    
    print(f"\n--- Running process_email for ID: {message_id} ---")
    
    email_body_text = get_full_email_body(service, message_id)
    if not email_body_text:
        return jsonify({'error': 'Could not fetch or decode email body.'}), 500
    
    ai_analysis = get_gemini_analysis(email_body_text)
    
    response_data = {
        'id': message_id,
        'ai_analysis': ai_analysis,
        'full_body': email_body_text
    }
    
    print(f"Successfully processed AI analysis for {message_id}.")
    return jsonify(response_data)

# @app.route('/api/process-thread/<thread_id>')
# def process_thread_route(thread_id):
#     """
#     API route to process an ENTIRE thread using our new modules.
#     This now returns a summary generated by the thread processor (Agent 1).
#     """
#     service = get_gmail_service()
#     if not service:
#         print(f"Process-thread failed for {thread_id}: User not authenticated.")
#         return jsonify({'error': 'User not authenticated. Please authenticate first.'}), 401
    
#     if not thread_id:
#         return jsonify({'error': 'No thread_id provided.'}), 400
    
#     print(f"\n--- 1. Calling Thread Processor for ID: {thread_id} ---")
    
#     try:
#         # --- Call Thread Summarizer (Agent 1) ---
#         # NOTE: 
#         if 'thread_processor' not in globals():
#              return jsonify({'error': 'thread_processor module missing'}), 500

#         summary_data = thread_processor.summarize_thread(service, thread_id)
        
#         if "error" in summary_data:
#             return jsonify(summary_data), 500

#         # Extract pieces for downstream consumers
#         thread_summary = summary_data.get("ai_analysis", {})
#         full_conversation_text = summary_data.get("full_conversation_text", "")

#         # --- Integrate classifier on the summarized thread ---
#         classification_payload = thread_summary.get("thread_summary") or full_conversation_text
#         classification_result = {"error": "No content available to classify."}

#         if classification_payload and 'classifier' in globals():
#             try:
#                 classification_result = classifier._get_email_classification(classification_payload)
#             except Exception as classify_error:
#                 classification_result = {"error": f"Thread classification failed: {classify_error}"}

#         response_data = {
#             "thread_id": thread_id,
#             "thread_summary": thread_summary,
#             "full_conversation_text": full_conversation_text,
#             "classification": classification_result
#         }

#         print(f"Successfully processed thread {thread_id}.")
#         return jsonify(response_data)

#     except Exception as e:
#         print(f"An error occurred in thread processing route: {e}")
#         return jsonify({"error": f"An error occurred: {e}"}), 500


@app.route('/api/process-thread/<thread_id>')
def process_thread_route(thread_id):
    """
    API route to process an ENTIRE thread using our new modules.
    """
    service = get_gmail_service()
    if not service:
        # print(f"Process-thread failed for {thread_id}: User not authenticated.")
        return jsonify({'error': 'User not authenticated. Please authenticate first.'}), 401
    
    if not thread_id:
        return jsonify({'error': 'No thread_id provided.'}), 400
    
    print(f"\n--- 1. Calling Thread Processor for ID: {thread_id} ---")
    
    try:
        if 'thread_processor' not in globals():
             return jsonify({'error': 'thread_processor module missing'}), 500

        # --- STEP 1: Get Summary (Agent 1) ---
        summary_data = thread_processor.summarize_thread(service, thread_id)
        
        if "error" in summary_data:
            return jsonify(summary_data), 500

        # --- STEP 2: Extract Data (THE FIX IS HERE) ---
        # We access keys directly because thread_processor returns a flat dict
        thread_summary_text = summary_data.get("thread_summary", "")
        action_item = summary_data.get("latest_action_item", "")
        full_conversation_text = summary_data.get("full_conversation_text", "")

        # --- STEP 3: Classify (Agent 2) ---
        # Prefer classifying the summary (cheaper/faster), fallback to full text
        classification_payload = thread_summary_text if thread_summary_text else full_conversation_text
        
        classification_result = {"error": "No content available to classify."}

        if classification_payload and 'classifier' in globals():
            try:
                # Pass the TEXT string, not a dictionary
                classification_result = classifier._get_email_classification(classification_payload)
            except Exception as classify_error:
                classification_result = {"error": f"Thread classification failed: {classify_error}"}

        # --- STEP 4: Return Response ---
        response_data = {
            "thread_id": thread_id,
            "thread_summary": thread_summary_text, # Send the string directly
            "latest_action_item": action_item,     # Send action item
            "full_conversation_text": full_conversation_text,
            "classification": classification_result
        }

        print(f"Successfully processed thread {thread_id}.")
        return jsonify(response_data)

    except Exception as e:
        print(f"An error occurred in thread processing route: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500



# --- Start the Server ---
if __name__ == '__main__':
    # Allow non-HTTPS for local OAuth testing
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(port=5000, debug=True)