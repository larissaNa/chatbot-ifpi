from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent
from apps.reports.llm_config import get_llm

llm = get_llm()
tavily_tool = TavilySearch(max_results=2)
tavily_agent = create_react_agent(
    model=llm,
    tools=[tavily_tool],
    prompt="You perform web searches",
    name="tavily_agent"
)
tavily_agent.llm = llm  # usado pelo supervisor
