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

# Set environment variables inside the container from the build-time arguments
ENV pinecone_api=$pinecone_api
ENV OPENAI_API_KEY=$OPENAI_API_KEY
ENV tier_1_auth_key=$tier_1_auth_key
ENV GEMINI_API_KEY=$GEMINI_API_KEY
ENV POSTGRES_URL=$POSTGRES_URL
ENV SQLITE_DB_PATH=$SQLITE_DB_PATH

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY . .

# Expose the port for the backend
EXPOSE 8056