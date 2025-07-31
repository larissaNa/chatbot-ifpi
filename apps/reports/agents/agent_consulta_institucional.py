from langchain.chains import RetrievalQA
from langchain.tools import Tool

def create_consulta_institucional_agent(llm, retriever):
    institucional_qa = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True
    )

    return Tool(
        name="consulta_institucional",
        func=lambda q: institucional_qa.invoke(q)["result"],
        description="Use esta ferramenta para responder perguntas sobre normativas, diretrizes, artigos ou documentos do IFPI."
    )
