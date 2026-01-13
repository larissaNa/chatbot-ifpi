from langgraph.prebuilt import create_react_agent
from apps.core.agents.response_agents.tavily_agent import tavily_tool
from apps.core.agents.response_agents.consulta_agent import consulta_tool
from apps.core.llm_config import get_llm
# from apps.core.agents.revision_agent import revisar_crenca
from apps.core.agents.search_agent import buscar_documentos_oficiais
from apps.core.agents.extraction_agent import extrair_texto_pdf

# Inicializa o LLM
llm = get_llm()

tavily_agent = create_react_agent(
    model=llm,
    tools=[tavily_tool] if "tavily_tool" in globals() else [],
    prompt="You perform web searches",
    name="tavily_agent"
)
tavily_agent.llm = llm  # usado pelo supervisor


consulta_agent = create_react_agent(
    model=llm,
    tools=[consulta_tool],
    prompt="You respond only based on internal IFPI documents.",
    name="consulta_institucional"
)
consulta_agent.llm = llm  # usado pelo supervisor

#novos agentes de revisão e busca

search_agent = create_react_agent(
    model=llm,
    tools=[buscar_documentos_oficiais],
    prompt="Você busca documentos oficiais (PDFs) do IFPI e retorna uma lista de URLs.",
    name="search_agent"
)


extraction_agent = create_react_agent(
    model=llm,
    tools=[extrair_texto_pdf],
    prompt="Você extrai texto de PDFs.",
    name="extraction_agent"
)