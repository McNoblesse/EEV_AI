from pydantic_settings import SettingsConfigDict, BaseSettings

class AccessKeys(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", 
                                      case_sensitive=True)
    
    pinecone_api:str
    OPENAI_API_KEY:str
    tier_1_auth_key:str
    GEMINI_API_KEY:str
    POSTGRES_URL:str
    SQLITE_DB_PATH:str

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    
accessKeys = AccessKeys()