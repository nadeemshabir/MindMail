🚀 MailMind - AI Email Assistant

MailMind is an intelligent email dashboard that transforms your messy Gmail inbox into a structured, prioritized to-do list.

It uses a Multi-Agent AI System powered by Google Gemini to read your emails, summarize them, extract action items, and classify them by urgency and category.

✨ Key Features

🔐 Secure Gmail Login: Uses OAuth2 to securely authenticate with your Google account.

🤖 Multi-Agent Architecture:

Agent 1 (Summarizer): Reads full email threads, cleans "junk" characters (like invisible LinkedIn text), and generates a concise summary + action items.

Agent 2 (Classifier): Takes the summary and categorizes the email (e.g., "University Notice", "Urgent", "Personal") based on context.

🛡️ Robust Error Handling:

Smart Retries: Automatically handles 429 Resource Exhausted errors from the Gemini API with exponential backoff.

Safe Parsing: Handles Markdown code blocks and malformed JSON responses from the AI to prevent crashes.

🎨 Modern Dashboard: A clean, responsive UI built with HTML, Tailwind CSS, and Lucide Icons.

🛠️ Tech Stack

Backend: Python, Flask

AI Model: Google Gemini 2.5 Flash (gemini-2.5-flash-preview-09-2025)

APIs: Gmail API, Google Generative AI SDK

Frontend: HTML5, JavaScript (Fetch API), Tailwind CSS

📂 Project Structure

MailMind_Project/
│
├── backend/                 # Core Backend Logic
│   ├── gmail_api.py         # Flask Server (Orchestrator)
│   ├── thread_processor.py  # Agent 1: Summaries & Cleanup
│   ├── classifier.py        # Agent 2: Email Classifier
│   ├── utils.py             # Safe JSON parsing & Retry logic
│   ├── .env                 # API Keys (Not included)
│   └── credentials.json     # Google OAuth Credentials
│
└── frontend/
    └── index.html           # Dashboard UI



🚀 Setup & Installation

1. Prerequisites

Python 3.8 or higher

A Google Cloud Project with the Gmail API enabled.

A Google AI Studio API Key.

2. Clone & Install Dependencies

Navigate to the project folder and install the required Python packages:

pip install flask flask-cors google-generativeai python-dotenv google-auth-oauthlib google-api-python-client


3. Configuration

A. Gemini API Key

Get a key from Google AI Studio.

Create a file named .env inside the backend/ folder.

Add your key:

GEMINI_API_KEY=AIzaSyYourKeyHere...
FLASK_SECRET_KEY=some_random_secret_string


B. Google OAuth Credentials

Go to the Google Cloud Console.

Create a project and enable the Gmail API.

Go to Credentials -> Create Credentials -> OAuth Client ID.

Select Desktop App.

Download the JSON file, rename it to credentials.json, and place it inside the backend/ folder.

▶️ How to Run

Open your terminal in the project root.

Run the backend server:

python backend/gmail_api.py


Open your browser and go to:
http://localhost:5000

Click "Refresh Login" to authenticate with Google.

Click "Analyze" on any email thread to see the AI in action.

🐛 Troubleshooting

Error: 429 Resource exhausted:

You are hitting the free tier limits of Gemini. The app includes auto-retry logic, so just wait a few seconds, and it will process automatically.

Error: Invalid Client / redirect_uri_mismatch:

Ensure your credentials.json is valid and placed correctly in the backend/ folder.

Frontend shows "Auth Required":

Your session likely expired. Click the "Refresh Login" button in the top right corner.

🔮 Future Improvements

Draft Replies: Have the AI generate a draft response based on the summary.

Bulk Analysis: Analyze the entire inbox with one click (requires background workers).

Fine-Tuning: Train a custom LoRA adapter on your specific email writing style.
