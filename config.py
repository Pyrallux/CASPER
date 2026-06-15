import os

class Config:
    GITLAB_URL = os.environ.get("GITLAB_URL", "https://gitlab.example.com").rstrip("/")
    GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
    
    INTERNAL_LLM_API_BASE = os.environ.get("INTERNAL_LLM_API_BASE")
    INTERNAL_LLM_API_KEY = os.environ.get("INTERNAL_LLM_API_KEY")
    LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "gpt-4o")
    
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "casper_memory.sqlite")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.GITLAB_TOKEN: missing.append("GITLAB_TOKEN")
        if not cls.INTERNAL_LLM_API_KEY: missing.append("INTERNAL_LLM_API_KEY")
        if not cls.INTERNAL_LLM_API_BASE: missing.append("INTERNAL_LLM_API_BASE")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")