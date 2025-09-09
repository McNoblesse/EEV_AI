#Importing necessary libraries
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

load_dotenv()

os.environ["GOOGLE_API_KEY"] = accessKeys.GEMINI_API_KEY

embed_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

pc = Pinecone(api_key=accessKeys.pinecone_api)
spec = ServerlessSpec(cloud="aws", region="us-east-1")
index_name = 'eev-ai-unstructured-data'
index = pc.Index(index_name)
vectorstore = PineconeVectorStore(index=index, embedding=embed_model, text_key="text")

@tool
def send_mail_to_human_agent_sync(mail_input):
    """
    Sends an HTML email to multiple human agents for Tier 2 support requests.

    This tool handles both dictionary inputs and string inputs formatted like:
    "mail: {'subject': 'Subject line', 'body': 'HTML content'}"

    Args:
        mail_input (dict or str): Either a dictionary containing subject and HTML body,
                                 or a string representation of such a dictionary

    Returns:
        str: Confirmation message that the email was sent successfully

    Example:
        # With dictionary input
        send_mail_to_human_agent_sync({
            "subject": "Support Request",
            "body": "<html><body>Email content</body></html>"
        })

        # With string input
        send_mail_to_human_agent_sync("mail: {'subject': 'Support Request', 'body': '<html>...'}")
    """

    # Helps to convert string passed by llm into dictionary
    if isinstance(mail_input, str):
        try:
            # Removing "mail:" prefix if present
            if "mail:" in mail_input:
                mail_str = mail_input.replace("mail:", "").strip()
            else:
                mail_str = mail_input.strip()

            # Converts the mail_str passed into it into a dictionary element
            mail = ast.literal_eval(mail_str)
        except Exception as e:
            return f"Error parsing email data: {str(e)}"
    else:
        # An else statement in a case whereby llm outputs a dictionary
        mail = mail_input

    # Validates the mail dictionary
    if not isinstance(mail, dict) or "subject" not in mail or "body" not in mail:
        return "Invalid email format. Must include 'subject' and 'body' fields."

    async def _send_email(mail_dict):
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
            recipients=[
                "ayomidedipeolu@gmail.com"
            ],
            body=body,
            subtype="html"
        )
        fm = FastMail(config)
        await fm.send_message(message)
        return "Email sent successfully"

    # Run the async function synchronously
    try:
        return asyncio.run(_send_email(mail))
    except Exception as e:
        return f"Error sending email: {str(e)}"
    

@tool
def retriever_tool(query: str) -> str:
    """Retrieve FAQ data for Optimus or Branch systems."""
    if not query.strip():
        return "Error: Please provide a search query"
    try:
        results = vectorstore.similarity_search(query.strip(), k=3)
        if not results:
            return f"No information found for '{query}'"
        output = ""
        for i, doc in enumerate(results, 1):
            text = doc.metadata.get('text', doc.page_content)
            output += f"Result {i}: {text}\n\n"
        return output
    except Exception as e:
        return f"Search failed: {str(e)}"