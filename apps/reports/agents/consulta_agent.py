from langchain.chains import RetrievalQA
from langchain.tools import Tool
from apps.reports.llm_config import get_llm
from apps.reports.services.vectorstore_service import get_vectorstore

llm = get_llm()
vectorstore = get_vectorstore()
retriever = vectorstore.as_retriever(search_kwargs={"k": 6})

qa = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)

consulta_tool = Tool(
    name="consulta_institucional",
    func=lambda q: qa.invoke(q)["result"],
    description="Responde perguntas com base nos documentos internos do IFPI."
)

from langgraph.prebuilt import create_react_agent
consulta_agent = create_react_agent(
    model=llm,
    tools=[consulta_tool],
    prompt="You respond only based on internal IFPI documents.",
    name="consulta_institucional"
)
consulta_agent.llm = llm
