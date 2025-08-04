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
    MAIL_USERNAME:str
    MAIL_PASSWORD:str
    MAIL_FROM:str
    MAIL_PORT:int
    MAIL_SERVER:str
    MAIL_FROM_NAME:str
    # freshdesk config
    FRESHDESK_API_KEY:str
    FRESHDESK_DOMAIN:str
    TICKET_QUEUE:str
    # Redis Configuration
    REDIS_HOST:str
    REDIS_PORT:int
    REDIS_PASSWORD:str

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    
accessKeys = AccessKeys()