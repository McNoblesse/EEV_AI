# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Declare build-time arguments for all your secrets
ARG pinecone_api
ARG OPENAI_API_KEY
ARG tier_1_auth_key
ARG GEMINI_API_KEY
ARG POSTGRES_URL
ARG SQLITE_DB_PATH
ARG MAIL_USERNAME
ARG MAIL_PASSWORD
ARG MAIL_FROM
ARG MAIL_PORT
ARG MAIL_SERVER
ARG MAIL_FROM_NAME
ARG FRESHDESK_API_KEY
ARG FRESHDESK_DOMAIN
ARG TICKET_QUEUE
ARG REDIS_HOST
ARG REDIS_PORT
ARG REDIS_PASSWORD

# Set environment variables inside the container from the build-time arguments
ENV pinecone_api=$pinecone_api
ENV OPENAI_API_KEY=$OPENAI_API_KEY
ENV tier_1_auth_key=$tier_1_auth_key
ENV GEMINI_API_KEY=$GEMINI_API_KEY
ENV POSTGRES_URL=$POSTGRES_URL
ENV SQLITE_DB_PATH=$SQLITE_DB_PATH
ENV MAIL_USERNAME=$MAIL_USERNAME
ENV MAIL_PASSWORD=$MAIL_PASSWORD
ENV MAIL_FROM=$MAIL_FROM
ENV MAIL_PORT=$MAIL_PORT
ENV MAIL_SERVER=$MAIL_SERVER
ENV MAIL_FROM_NAME=$MAIL_FROM_NAME
ENV FRESHDESK_API_KEY=$FRESHDESK_API_KEY
ENV FRESHDESK_DOMAIN=$FRESHDESK_DOMAIN
ENV TICKET_QUEUE=$TICKET_QUEUE
ENV REDIS_HOST=$REDIS_HOST
ENV REDIS_PORT=$REDIS_PORT
ENV REDIS_PASSWORD=$REDIS_PASSWORD

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Expose the port for the backend
EXPOSE 8056