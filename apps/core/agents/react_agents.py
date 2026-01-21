from langgraph.prebuilt import create_react_agent
from apps.core.agents.response_agents.tavily_agent import tavily_tool
from apps.core.agents.response_agents.consulta_agent import consulta_tool
from apps.core.llm_config import get_llm
from apps.core.agents.link_analysis_agent import buscar_documentos_oficiais, analisar_link
from apps.core.agents.extraction_agent import extrair_conteudo
from apps.core.agents.processing_agent import processar_conteudo
from apps.core.agents.belief_revision_agent import revisar_crenca

llm = get_llm()

tavily_agent = create_react_agent(
    model=llm,
    tools=[tavily_tool] if "tavily_tool" in globals() else [],
    prompt="You perform web searches",
    name="tavily_agent"
)
tavily_agent.llm = llm


consulta_agent = create_react_agent(
    model=llm,
    tools=[consulta_tool],
    prompt="You respond only based on internal IFPI documents.",
    name="consulta_institucional"
)
consulta_agent.llm = llm


search_agent = create_react_agent(
    model=llm,
    tools=[buscar_documentos_oficiais],
    prompt="Você busca documentos oficiais (PDFs) do IFPI e retorna uma lista de URLs.",
    name="search_agent"
)


extraction_agent = create_react_agent(
    model=llm,
    tools=[extrair_conteudo],
    prompt=(
        "Você é um Agente de Extração de Conteúdo. "
        "Recebe o JSON do Agente de Análise de Links, baixa PDFs ou HTML, "
        "extrai e normaliza o texto e retorna exclusivamente o JSON de saída "
        "no formato especificado para o Agente de Processamento."
    ),
    name="extraction_agent"
)


link_analysis_agent = create_react_agent(
    model=llm,
    tools=[analisar_link],
    prompt=(
        "Você é um Agente de Análise de Links institucionais. "
        "Ao receber uma URL, valide, classifique e retorne exclusivamente um JSON "
        "no formato especificado pela arquitetura de Revisão de Crenças."
    ),
    name="link_analysis_agent"
)


processing_agent = create_react_agent(
    model=llm,
    tools=[processar_conteudo],
    prompt=(
        "Você é um Agente de Processamento Semântico. "
        "Recebe o texto extraído e normalizado, realiza chunking semântico, "
        "gera embeddings e metadados, e retorna exclusivamente o JSON pronto para indexação vetorial."
    ),
    name="processing_agent"
)
