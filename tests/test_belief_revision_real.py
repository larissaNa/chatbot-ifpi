import sys
import os
import glob
import json
import numpy as np

# Adiciona o diretório raiz ao path
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from apps.core.documents.agents.processing_agent import processar_conteudo
from apps.core.documents.agents.belief_revision_agent import revisar_crenca

def find_file(suffix):
    paths = glob.glob(f"apps/uploads/*{suffix}")
    if not paths:
        raise FileNotFoundError(f"Arquivo com sufixo {suffix} não encontrado em apps/uploads")
    return os.path.basename(paths[0]), paths[0]

def run_real_pipeline(filename, content, doc_title="Documento Oficial", fontes=None):
    if fontes is None:
        fontes = [{"url": f"file:///apps/uploads/{filename}", "status": "VALIDO", "http_status": 200}]
        
    extracao = {
        "fonte": f"file:///apps/uploads/{filename}",
        "tipo_extracao": "TXT_TEXTUAL",
        "documentos": [
            {
                "id_documento": "doc_teste_real",
                "titulo": doc_title,
                "texto": content,
                "metadata": {
                    "paginas_estimadas": 1,
                    "idioma": "pt",
                    "tipo_extracao": "TXT_TEXTUAL"
                }
            }
        ],
        "observacoes": "",
        "proximo_agente": "AGENTE_PROCESSAMENTO"
    }
    
    # Executa o processador real para gerar chunks e embeddings reais
    resultado_processamento = processar_conteudo.invoke({"extracao": extracao})
    return resultado_processamento

def run_real_battery():
    print("=" * 60)
    print("INICIANDO VALIDAÇÃO EXPERIMENTAL COM DOCUMENTOS REAIS (24 CASOS)")
    print("=" * 60)
    
    # 1. Localiza os 6 arquivos reais
    try:
        name_sabados, path_sabados = find_file("_Informacoes_sobre_sabados_letivos.txt")
        name_proeja, path_proeja = find_file("_horarios_proeja.txt")
        name_escala, path_escala = find_file("_ESCALA_DOCENTE_-_SABADOS_LETIVOSESCALA_DOCENTE_-_SABADOS_LETIVOS.txt")
        name_vestuario, path_vestuario = find_file("_horarios_vestuario.txt")
        name_informatica, path_informatica = find_file("_horarios_informatica.txt")
        name_matematica, path_matematica = find_file("_horarios_matematica.txt")
    except FileNotFoundError as e:
        print(f"Erro: {e}")
        print("Certifique-se de executar o teste a partir da raiz do projeto.")
        sys.exit(1)
        
    # 2. Carrega o conteúdo original dos arquivos
    with open(path_sabados, "r", encoding="utf-8") as f:
        orig_sabados = f.read()
    with open(path_proeja, "r", encoding="utf-8") as f:
        orig_proeja = f.read()
    with open(path_escala, "r", encoding="utf-8") as f:
        orig_escala = f.read()
    with open(path_vestuario, "r", encoding="utf-8") as f:
        orig_vestuario = f.read()
    with open(path_informatica, "r", encoding="utf-8") as f:
        orig_informatica = f.read()
    with open(path_matematica, "r", encoding="utf-8") as f:
        orig_matematica = f.read()

    print(f"Arquivos reais carregados com sucesso:")
    print(f" - Sábados Letivos ({len(orig_sabados)} chars)")
    print(f" - PROEJA ADM ({len(orig_proeja)} chars)")
    print(f" - Escala Docente ({len(orig_escala)} chars)")
    print(f" - PROEJA Vestuário ({len(orig_vestuario)} chars)")
    print(f" - Horários Informática ({len(orig_informatica)} chars)")
    print(f" - Horários Matemática ({len(orig_matematica)} chars)")
    print("\nInicializando embeddings reais para o estado anterior...")

    # Gera embeddings originais (estado anterior)
    proc_sabados_orig = run_real_pipeline(name_sabados, orig_sabados, "Informações Sábados Letivos")
    proc_proeja_orig = run_real_pipeline(name_proeja, orig_proeja, "Horários PROEJA ADM")
    proc_escala_orig = run_real_pipeline(name_escala, orig_escala, "Escala Docente Sábados")
    proc_vestuario_orig = run_real_pipeline(name_vestuario, orig_vestuario, "Horários Vestuário")
    proc_informatica_orig = run_real_pipeline(name_informatica, orig_informatica, "Horários Informática")
    proc_matematica_orig = run_real_pipeline(name_matematica, orig_matematica, "Horários Matemática")

    # MUTAÇÕES DE CONTEÚDO (Alterações de Conteúdo - 6 casos)
    # Caso 7 (Sabados): Reestruturação do cronograma de sábados letivos
    mut_sabados_datas = """Sobre os Sábados Letivos do semestre 2026.1:
A Direção de Ensino convoca todos os docentes e discentes do Ensino Médio Integrado para as atividades letivas especiais aos sábados, visando à reposição de carga horária e revisões para o ENEM.

A programação oficial e as escalas foram alteradas e redefinidas pela coordenação acadêmica:

05/09 - Aulas de reposição de todas as disciplinas
12/09 - Evento Cultural: Feira de Ciências e Tecnologia
19/09 - Aplicação do 1º Simulado ENEM para as turmas de 3º ano
26/09 - Evento de Extensão: Mesa redonda sobre Direitos Humanos (NEABI)
10/10 - Aulas normais e reposição de escala docente
17/10 - Sábado letivo especial de reposição pedagógica

As escalas de professores de cada área serão divulgadas na sexta-feira anterior no portal acadêmico."""

    # Caso 8 (Proeja): Alteração de disciplinas e professores
    mut_proeja_disciplinas = orig_proeja.replace("Química — Max Wagno", "Introdução à Inteligência Artificial — Antigravity") \
                                          .replace("Administração da Produção — Alan", "Banco de Dados NoSQL — Marcus") \
                                          .replace("Matemática — Ivan", "Desenvolvimento Web com React — Luan") \
                                          .replace("Língua Portuguesa — Ella Bispo", "Ética e Filosofia da Tecnologia — Simone")

    # Caso 9 (Escala): Alteração de docentes na escala
    mut_escala_docentes = orig_escala.replace("Mikaelle, Aderlange, Caio, Carola, Clenilson, Cristiano, Francílio, Ivan, Hyane, Marcos Ramon, Nelson Costa, Ronan, Tamires, Wanderson Leonardo, Wanderson Vasconcelos", 
                                             "Antigravity, Beatrice, Roberto, Luan, Simone, Marcus, Jonas, Ana Clara, Samuel, Carlos, Maria, Clara, Fernando, Julia, Ricardo") \
                                     .replace("Mikaelle, Alan, Brito, Egmar, Emanuela, Jane (subs), Jadiel, Jeferson, Lidiane, Marcelo Viana, Paula, Raul, Sekeff, Teresa, Wanderson Carvalho",
                                             "Antigravity, Roberto, Bruno, Carla, Daniel, Elaine, Fabio, Gabriel, Helena, Igor, Julia, Katia, Leonardo, Mariana, Otavio") \
                                     .replace("Nelson, Ella Bispo, Marcos Vinicius, Fransuel, Glairton, Luciana, Raquelle, Jeferson, Jonathas, Marcelo Batista, Poena, Francisco, Reis, Rodrigo Amaral, Wanderson Vasconcelos",
                                             "Sonia, Thiago, Vanessa, Walter, Xavier, Yara, Zeca, Arthur, Bianca, Caio, Daniel, Eduarda, Felipe, Gustavo, Henrique") \
                                     .replace("Mayllon, Alberto, Ariane, Benedito, Fernandes, Marcelo Viana, Marcos Ramon, Pablo Dias, Raul, Renata, Ronan, Sérgio, Viana, Wanderson Carvalho",
                                             "Irene, Joao, Kleber, Larissa, Murilo, Natalia, Olivia, Patricia, Quiteria, Reginaldo, Sebastiao, Tatiana, Uelinton, Valter")

    # Caso 10 (Vestuario): Alteração de disciplinas de costura/modelagem
    mut_vestuario_disciplinas = orig_vestuario.replace("História, Cultura e Moda — Luciana", "História da Moda e Estilo Contemporâneo — Luciana") \
                                              .replace("Segurança do Trabalho — Marcelo Viana", "Ergonomia e Higiene no Trabalho — Marcelo Viana") \
                                              .replace("Desenho Técnico — Aderlange", "Desenho Técnico Assistido por Computador — Aderlange") \
                                              .replace("Materiais e Beneficiamentos Têxteis — Hyane", "Química Têxtil e Fibras Sustentáveis — Hyane") \
                                              .replace("Moda e Criatividade — Hyane", "Processos Criativos e Economia Circular — Hyane")

    # Caso 11 (Informatica): Alteração de professores e disciplinas de informática
    mut_informatica_disciplinas = orig_informatica.replace("Infraestrutura Comp. e Suporte Técnico — Marcos Ramon", "Arquitetura de Computadores e Sistemas Operacionais — Antigravity") \
                                                  .replace("Desenvolvimento Web Front-End — Wanderson Leonardo", "Aplicações SPA com React e Vue — Wanderson Leonardo") \
                                                  .replace("Fundamentos de Redes e Internet — Marcos Ramon", "Redes de Computadores e Segurança de Sistemas — Antigravity") \
                                                  .replace("Algoritmos e Lógica de Programação — Mayllon", "Estruturas de Dados e Resolução de Problemas — Mayllon") \
                                                  .replace("Fundamentos da Informática e Aplicações — Jonathas", "Introdução à Computação Científica — Jonathas") \
                                                  .replace("Química — Brito", "Química Tecnológica — Brito") \
                                                  .replace("Educação Física — Fernandes", "Práticas Esportivas e Saúde — Fernandes") \
                                                  .replace("Geografia — Nelson Monte", "Geografia Humana e Econômica — Nelson Monte")

    # Caso 12 (Matematica): Substituição completa do assunto (Outro Tema)
    mut_matematica_deep = "Regulamento interno de conduta estudantil do IFPI Campus Piripiri. " \
                          "Fica estabelecido que o uso de aparelhos celulares em sala de aula é permitido apenas " \
                          "para fins pedagógicos autorizados. O descumprimento acarretará em advertência verbal."

    # MUTAÇÕES ESTRUTURAIS (Variação de Chunks - 6 casos)
    # Caso 13 (Sabados): Redução drástica de chunks (apenas a introdução)
    mut_sabados_reduzido = "\n".join(orig_sabados.split("\n")[:3])

    # Caso 14 (Proeja): Aumento drástico de chunks (repetição do texto 6 vezes)
    mut_proeja_aumentado = orig_proeja * 6

    # Caso 15 (Escala): Adição de novas seções (aumentando a quantidade de chunks)
    mut_escala_adicao = orig_escala + "\n\n" + """
ESCALA DOCENTE COMPLEMENTAR - NOVOS SÁBADOS
14/11 - Prof. Carlos (Física)
21/11 - Profª. Maria (Geografia)
28/11 - Prof. Roberto (História)
05/12 - Profª. Clara (Sociologia)
12/12 - Prof. Fernando (Filosofia)
"""

    # Caso 16 (Vestuario): Redução drástica de chunks
    mut_vestuario_reduzido = "\n".join(orig_vestuario.split("\n")[:10])

    # Caso 17 (Informatica): Aumento drástico de chunks
    mut_informatica_aumentado = orig_informatica * 5

    # Caso 18 (Matematica): Adição de novas seções
    mut_matematica_adicao = orig_matematica + "\n\n" + """
CÁLCULO NUMÉRICO E ÁLGEBRA LINEAR - TURMA C
Segunda-feira - 14:00 - Prof. Jonas
Quarta-feira - 16:00 - Profª. Ana Clara
Sexta-feira - 10:00 - Prof. Samuel
"""

    cases = [
        # === CATEGORIA 1: DOCUMENTOS INALTERADOS (6 casos) ===
        {
            "id": 1,
            "categoria": "Documentos Inalterados",
            "documento": "Informações Sábados Letivos",
            "original_proc": proc_sabados_orig,
            "filename": name_sabados,
            "new_content": orig_sabados,
            "fontes": None,
            "exp_status": "INALTERADA",
            "exp_acao": "MANTER",
            "alteracao": "Nenhuma (mesmo conteúdo)"
        },
        {
            "id": 2,
            "categoria": "Documentos Inalterados",
            "documento": "Horários PROEJA ADM",
            "original_proc": proc_proeja_orig,
            "filename": name_proeja,
            "new_content": orig_proeja,
            "fontes": None,
            "exp_status": "INALTERADA",
            "exp_acao": "MANTER",
            "alteracao": "Nenhuma (mesmo conteúdo)"
        },
        {
            "id": 3,
            "categoria": "Documentos Inalterados",
            "documento": "Escala Docente Sábados",
            "original_proc": proc_escala_orig,
            "filename": name_escala,
            "new_content": orig_escala,
            "fontes": None,
            "exp_status": "INALTERADA",
            "exp_acao": "MANTER",
            "alteracao": "Nenhuma (mesmo conteúdo)"
        },
        {
            "id": 4,
            "categoria": "Documentos Inalterados",
            "documento": "Horários Vestuário",
            "original_proc": proc_vestuario_orig,
            "filename": name_vestuario,
            "new_content": orig_vestuario,
            "fontes": None,
            "exp_status": "INALTERADA",
            "exp_acao": "MANTER",
            "alteracao": "Nenhuma (mesmo conteúdo)"
        },
        {
            "id": 5,
            "categoria": "Documentos Inalterados",
            "documento": "Horários Informática",
            "original_proc": proc_informatica_orig,
            "filename": name_informatica,
            "new_content": orig_informatica,
            "fontes": None,
            "exp_status": "INALTERADA",
            "exp_acao": "MANTER",
            "alteracao": "Nenhuma (mesmo conteúdo)"
        },
        {
            "id": 6,
            "categoria": "Documentos Inalterados",
            "documento": "Horários Matemática",
            "original_proc": proc_matematica_orig,
            "filename": name_matematica,
            "new_content": orig_matematica,
            "fontes": None,
            "exp_status": "INALTERADA",
            "exp_acao": "MANTER",
            "alteracao": "Nenhuma (mesmo conteúdo)"
        },

        # === CATEGORIA 2: ALTERAÇÕES DE CONTEÚDO (6 casos) ===
        {
            "id": 7,
            "categoria": "Alterações de Conteúdo",
            "documento": "Informações Sábados Letivos",
            "original_proc": proc_sabados_orig,
            "filename": name_sabados,
            "new_content": mut_sabados_datas,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Reestruturação completa de cronograma e datas"
        },
        {
            "id": 8,
            "categoria": "Alterações de Conteúdo",
            "documento": "Horários PROEJA ADM",
            "original_proc": proc_proeja_orig,
            "filename": name_proeja,
            "new_content": mut_proeja_disciplinas,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Substituição de disciplinas e professores"
        },
        {
            "id": 9,
            "categoria": "Alterações de Conteúdo",
            "documento": "Escala Docente Sábados",
            "original_proc": proc_escala_orig,
            "filename": name_escala,
            "new_content": mut_escala_docentes,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Alteração de docentes na escala de reposição"
        },
        {
            "id": 10,
            "categoria": "Alterações de Conteúdo",
            "documento": "Horários Vestuário",
            "original_proc": proc_vestuario_orig,
            "filename": name_vestuario,
            "new_content": mut_vestuario_disciplinas,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Substituição de disciplinas técnicas e horários"
        },
        {
            "id": 11,
            "categoria": "Alterações de Conteúdo",
            "documento": "Horários Informática",
            "original_proc": proc_informatica_orig,
            "filename": name_informatica,
            "new_content": mut_informatica_disciplinas,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Substituição de disciplinas da área técnica de TI"
        },
        {
            "id": 12,
            "categoria": "Alterações de Conteúdo",
            "documento": "Horários Matemática",
            "original_proc": proc_matematica_orig,
            "filename": name_matematica,
            "new_content": mut_matematica_deep,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Substituição profunda do assunto (Regulamento de TI)"
        },

        # === CATEGORIA 3: MUDANÇAS ESTRUTURAIS (6 casos) ===
        {
            "id": 13,
            "categoria": "Mudanças Estruturais",
            "documento": "Informações Sábados Letivos",
            "original_proc": proc_sabados_orig,
            "filename": name_sabados,
            "new_content": mut_sabados_reduzido,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Redução drástica (corte de 90% das linhas)"
        },
        {
            "id": 14,
            "categoria": "Mudanças Estruturais",
            "documento": "Horários PROEJA ADM",
            "original_proc": proc_proeja_orig,
            "filename": name_proeja,
            "new_content": mut_proeja_aumentado,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Aumento drástico por repetição (6x)"
        },
        {
            "id": 15,
            "categoria": "Mudanças Estruturais",
            "documento": "Escala Docente Sábados",
            "original_proc": proc_escala_orig,
            "filename": name_escala,
            "new_content": mut_escala_adicao,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Adição de seção completa de escala docente"
        },
        {
            "id": 16,
            "categoria": "Mudanças Estruturais",
            "documento": "Horários Vestuário",
            "original_proc": proc_vestuario_orig,
            "filename": name_vestuario,
            "new_content": mut_vestuario_reduzido,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Redução drástica do arquivo de vestuário"
        },
        {
            "id": 17,
            "categoria": "Mudanças Estruturais",
            "documento": "Horários Informática",
            "original_proc": proc_informatica_orig,
            "filename": name_informatica,
            "new_content": mut_informatica_aumentado,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Aumento drástico por repetição (5x)"
        },
        {
            "id": 18,
            "categoria": "Mudanças Estruturais",
            "documento": "Horários Matemática",
            "original_proc": proc_matematica_orig,
            "filename": name_matematica,
            "new_content": mut_matematica_adicao,
            "fontes": None,
            "exp_status": "ATUALIZADA",
            "exp_acao": "ATUALIZAR",
            "alteracao": "Adição de seção de horários para Turma C"
        },

        # === CATEGORIA 4: DOCUMENTOS OBSOLETOS (6 casos) ===
        {
            "id": 19,
            "categoria": "Documentos Obsoletos",
            "documento": "Informações Sábados Letivos",
            "original_proc": proc_sabados_orig,
            "filename": name_sabados,
            "new_content": orig_sabados,
            "fontes": [{"url": f"file:///apps/uploads/{name_sabados}", "status": "INVALIDO", "http_status": 200}],
            "exp_status": "OBSOLETA",
            "exp_acao": "SINALIZAR_OBSOLESCENCIA",
            "alteracao": "Sinalização de fonte INVÁLIDA"
        },
        {
            "id": 20,
            "categoria": "Documentos Obsoletos",
            "documento": "Horários PROEJA ADM",
            "original_proc": proc_proeja_orig,
            "filename": name_proeja,
            "new_content": orig_proeja,
            "fontes": [{"url": f"file:///apps/uploads/{name_proeja}", "status": "VALIDO", "http_status": 404}],
            "exp_status": "OBSOLETA",
            "exp_acao": "SINALIZAR_OBSOLESCENCIA",
            "alteracao": "Indisponibilidade da fonte (HTTP 404)"
        },
        {
            "id": 21,
            "categoria": "Documentos Obsoletos",
            "documento": "Escala Docente Sábados",
            "original_proc": proc_escala_orig,
            "filename": name_escala,
            "new_content": orig_escala,
            "fontes": [{"url": f"file:///apps/uploads/{name_escala}", "status": "VALIDO", "http_status": 500}],
            "exp_status": "OBSOLETA",
            "exp_acao": "SINALIZAR_OBSOLESCENCIA",
            "alteracao": "Erro de servidor na fonte (HTTP 500)"
        },
        {
            "id": 22,
            "categoria": "Documentos Obsoletos",
            "documento": "Horários Vestuário",
            "original_proc": proc_vestuario_orig,
            "filename": name_vestuario,
            "new_content": orig_vestuario,
            "fontes": [{"url": f"file:///apps/uploads/{name_vestuario}", "status": "INVALIDO", "http_status": 200}],
            "exp_status": "OBSOLETA",
            "exp_acao": "SINALIZAR_OBSOLESCENCIA",
            "alteracao": "Sinalização de fonte INVÁLIDA"
        },
        {
            "id": 23,
            "categoria": "Documentos Obsoletos",
            "documento": "Horários Informática",
            "original_proc": proc_informatica_orig,
            "filename": name_informatica,
            "new_content": orig_informatica,
            "fontes": [{"url": f"file:///apps/uploads/{name_informatica}", "status": "VALIDO", "http_status": 404}],
            "exp_status": "OBSOLETA",
            "exp_acao": "SINALIZAR_OBSOLESCENCIA",
            "alteracao": "Indisponibilidade da fonte (HTTP 404)"
        },
        {
            "id": 24,
            "categoria": "Documentos Obsoletos",
            "documento": "Horários Matemática",
            "original_proc": proc_matematica_orig,
            "filename": name_matematica,
            "new_content": orig_matematica,
            "fontes": [{"url": f"file:///apps/uploads/{name_matematica}", "status": "VALIDO", "http_status": 500}],
            "exp_status": "OBSOLETA",
            "exp_acao": "SINALIZAR_OBSOLESCENCIA",
            "alteracao": "Erro de servidor na fonte (HTTP 500)"
        },
    ]

    total_casos = len(cases)
    acertos = 0
    erros = 0

    stats_categoria = {}
    classes = ["INALTERADA", "ATUALIZADA", "OBSOLETA"]
    confusion_matrix = {real: {pred: 0 for pred in classes} for real in classes}

    print("\n" + "=" * 105)
    print(f"{'ID':<3} | {'Documento Real':<28} | {'Categoria':<23} | {'Sim.':<6} | {'Chunks':<6} | {'Esperado':<11} | {'Obtido':<11} | {'Status':<7}")
    print("=" * 105)

    for c in cases:
        # Gera o processamento atualizado (embeddings e chunks reais)
        updated_proc = run_real_pipeline(c["filename"], c["new_content"], c["documento"], c["fontes"])
        
        # Recupera embeddings antigos e novos
        emb_old = [chunk["embedding"] for chunk in c["original_proc"]["chunks"]]
        emb_new = [chunk["embedding"] for chunk in updated_proc["chunks"]]
        
        # Constrói fontes caso não seja especificado
        fontes_caso = c["fontes"]
        if fontes_caso is None:
            fontes_caso = [{"url": f"file:///apps/uploads/{c['filename']}", "status": "VALIDO", "http_status": 200}]
            
        dados_revisao = {
            "id_crenca": f"doc_teste_real_{c['id']}",
            "texto_crenca": c["documento"],
            "documentos_fonte": fontes_caso,
            "embeddings_anteriores": emb_old,
            "embeddings_atualizados": emb_new,
            "chunks_novos": updated_proc["chunks"],
            "metadados_associados": {"fonte": f"file:///apps/uploads/{c['filename']}"}
        }
        
        # Executa o agente de revisão
        res = revisar_crenca.invoke({"dados_revisao": dados_revisao})
        
        status_obtido = res["status_crenca"]
        acao_obtida = res["acao_recomendada"]
        
        # Similaridade calculada
        if "Similaridade semantica media" in res.get("justificativa_tecnica", "") or "Similaridade media" in res.get("justificativa_tecnica", ""):
            import re
            match = re.search(r"(\d+\.\d+)", res.get("justificativa_tecnica", ""))
            sim_value = float(match.group(1)) if match else 1.0000
        else:
            sim_value = 1.0000 if status_obtido == "INALTERADA" else 0.0000
            
        # Verifica acerto
        is_correct = (status_obtido == c["exp_status"] and acao_obtida == c["exp_acao"])
        resultado_str = "ACERTO" if is_correct else "ERRO"
        
        if is_correct:
            acertos += 1
        else:
            erros += 1
            
        # Matriz de Confusão
        confusion_matrix[c["exp_status"]][status_obtido] += 1
        
        # Estatísticas por Categoria
        cat = c["categoria"]
        if cat not in stats_categoria:
            stats_categoria[cat] = {"casos": 0, "acertos": 0, "erros": 0}
        stats_categoria[cat]["casos"] += 1
        if is_correct:
            stats_categoria[cat]["acertos"] += 1
        else:
            stats_categoria[cat]["erros"] += 1
            
        chunks_str = f"{len(emb_old)}->{len(emb_new)}"
        print(f"{c['id']:<3} | {c['documento'][:28]:<28} | {c['categoria']:<23} | {sim_value:<6.4f} | {chunks_str:<6} | {c['exp_status']:<11} | {status_obtido:<11} | {resultado_str:<7}")

    print("=" * 105)
    print("\n" + "=" * 60)
    print("MÉTRICAS CONSOLIDADAS (DOCUMENTOS REAIS)")
    print("=" * 60)
    
    acuracia_global = acertos / total_casos
    print(f"Total de Casos: {total_casos}")
    print(f"Total de Acertos: {acertos}")
    print(f"Acurácia Global: {acuracia_global * 100:.2f}%")
    
    print("\nDesempenho por Categoria:")
    print(f"{'Categoria':<25} | {'Casos':<6} | {'Acertos':<8} | {'Erros':<6} | {'Taxa de Acerto':<8}")
    print("-" * 65)
    for cat, info in stats_categoria.items():
        acc = info["acertos"] / info["casos"]
        print(f"{cat:<25} | {info['casos']:<6} | {info['acertos']:<8} | {info['erros']:<6} | {acc * 100:.2f}%")

    print("\nMatriz de Classificação (Confusão) - Status:")
    print(f"{'Real / Previsto':<16} | {'INALTERADA':<10} | {'ATUALIZADA':<10} | {'OBSOLETA':<10}")
    print("-" * 55)
    for real in classes:
        print(f"{real:<16} | {confusion_matrix[real]['INALTERADA']:<10} | {confusion_matrix[real]['ATUALIZADA']:<10} | {confusion_matrix[real]['OBSOLETA']:<10}")
        
    print("\nValidação com documentos reais concluída!")
    
    # Assert final para regressão
    assert erros == 0, f"Falha na validação com documentos reais: {erros} erros detectados!"

if __name__ == "__main__":
    run_real_battery()
