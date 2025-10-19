import os
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent
from apps.core.llm_config import get_llm
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

llm = get_llm()
tavily_api_key = os.getenv("TAVILY_API_KEY")
tools = []

if tavily_api_key:
    tavily_tool = TavilySearch(max_results=2, tavily_api_key=tavily_api_key)
    tools = [tavily_tool]
else:
    try:

        @tool
        def disabled_search(query: str) -> str:
            return "Web search disabled: missing TAVILY_API_KEY."

        tools = [disabled_search]
    except Exception:
        tools = []
tavily_agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt="You perform web searches",
    name="tavily_agent"
)
tavily_agent.llm = llm  # usado pelo supervisor
