import gradio as gr
import requests
import json

def chatbot_interaction(api_key, user_query, session_id="default_session"):
    if not api_key:
        return "Error: API Key is required.", session_id

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
        response.raise_for_status()  # Raise an exception for bad status codes
        
        response_data = response.json()
        return response_data.get("bot_response", "Error: Invalid response from bot."), response_data.get("session_id", session_id)
        
    except requests.exceptions.RequestException as e:
        return f"Error: Could not connect to the backend. {e}", session_id

def chat_interface(api_key, message, history):
    bot_response, _ = chatbot_interaction(api_key, message)
    return bot_response

API_KEY = "6fcbc285706bdf4fdae56f252653036b816651a6c63e057959d9b90a71a779757760436324534136ed1ad42915f2a099eb4f31dd030d661ce5a86b5487ffe480" # Replace with your actual API key

with gr.Blocks() as demo:
    gr.Markdown("# eeV-AI Chatbot")
    
    chat = gr.ChatInterface(
        fn=lambda message, history: chat_interface(API_KEY, message, history),
        chatbot=gr.Chatbot(height=500, type='messages'),
        textbox=gr.Textbox(placeholder="Ask me anything...", container=False, scale=7),
        title=None,
        description="Start chatting with the bot.",
        theme="soft",
        examples=[["Hello"], ["What do you know about Optimus AI?"]],
        cache_examples=False,
    )

if __name__ == "__main__":
    demo.launch(share=True)