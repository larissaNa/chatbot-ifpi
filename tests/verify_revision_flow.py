
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.append(os.getcwd())

from apps import create_app, db
from apps.config import config_dict
from apps.authentication.models import DocumentoOficial, DocumentoVersao, LogProcessamento
from apps.core.services.revision_service import executar_revisao_documento

# Obtém configuração de Debug
get_config = config_dict['Debug']
app = create_app(get_config)

with app.app_context():
    db.create_all() # Garante que as tabelas existem
    print("=== Iniciando Teste de Fluxo de Revisão ===")
    
    # 1. Setup: Criar Documento Fake no Banco
    # Verifica se já existe
    doc = DocumentoOficial.query.filter_by(titulo="Documento de Teste Automatizado").first()
    if not doc:
        print("Criando documento de teste no banco...")
        doc = DocumentoOficial(
            titulo="Documento de Teste Automatizado",
            url="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf", # URL pública estável
            descricao="Documento criado para testar o fluxo de revisão."
        )
        db.session.add(doc)
        db.session.commit()
    else:
        print(f"Documento de teste já existe (ID: {doc.id}). Atualizando URL para teste remoto...")
        doc.url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
        db.session.commit()

    # 2. Executar Revisão
    print(f"Acionando revisão para o documento ID {doc.id}...")
    resultado = executar_revisao_documento(doc.id)
    
    print("\n=== Resultado da Execução ===")
    print(resultado)
    
    # 3. Verificar Logs e Versões
    print("\n=== Verificando Banco de Dados ===")
    logs = LogProcessamento.query.filter_by(documento_id=doc.id).order_by(LogProcessamento.id.desc()).limit(5).all()
    print(f"Logs encontrados: {len(logs)}")
    for l in logs:
        print(f" - [{l.agente}] {l.acao}: {l.detalhe[:50]}...")
        
    versoes = DocumentoVersao.query.filter_by(documento_id=doc.id).all()
    print(f"Versões criadas: {len(versoes)}")
    for v in versoes:
        print(f" - Versão {v.versao_numero} (Criada em: {v.criado_em})")

    print("\n=== Teste Concluído ===")
