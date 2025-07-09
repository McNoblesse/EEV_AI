
import streamlit as st
import requests
import uuid

st.title("eeV-AI Chatbot")

# Get API key from user
api_key = st.text_input("Enter your Tier 1 API Key:", type="password")

# Generate a session ID if one doesn't exist
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Call the API
    if api_key:
        headers = {
            "tier_1_key_auth": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "user_query": prompt,
            "session_id": st.session_state.session_id
        }
        try:
            response = requests.post(
                "http://127.0.0.1:8000/eeVai/model/tier_1_model",
                headers=headers,
                json=payload
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            bot_response = response.json()["bot_response"]
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(bot_response)
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": bot_response})
        except requests.exceptions.RequestException as e:
            st.error(f"An error occurred: {e}")
    else:
        st.warning("Please enter your API key to chat.")
