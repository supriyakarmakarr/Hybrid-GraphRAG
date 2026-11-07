"""
Application configuration via environment variables.
Never trust user-supplied values for security-sensitive fields.
"""
from pydantic_settings import BaseSettings
from typing import Literal
import os


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"

    # JWT (RS256 — private key signs, public key verifies)
    JWT_PRIVATE_KEY: str = ""
    JWT_PUBLIC_KEY: str = ""
    JWT_PRIVATE_KEY_PATH: str = ""
    JWT_PUBLIC_KEY_PATH: str = ""
    JWT_ALGORITHM: str = "RS256"
    JWT_EXPIRY_MINUTES: int = 15  # Short expiry to limit exposure of leaked tokens
    JWT_ISSUER: str = "graphrag-auth"
    JWT_AUDIENCE: str = "graphrag-api"

    # LLM
    LLM_PROVIDER: Literal["anthropic", "openai"] = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "claude-3-5-haiku-20241022"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.0

    # Databases (psycopg connection format)
    POSTGRES_URL: str = ""
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    NEO4J_URL: str = ""
    NEO4J_USER: str = ""
    NEO4J_PASSWORD: str = ""

    # Embedding
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384
    QDRANT_COLLECTION: str = "chunks_multilingual_minilm_l12_v1"
    CORS_ORIGINS: str = ""

    # Upload
    MAX_UPLOAD_MB: int = 10
    ALLOWED_EXTENSIONS: str = "pdf,docx,txt"

    # Retrieval limits
    DEFAULT_MAX_CHUNKS: int = 7
    DEFAULT_MAX_GRAPH_EDGES: int = 50

    @property
    def jwt_private_key(self) -> str:
        if self.JWT_PRIVATE_KEY:
            return self.JWT_PRIVATE_KEY.replace("\\n", "\n")
        path = self.JWT_PRIVATE_KEY_PATH
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    @property
    def jwt_public_key(self) -> str:
        if self.JWT_PUBLIC_KEY:
            return self.JWT_PUBLIC_KEY.replace("\\n", "\n")
        path = self.JWT_PUBLIC_KEY_PATH
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
