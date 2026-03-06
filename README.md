🚀 EEV AI
Voice-Enabled Generative AI Assistant for Intelligent Document Search & Customer Support
<p align="center">












</p>

EEV AI is a voice-enabled Generative AI platform that transforms enterprise documents into an intelligent conversational assistant.

It combines LLMs, Retrieval Augmented Generation (RAG), vector search, and real-time voice agents to deliver fast, grounded answers from organizational knowledge bases.

The system supports both chat and voice interactions, making it suitable for banks, enterprise knowledge systems, document automation, and AI call centers.

🎬 Demo
Voice AI Call Flow
Caller
   ↓
Speech Recognition (Deepgram)
   ↓
LiveKit Voice Agent
   ↓
GenAI RAG Pipeline
   ↓
Knowledge Retrieval (Pinecone)
   ↓
LLM Reasoning
   ↓
Voice Response (TTS)

Example query:

“How do I reset my online banking password?”

Response:

“To reset your password, open the banking app, select forgot password, and follow the verification steps using your registered phone number.”

✨ Key Features
🤖 Generative AI Assistant

Powered by OpenAI LLMs

Context-aware conversational responses

Multi-agent architecture

Prompt-optimized responses for voice interactions

📄 Intelligent Document Processing

Extracts knowledge from:

PDFs

JSON documents

Text files

Enterprise datasets

All documents are converted into vector embeddings for semantic search.

🔎 Retrieval Augmented Generation (RAG)

EEV AI uses a RAG architecture to ensure responses are grounded in real data.

User Query
   ↓
Embedding
   ↓
Vector Search
   ↓
Relevant Documents
   ↓
LLM Reasoning
   ↓
Final Response

Benefits:

✔ Accurate answers
✔ Reduced hallucination
✔ Enterprise knowledge grounding

🎙 Real-Time Voice AI

EEV integrates LiveKit Voice Agents with streaming responses.

Features:

Real-time speech recognition

AI voice assistant

low-latency streaming responses

phone call integration

conversational AI workflows

🧠 System Architecture
                    ┌──────────────────────────┐
                    │        User Query        │
                    └────────────┬─────────────┘
                                 │
                         Speech / Text
                                 │
                     ┌───────────▼───────────┐
                     │   Voice / Chat Agent  │
                     │       (LiveKit)       │
                     └───────────┬───────────┘
                                 │
                        Query Processing
                                 │
                     ┌───────────▼───────────┐
                     │   RAG Pipeline        │
                     │ (LangChain + LLM)     │
                     └───────────┬───────────┘
                                 │
                       Semantic Retrieval
                                 │
                        ┌────────▼─────────┐
                        │ Pinecone Vector  │
                        │      Database    │
                        └────────┬─────────┘
                                 │
                        Relevant Documents
                                 │
                     ┌───────────▼───────────┐
                     │      LLM Response     │
                     └───────────┬───────────┘
                                 │
                         Voice / Text Output
🛠 Technology Stack
Component	Technology
Backend	FastAPI
LLM	OpenAI
Vector Database	Pinecone
Embeddings	OpenAI Embeddings
AI Framework	LangChain
Voice Infrastructure	LiveKit
Speech Recognition	Deepgram
Text-to-Speech	Deepgram Aura
Containerization	Docker
Deployment	Cloud / VPS
📂 Project Structure
eev-ai/
│
├── app/
│   ├── api/
│   │   ├── routes/
│   │   └── logger/
│   │
│   ├── toolkit/
│   │   └── agent_toolkit.py
│   │
│   ├── voice_agent_app/
│   │   └── telephony_agent.py
│   │
│   ├── schemas/
│   │   └── agent_schemas.py
│   │
│   └── eev_configurations/
│       └── config.py
│
├── docker/
├── requirements.txt
└── README.md
⚡ Installation
1️⃣ Clone the repository
git clone https://github.com/yourusername/eev-ai.git
cd eev-ai
2️⃣ Install dependencies
pip install -r requirements.txt
3️⃣ Configure environment variables

Create .env

OPENAI_API_KEY=
PINECONE_API_KEY=
LIVEKIT_URL=
EEV_BACKEND_API_KEY=
4️⃣ Start the API
python run.py
5️⃣ Start the voice agent
python app/voice_agent_app/telephony_agent.py
🔌 API Example
Query Endpoint
POST /chat-agent/eev-voice-rag

Request:

{
  "user_query": "How can I reset my password?",
  "session_id": "user123",
  "index_name": "bank-docs"
}

Response:

{
  "bot_response": "To reset your password, open the banking app and follow the forgot password process."
}
📊 Performance Optimizations

EEV AI includes several optimizations:

✔ Cached vector retrieval
✔ Streaming LLM responses
✔ Asynchronous document ingestion
✔ HTTP connection pooling
✔ Low-latency voice pipeline

These ensure fast real-time responses during phone calls.

🔐 Security

The platform follows secure AI deployment practices:

API authentication

Controlled document ingestion

secure vector database access

prompt injection protection

data privacy compliance

🧪 Future Roadmap

Planned improvements:

Multi-language voice support

African-accent voice models

agent reasoning workflows

knowledge graph integration

advanced document extraction pipelines

👨‍💻 Author
Joshua

AI Engineer | Data Scientist

Interested in:

Generative AI systems

Voice AI agents

Intelligent document processing

Enterprise AI automation

⭐ Support the Project

If you find this project useful:

⭐ Star the repository
⭐ Share it
⭐ Contribute improvements

🤝 Contributing

Contributions are welcome.

Fork the repository

Create a feature branch

Submit a pull request
