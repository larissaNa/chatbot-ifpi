import requests
import re, json
import asyncio
from apify_client import ApifyClient
from PIL import Image
from io import BytesIO
import os

APIKEY_VORTICE = ""

def get_instagram_avatar(profile_id: str) -> str:
    """
    Retorna a URL da imagem de perfil pública do Instagram, via scraping.
    """
    try:
        url = f"https://www.instagram.com/{profile_id}/"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        print(response.text)
        # Regex para encontrar o avatar (imagem de perfil)
        match = re.search(r'"Foto do perfil":"([^"]+)"', response.text)
        if match:
            avatar_url = match.group(1).replace("\\u0026", "&")
            return avatar_url
        else:
            return "/static/assets/image/avatar.png"  # fallback local

    except Exception as e:
        print(f"[Erro Instagram Avatar] {e}")
        return "/static/assets/image/avatar.png"

def getpost(account):
    apify_client = ApifyClient(APIKEY_VORTICE)

    # Start an Actor and wait for it to finish.
    actor_client = apify_client.actor('apify/instagram-profile-scraper')
    input_data = {"resultsLimit": 1, "usernames": [f"{account}"]}
    call_result = actor_client.call(run_input=input_data, timeout_secs=300)


    if call_result is None:
        print('Actor run failed.')
        return
    
    # Fetch results from the Actor run's default dataset.
    dataset_client = apify_client.dataset(call_result['defaultDatasetId'])
    dataset_items = dataset_client.list_items().items  # <- lista de dicionários
    # print(dataset_client)
    
    if dataset_items:
        avatar_url = dataset_items[0].get("profilePicUrl")  # ou outro campo adequado
        return baixar_e_converter_para_jpeg(avatar_url, account)
    else:
        return "/static/assets/images/avatar.png"

def baixar_e_converter_para_jpeg(url: str, nome_arquivo: str = "imagem_convertida.jpg"):
    try:
        # Baixa a imagem com cabeçalho amigável
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()

        # Abre imagem em memória
        imagem = Image.open(BytesIO(response.content))

        # Converte para RGB se estiver em modo incompatível com JPEG
        if imagem.mode in ("RGBA", "P"):
            imagem = imagem.convert("RGB")

        # Garante extensão correta
        if not nome_arquivo.lower().endswith(".jpg"):
            nome_arquivo += ".jpg"

        # Define caminho absoluto para apps/static/images
        pasta_static = os.path.join(os.path.dirname(__file__), "..", "static", "assets", "images")
        os.makedirs(pasta_static, exist_ok=True)

        caminho_completo = os.path.join(pasta_static, nome_arquivo)
        imagem.save(caminho_completo, format="JPEG", quality=90)

        print(f"[OK] Imagem salva: {caminho_completo}")
        return f"/static/assets/images/{nome_arquivo}"

    except Exception as e:
        print(f"Erro ao processar imagem: {e}")
        return "/static/assets/images/avatar.png"
    
def salvar_imagem_local(url: str, nome_arquivo: str) -> str:
    """
    Baixa uma imagem a partir de uma URL e salva como JPEG na pasta static/images/posts.
    Retorna o caminho relativo para uso no HTML.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()

        imagem = Image.open(BytesIO(response.content))
        if imagem.mode in ("RGBA", "P"):
            imagem = imagem.convert("RGB")

        pasta_destino = os.path.join(os.path.dirname(__file__), "..", "static", "assets", "images", "posts")
        os.makedirs(pasta_destino, exist_ok=True)

        caminho_arquivo = os.path.join(pasta_destino, f"{nome_arquivo}.jpg")
        imagem.save(caminho_arquivo, format="JPEG", quality=90)

        return f"/static/assets/images/posts/{nome_arquivo}.jpg"

    except Exception as e:
        print(f"[ERRO] Falha ao salvar imagem: {e}")
        return "/static/assets/images/placeholder.jpg"