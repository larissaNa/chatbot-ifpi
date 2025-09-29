import os
from dotenv import load_dotenv

load_dotenv()

def get_env_var(var):
    value = os.getenv(var)
    if not value:
        raise EnvironmentError(f"Variável de ambiente {var} não definida.")
    return value

TAVILY_API_KEY = get_env_var("TAVILY_API_KEY")
ANTHROPIC_API_KEY = get_env_var("ANTHROPIC_API_KEY")
