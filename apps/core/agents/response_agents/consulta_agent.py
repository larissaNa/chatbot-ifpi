from langchain_core.runnables import RunnableSequence, RunnablePassthrough, RunnableMap
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool
from langchain_core.messages import AIMessage

from apps.core.llm_config import get_llm
from ...prompt import get_llm_prompt, get_qa_prompt
from apps.core.services.utils import setup_vectorstore

# Inicializa LLM e banco vetorial
llm = get_llm()
vectorstore = setup_vectorstore()
retriever = vectorstore.as_retriever(search_kwargs={"k": 6})

# Prompt de QA
llm_prompt = ChatPromptTemplate.from_template(get_qa_prompt())

def format_docs(docs):
    return "\n\n".join([d.page_content for d in docs])

# Cadeia de QA
qa = (
    RunnableMap({
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    })
    | llm_prompt
    | llm
    | StrOutputParser()
)

# Ferramenta de consulta institucional
consulta_tool = Tool(
    name="consulta_institucional",
    func=lambda q: AIMessage(content=qa.invoke(q)),
    description="FONTE DE VERDADE. Responde perguntas baseadas nas crenças e documentos internos. Use para validar fatos, regras e definições antes de buscar externamente."
)

