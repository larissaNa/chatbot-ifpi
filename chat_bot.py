import ollama
from pdf2image import convert_from_path
import pytesseract
#comandos para lembrar:
#ollama run >modelo<
#ollama list
#ollama serve

# Função para converter PDF em texto usando OCR 
def pdf_to_text_with_ocr(pdf_path, txt_path):
    # Converte cada página do PDF em uma imagem
    pages = convert_from_path(pdf_path, dpi=300)
    text_content = ""

    # Realiza OCR em cada página
    for i, page in enumerate(pages, start=1):
        print(f"Processando página {i}...")
        text = pytesseract.image_to_string(page, lang="por")  # Especifica "por" para português
        text_content += text + "\n"

    # Salva o texto extraído em um arquivo .txt
    with open(txt_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(text_content)

    print(f"PDF convertido com sucesso para o arquivo de texto: {txt_path}")
    return text_content


# Função para enviar perguntas ao chatbot
def gerar_resposta(pergunta, contexto):
    print("Enviando pergunta ao chatbot...")
    response = ollama.chat(
        model='llama3',
        messages=[
            {
                'role': 'system',
                'content': 'Você é um assistente treinado para responder com base nas normas e diretrizes do IFPI.'
            },
            {
                'role': 'user',
                'content': f"Baseando-se no seguinte contexto: {contexto}\n\nPergunta: {pergunta}"
            }
        ]
    )
    return response['message']['content']


# Programa principal
if __name__ == "__main__":
    # Caminho para o PDF com normas e diretrizes
    pdf_path = "teste2.pdf"
    txt_path = "teste2.txt"

    # Extração de texto do PDF
    print("Extraindo texto do PDF...")
    texto_extraido = pdf_to_text_with_ocr(pdf_path, txt_path)
    # with open(txt_path, "r") as texto:
    #     texto_extraido = texto.read()
    # Loop para interação com o chatbot
    print("Chat bot IFPI - digite 'sair' para encerrar o chat")
    while True:
        pergunta = input("Você: ")
        if pergunta.lower() == "sair":
            break
        resposta = gerar_resposta(pergunta, texto_extraido)
        print(f"Bot: {resposta}")
