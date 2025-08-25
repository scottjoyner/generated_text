from pydantic import BaseModel
import os

class Settings(BaseModel):
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql+psycopg2://postgres:postgres@localhost:5432/hfdb")
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "neo4j")
    uvicorn_host: str = os.getenv("UVICORN_HOST", "0.0.0.0")
    uvicorn_port: int = int(os.getenv("UVICORN_PORT", "8000"))

settings = Settings()
