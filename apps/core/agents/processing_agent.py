from langchain_core.tools import tool

@tool
def processar_texto(texto: str) -> dict:
    chunks = texto.split("\n\n")  # simples; depois você melhora
    hash_content = hash(texto)

    return {
        "hash": hash_content,
        "chunks": chunks
    }
