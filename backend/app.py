import streamlit as st
import google.generativeai as genai
import os
import json
from gmail_api import get_gmail_service, get_message_threads, get_full_thread_details
from thread_processor import _get_gemini_thread_analysis
from classifier import _get_email_classification, CLASSIFICATION_CATEGORIES # <-- 1. IMPORT THE NEW FUNCTION

st.set_page_config(layout="wide")

# --- Configuration and Setup ---
try:
    # Configure Gemini API
    # Load from Streamlit secrets if available
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
        except (FileNotFoundError, KeyError):
            st.error("GEMINI_API_KEY not found. Please set it in Streamlit secrets or as an environment variable.")
            st.stop()
            
    genai.configure(api_key=api_key)
    
    # Get Gmail Service
    # This will trigger the OAuth flow on first run
    gmail_service = get_gmail_service()
    
    st.title("🚀 MailMind - Your AI Email Assistant")
    st.write("Fetching your 10 most recent email threads...")

    # --- Fetch and Display Threads ---
    threads = get_message_threads(gmail_service, max_results=10)

    if not threads:
        st.warning("No email threads found.")
    else:
        for thread in threads:
            thread_id = thread['id']
            snippet = thread['snippet']
            
            # Display basic thread info
            st.subheader(f"Thread: {snippet[:100]}...")
            
            # Button to trigger analysis
            analyze_button = st.button(f"Analyze Thread", key=thread_id)
            
            if analyze_button:
                with st.spinner("MailMind is reading and thinking..."):
                    
                    # 1. Get Full Conversation Text
                    conversation_data = get_full_thread_details(gmail_service, thread_id)
                    full_conversation_text = conversation_data.get("full_conversation_text", "")

                    if not full_conversation_text:
                        st.error("Could not fetch full conversation.")
                        continue

                    # --- 2. NEW: CALL THE CLASSIFIER ---
                    # We classify based on the snippet for a fast, "first-glance" category
                    st.write("Running Classification...")
                    classification_data = _get_email_classification(snippet)
                    
                    # --- 3. CALL THE SUMMARIZER ---
                    st.write("Running Summary...")
                    summary_data = _get_gemini_thread_analysis(full_conversation_text)
                    st.write("Done!")

                    # --- 4. NEW: DISPLAY CLASSIFICATION FIRST ---
                    st.divider()
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        category = classification_data.get("category", "Other")
                        # Add emoji logic for visual flair
                        emoji = "📄" # Default
                        if category == "University Notice": emoji = "🎓"
                        elif category == "Urgent / Action Required": emoji = "🔥"
                        elif category == "Personal / Social": emoji = "💬"
                        elif category == "Spam / Promotion": emoji = "🗑️"
                        
                        st.metric("Category", f"{emoji} {category}")
                    
                    with col2:
                        is_urgent = classification_data.get("is_urgent", False)
                        urgent_text = "YES 🔥" if is_urgent else "No"
                        st.metric("Is Urgent?", urgent_text)
                    
                    st.divider()

                    # --- 5. DISPLAY SUMMARY & ACTION (Existing Logic) ---
                    with st.expander("Show AI Summary & Action Item", expanded=True):
                        if "error" in summary_data:
                            st.error(summary_data["error"])
                        else:
                            st.subheader("Thread Summary")
                            st.write(summary_data.get("thread_summary", "No summary available."))
                            
                            st.subheader("Latest Action Item")
                            action_item = summary_data.get("latest_action_item")
                            if action_item:
                                st.success(action_item)
                            else:
                                st.info("No specific action item found in the last message.")
                    
                    # (Optional) Show full text for debugging
                    with st.expander("Show Full Conversation Text"):
                        st.code(full_conversation_text, language="text")

except Exception as e:
    st.error(f"An error occurred: {e}")
    st.error("Please make sure your GEMINI_API_KEY and Gmail credentials (token.json/credentials.json) are set up correctly.")



