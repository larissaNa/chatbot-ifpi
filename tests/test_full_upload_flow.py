import os
import sys
import uuid

# Adiciona o diretório raiz ao path
sys.path.append(os.getcwd())

from apps.core.documents.agents.link_analysis_agent import _analise_basica_url
from apps.core.documents.agents.extraction_agent import extrair_conteudo

def test_full_flow_txt():
    print("Testando fluxo completo para TXT...")
    # Cria um arquivo temporário
    test_file = "test_upload.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("Conteudo institucional do IFPI para teste de TXT.")
    
    abs_path = os.path.abspath(test_file)
    url = f"file:///{abs_path.replace(os.sep, '/')}"
    
    print(f"URL: {url}")
    
    # 1. Link Analysis
    analise = _analise_basica_url(url)
    print(f"Analise: {analise}")
    assert analise["tipo_conteudo"] == "TXT"
    
    # 2. Extraction
    resultado = extrair_conteudo.invoke({"analise": analise})
    print(f"Resultado extração: {len(resultado['documentos'])} documentos")
    assert len(resultado["documentos"]) == 1
    assert "IFPI" in resultado["documentos"][0]["texto"]
    
    os.remove(test_file)
    print("Sucesso TXT!\n")

def test_full_flow_docx():
    print("Testando fluxo completo para DOCX...")
    import docx
    test_file = "test_upload.docx"
    doc = docx.Document()
    doc.add_paragraph("Resolucao do IFPI em formato Word.")
    doc.save(test_file)
    
    abs_path = os.path.abspath(test_file)
    url = f"file:///{abs_path.replace(os.sep, '/')}"
    
    # 1. Link Analysis
    analise = _analise_basica_url(url)
    print(f"Analise: {analise}")
    assert analise["tipo_conteudo"] == "DOCX"
    
    # 2. Extraction
    resultado = extrair_conteudo.invoke({"analise": analise})
    print(f"Resultado extração: {len(resultado['documentos'])} documentos")
    assert len(resultado["documentos"]) == 1
    assert "Resolucao" in resultado["documentos"][0]["texto"]
    
    os.remove(test_file)
    print("Sucesso DOCX!\n")

if __name__ == "__main__":
    try:
        test_full_flow_txt()
        test_full_flow_docx()
        print("Fluxos completos validados!")
    except Exception as e:
        print(f"Erro nos testes de fluxo: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
