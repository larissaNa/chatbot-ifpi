import requests
from datetime import datetime
from urllib.parse import urlencode
# from transformers import pipeline
# import os
# os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# TODO Corrigir quando a imagem vem em formato de CAROUSSEL ou VÍDEO
# TODO Revisar métrica de Likes and Comments
# TODO Revisar layout do navigation


class APINaoDefinida(Exception):
    pass

def executar_consulta(servico, parametros):
    """
    Consulta a API da Fanpage Karma com base na estrutura esperada.
    """
    if not servico.endpoint_api:
        raise APINaoDefinida("O serviço selecionado não possui uma API configurada.")

    # Elementos necessários
    version = "v1"
    network = servico.tipo_conteudo.lower()  # ex: facebook, instagram, etc.
    profile_id = parametros.get("profile_id")
    task = parametros.get("task") or "posts"
    token = servico.api_token
    period = _formatar_periodo(parametros)

    if not all([network, profile_id, token]):
        raise ValueError("Dados incompletos para montar a URL da API.")
    # if period=="None_None":
    #     query_params = {
    #     "token": token
    #     } 
    # else:
    query_params = {
    "token": token,
    "period": period}       
    # Monta a URL completa da chamada
    url_base = f"{servico.endpoint_api}/{version}/{network}/{profile_id}/{task}"
    url_final = f"{url_base}?{urlencode(query_params)}"

    try:
        response = requests.get(url_final, timeout=300)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Erro ao consultar API externa: {str(e)}")


def _formatar_periodo(parametros):
    """
    Gera o valor de 'period' no formato YYYY-MM-DD_YYYY-MM-DD.
    """
    inicio = parametros.get("inicio")
    fim = parametros.get("fim")
    if isinstance(inicio, datetime): inicio = inicio.strftime("%Y-%m-%d")
    if isinstance(fim, datetime): fim = fim.strftime("%Y-%m-%d")
    return f"{inicio}_{fim}"

# def classificar_emocoes(texto):
#     classifier = pipeline("zero-shot-classification", model="joeddav/xlm-roberta-large-xnli")

#     # 3) Rótulos de emoção em português
#     candidate_labels = ["alegria", "tristeza", "raiva", "ironia", "satisfação", "insatisfação", "neutro"]
#     emocoes = []
#     # 4) Classificação
#     resultado = classifier(
#         texto,
#         candidate_labels=candidate_labels,
#         hypothesis_template="Este texto expressa {}?"
#     )
#     for label, score in zip(resultado["labels"], resultado["scores"]):
#         emocoes.append({label: score})
#         print(f"  {label}: {score:.4f}")
#     return emocoes
