import os
import yaml
from dotenv import load_dotenv

load_dotenv()

def get_env_vars():
    return {
        "github_token": os.getenv("GITHUB_TOKEN"),
        "mongo_uri": os.getenv("MONGO_URI"),
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
        "model_name": os.getenv("MODEL_NAME", "gemma2:2b")
    }

def load_config(config_path="config.yaml"):
    with open(config_path, "r") as file:
        return yaml.safe_load(file)