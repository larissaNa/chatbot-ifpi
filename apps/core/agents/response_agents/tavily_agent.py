import os
from langchain_tavily import TavilySearch
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

tavily_api_key = os.getenv("TAVILY_API_KEY")

if tavily_api_key:
    tavily_tool = TavilySearch(max_results=2, tavily_api_key=tavily_api_key)
    tools = [tavily_tool]
else:
    @tool
    def disabled_search(query: str) -> str:
        """Search tool disabled because API key is missing."""
        return "Web search disabled: missing TAVILY_API_KEY."
    
    tavily_tool = disabled_search
    tools = [tavily_tool]
