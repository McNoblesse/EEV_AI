from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # model_config = SettingsConfigDict(
    #     env_file="../.env",
    #     case_sensitive=False,
    #     env_file_encoding="utf-8",
    #     extra="ignore",
    # )
    
    OPENAI_API_KEY:str
    PINECONE_API_KEY:str
    GEMINI_API_KEY:str
    MEMORY_DB:str
    RESEND_API:str
    OPENAI_EMBEDDING_NAME:str
    PINECONE_CLOUD:str
    PINECONE_REGION:str
    ENDPOINT_AUTH_KEY:str

settings = Settings()