from pydantic_settings import SettingsConfigDict, BaseSettings

class AccessKeys(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", 
                                      case_sensitive=True, 
                                      extra='ignore')
    
    pinecone_api: str
    OPENAI_API_KEY: str
    TIER1_API_KEY: str
    TIER2_API_KEY: str
    TIER3_API_KEY: str
    GEMINI_API_KEY: str
    JWT_SECRET_KEY: str  # Changed to match .env
    JWT_ALGORITHM: str
    POSTGRES_MEMORY_URL: str

accessKeys = AccessKeys()