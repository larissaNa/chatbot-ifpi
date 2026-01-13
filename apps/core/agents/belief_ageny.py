# import re
# from langchain_core.tools import tool
# from ..config import scheduler, active_jobs
# from datetime import datetime, timedelta
# import uuid


# @tool
# def revisar_crenca(chroma, novo_doc, novo_embedding, metadata):
#     doc_id = metadata["doc_id"]

#     # Buscar se já existe este documento
#     docs_existentes = chroma.get(where={"doc_id": doc_id})
#     if docs_existentes:
#         versao_antiga = docs_existentes['metadatas'][0]['version']
#         if versao_antiga != metadata['version']:
#             chroma.delete(where={"doc_id": doc_id})
#             chroma.add(documents=[novo_doc], embeddings=[novo_embedding], metadatas=[metadata])
#             print(f"Documento {doc_id} atualizado da versão {versao_antiga} → {metadata['version']}")
#         else:
#             print(f"Nenhuma atualização detectada para {doc_id}.")
#     else:
#         chroma.add(documents=[novo_doc], embeddings=[novo_embedding], metadatas=[metadata])
#         print(f"Novo documento {doc_id} adicionado.")



# def agendar_revisao(chroma, doc_id, intervalo_horas, obter_novo_conteudo_func):
#     job_id = str(uuid.uuid4())

#     def tarefa_revisao():
#         novo_doc, novo_embedding, metadata = obter_novo_conteudo_func(doc_id)
#         revisar_crenca(chroma, novo_doc, novo_embedding, metadata)

#     job = scheduler.add_job(
#         tarefa_revisao,
#         'interval',
#         hours=intervalo_horas,
#         id=job_id,
#         next_run_time=datetime.now() + timedelta(seconds=10)  # primeira execução em 10 segundos
#     )

#     active_jobs[job_id] = job
#     print(f"Revisão agendada para o documento {doc_id} a cada {intervalo_horas} horas. Job ID: {job_id}")
#     return job_id


