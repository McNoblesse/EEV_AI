from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
import time
from dotenv import load_dotenv
import os
import json
import asyncio
import ast
from langchain_core.tools import tool
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from config.access_keys import accessKeys
import logging

logger = logging.getLogger(__name__)
load_dotenv()

os.environ["GOOGLE_API_KEY"] = accessKeys.GEMINI_API_KEY

# Initialize embeddings and vector store
embed_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

pc = Pinecone(api_key=accessKeys.pinecone_api)
spec = ServerlessSpec(cloud="aws", region="us-east-1")
index_name = 'eev-ai-unstructured-data'
index = pc.Index(index_name)
vectorstore = PineconeVectorStore(index=index, embedding=embed_model, text_key="text")

@tool
def send_mail_to_human_agent_sync(mail_input: dict) -> str:
    """
    Sends an HTML email to human agents for escalation requests.
    
    Args:
        mail_input (dict): Dictionary containing subject and HTML body
        
    Returns:
        str: Confirmation message
        
    Example:
        send_mail_to_human_agent_sync({
            "subject": "Support Request",
            "body": "<html><body>Email content</body></html>"
        })
    """
    try:
        # Validate input
        if not isinstance(mail_input, dict):
            return "Error: Input must be a dictionary"
            
        if "subject" not in mail_input or "body" not in mail_input:
            return "Error: Missing required fields 'subject' or 'body'"
        
        async def _send_email(mail_dict: dict) -> str:
            config = ConnectionConfig(
                MAIL_USERNAME="ayomidedipeolu2003@gmail.com",
                MAIL_PASSWORD="aniqtzdrltugjjwn",
                MAIL_FROM="ayomidedipeolu2003@gmail.com",
                MAIL_PORT=587,
                MAIL_SERVER="smtp.gmail.com",
                MAIL_FROM_NAME="EEV AI Agent",
                MAIL_STARTTLS=True,
                MAIL_SSL_TLS=False,
                USE_CREDENTIALS=True,
                VALIDATE_CERTS=True,
            )
            
            subject = f"🚨 ESCALATION: {mail_dict['subject']}"
            body = mail_dict["body"]
            
            message = MessageSchema(
                subject=subject,
                recipients=["ayomidedipeolu@gmail.com"],
                body=body,
                subtype="html"
            )
            
            fm = FastMail(config)
            await fm.send_message(message)
            return "Email sent successfully to human agent"
        
        # Run async function synchronously
        return asyncio.run(_send_email(mail_input))
        
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return f"Error sending email: {str(e)}"

@tool
def retriever_tool(query: str) -> str:
    """
    Retrieve relevant information from knowledge base for customer queries.
    
    Args:
        query (str): Search query for relevant information
        
    Returns:
        str: Retrieved information or error message
    """
    if not query or not query.strip():
        return "Error: Please provide a search query"
    
    try:
        # Perform similarity search
        results = vectorstore.similarity_search(query.strip(), k=3)
        
        if not results:
            return f"No relevant information found for: '{query}'"
        
        # Format results
        formatted_results = []
        for i, doc in enumerate(results, 1):
            # Use metadata text if available, otherwise page content
            text = doc.metadata.get('text', doc.page_content)
            source = doc.metadata.get('source', 'Unknown')
            
            # Truncate long text
            if len(text) > 500:
                text = text[:500] + "..."
                
            formatted_results.append(f"Result {i} (Source: {source}): {text}")
        
        return "\n\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Knowledge retrieval failed: {str(e)}")
        return f"Search failed: {str(e)}"

@tool
def greeting_response_tool(user_message: str) -> str:
    """
    Generate appropriate greeting responses based on user message.
    
    Args:
        user_message (str): User's greeting message
        
    Returns:
        str: Appropriate greeting response
    """
    user_message_lower = user_message.lower()
    
    greeting_responses = {
        'hello': "Hello! Welcome to EEV AI. How can I assist you today?",
        'hi': "Hi there! I'm here to help. What can I do for you?",
        'hey': "Hey! Great to see you. How can I assist?",
        'good morning': "Good morning! Hope you're having a great day. How can I help?",
        'good afternoon': "Good afternoon! What can I assist you with today?",
        'good evening': "Good evening! How can I help you tonight?",
        'how are you': "I'm functioning well, thank you! How can I assist you today?",
        'what\'s up': "All systems operational! How can I help you?"
    }
    
    # Find matching greeting
    for greeting, response in greeting_responses.items():
        if greeting in user_message_lower:
            return response
    
    # Default greeting response
    return "Hello! Thank you for reaching out. How can I assist you today?"

@tool  
def faq_retrieval_tool(topic: str) -> str:
    """
    Retrieve frequently asked questions for common topics.
    
    Args:
        topic (str): Topic to get FAQs for
        
    Returns:
        str: FAQ information
    """
    common_faqs = {
        'pricing': "Our pricing starts at $99/month for basic features. Enterprise plans available.",
        'features': "Key features include AI assistance, multi-channel support, and analytics.",
        'support': "Support is available 24/7 via email, chat, and phone.",
        'setup': "Setup takes about 15 minutes. We provide full documentation.",
        'integration': "We integrate with Freshdesk, Slack, and major CRM systems."
    }
    
    topic_lower = topic.lower()
    for faq_topic, answer in common_faqs.items():
        if faq_topic in topic_lower:
            return answer
    
    return f"No specific FAQ found for '{topic}'. Please try a more specific query or contact support for detailed information."