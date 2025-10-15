# eeV-AI

eeV-AI is a conversational AI application built with FastAPI and LangChain. It provides a chatbot interface that can answer user queries by leveraging a powerful language model and retrieving information from a vector database. The project includes a FastAPI backend for the AI logic and a Gradio frontend for user interaction and testing.

## Features

-   **Conversational AI:** Powered by OpenAI's GPT models and LangChain for robust conversational flow.
-   **RAG Pipeline:** Implements a Retrieval-Augmented Generation (RAG) pipeline using Pinecone's vector store to provide contextually relevant answers from a knowledge base.
-   **Persistent Memory:** Maintains conversation history for each user session using a SQLite database.
-   **Secure API:** The API endpoint is protected by API key authentication.
-   **Gradio Frontend:** A simple and intuitive web interface for testing and interacting with the chatbot.

## Project Structure

```
.
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── config
│   └── access_keys.py
├── frontend
│   └── gradio_app.py
├── main.py
├── model
│   └── schema.py
├── requirements.txt
├── route
│   └── tier_1_model.py
├── security
│   └── authentication.py
└── utils
    └── tier_1_utils.py
```

-   **`config/`**: Contains configuration for accessing API keys and secrets.
-   **`frontend/`**: Holds the Gradio user interface code.
-   **`main.py`**: The main entry point for the FastAPI application.
-   **`model/`**: Defines the Pydantic data schemas for API requests and responses.
-   **`route/`**: Defines the API routes and their logic.
-   **`security/`**: Handles API authentication.
-   **`utils/`**: Contains the core AI logic, including the LangGraph workflow, tool definitions, and Pinecone integration.

## Getting Started

### Prerequisites

-   Python 3.9+
-   pip

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd eeV-AI
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv .venv
    .venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Set up environment variables:**
    -   Rename the `.env.example` file to `.env`.
    -   Open the `.env` file and add your actual API keys and secrets:
        ```
        PINECONE_API_KEY="your_pinecone_api_key"
        OPENAI_API_KEY="your_openai_api_key"
        tier_1_auth_key="your_tier_1_auth_key" # Can be any secret string for local testing
        GEMINI_API_KEY="your_gemini_api_key"
        ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

You need to run the backend and frontend in separate terminals.

### 1. Run the FastAPI Backend

In your first terminal, run the following command to start the API server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://127.0.0.1:8000`.

### 2. Run the Gradio Frontend

In your second terminal, run the following command to start the user interface:

```bash
python frontend/gradio_app.py
```

This will open the application in your web browser. The API key is now hardcoded in `frontend/gradio_app.py` for convenience. **Remember to replace the placeholder `"your_tier_1_auth_key"` with your actual key from `.env` for the app to work.** The Gradio app will also provide a public URL that you can share with colleagues (valid for 72 hours).

## API Endpoint

### POST /eeVai/model/tier_1_model

This endpoint processes a user's query and returns the chatbot's response.

-   **Headers:**
    -   `tier_1_key_auth`: (string, required) Your secret API key.

-   **Request Body:**
    ```json
    {
      "user_query": "string",
      "session_id": "string"
    }
    ```

-   **Success Response (200 OK):**
    ```json
    {
      "bot_response": "string",
      "session_id": "string"
    }
    ```

## Technology Stack

-   **Backend:** FastAPI, Uvicorn
-   **AI/ML:** LangChain, LangGraph, OpenAI, Google Generative AI
-   **Database:** Pinecone (Vector Store), SQLite (Chat Memory)
-   **Frontend:** Gradio
-   **Data Validation:** Pydantic