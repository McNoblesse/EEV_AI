import gradio as gr
import requests
import json
import uuid
import os
import sys

# Add the project root to the Python path to allow for module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.database import engine, Base

def chatbot_interaction(api_key, user_query, session_id):
    """Sends the user's query and session_id to the backend and returns the bot's response."""
    if not api_key:
        return "Error: API Key is required."

    headers = {
        "tier_1_key_auth": api_key,
        "Content-Type": "application/json"
    }
    
    data = {
        "user_query": user_query,
        "session_id": session_id
    }
    
    try:
        response = requests.post("http://127.0.0.1:8000/eeVai/model/tier_1_model", headers=headers, data=json.dumps(data))
        response.raise_for_status()
        
        response_data = response.json()
        # The backend will return the bot's response in this key
        return response_data.get("bot_response", "Error: Invalid response format from bot.")
        
    except requests.exceptions.RequestException as e:
        return f"Error: Could not connect to the backend. Details: {e}"

def chat_interface_fn(message, history, api_key, session_id):
    """
    The function that Gradio's ChatInterface will call.
    It orchestrates the interaction with the backend.
    """
    # The history is managed by ChatInterface automatically.
    # We pass the new message and the session_id to our interaction function.
    bot_response = chatbot_interaction(api_key, message, session_id)
    return bot_response

# This key is now passed via gr.State, but you can keep it here for reference or other uses.
API_KEY = "6fcbc285706bdf4fdae56f252653036b816651a6c63e057959d9b90a71a779757760436324534136ed1ad42915f2a099eb4f31dd030d661ce5a86b5487ffe480"

with gr.Blocks() as demo:
    gr.Markdown("# eeV-AI Chatbot")
    
    # Add a state component to hold the session ID.
    # It initializes with a new UUID for each user session.
    session_id_state = gr.State(lambda: str(uuid.uuid4()))
    
    # Use gr.ChatInterface and pass the state to its function.
    chat = gr.ChatInterface(
        fn=chat_interface_fn,
        # Pass the API key and session_id state as non-visible inputs.
        additional_inputs=[gr.State(API_KEY), session_id_state],
        chatbot=gr.Chatbot(height=500, type='messages'),
        textbox=gr.Textbox(placeholder="Ask me anything...", container=False, scale=7),
        title=None,
        description="Start chatting with the bot.",
        theme="soft",
        examples=[["Hello"], ["What do you know about Optimus AI?"]],
        cache_examples=False,
    )

if __name__ == "__main__":
    # Launch the app without creating a public share link.
    demo.launch(share=False)