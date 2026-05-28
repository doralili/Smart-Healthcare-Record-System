from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    
    database_url: str = "postgresql+psycopg2://health_app:OpenGauss%40123@localhost:5433/health_security"
    jwt_secret: str = "dev_secret_for_course_project"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes:int = 60
    medical_record_key: str = "Z8L3gMkFw9dJZJzJCe4kF5rLCvB2nLrU7NxQ8xQh5gg="
    tz: str = "Asia/Shanghai"

    class Config:
        extra = "ignore"  # 忽略多余配置
        env_file = ".env"      
        env_file_encoding = "utf-8"

settings = Settings()