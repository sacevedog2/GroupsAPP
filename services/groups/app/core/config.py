import logging
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "GroupsApp - Groups Service"
    API_V1_STR: str = "/v1"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/groupsdb"
    
    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    
    # gRPC
    GRPC_PORT: int = 50051
    
    # Auth Service
    AUTH_GRPC_URL: str = "localhost:50051" # Overridden in docker-compose


    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
