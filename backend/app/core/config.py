from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes:int = 60
    medical_record_key: str
    tz: str = "Asia/Shanghai"

    class Config:
        extra = "ignore"  # 忽略多余配置
        env_file = ".env"      
        env_file_encoding = "utf-8-sig"

settings = Settings()
