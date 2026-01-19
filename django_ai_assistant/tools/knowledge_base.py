from typing import Optional, Type

from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool
from django_ai_assistant.vector_store import search_agent_index

class KnowledgeBaseInput(BaseModel):
    query: str = Field(description="The query to search the knowledge base for.")

class KnowledgeBaseTool(BaseTool):
    name: str = "search_knowledge_base"
    description: str = (
        "Useful for answering questions based on the agent's specific knowledge base "
        "(FAQs, Articles, etc.). Use this tool when the user asks something technical "
        "or specific to the domain."
    )
    args_schema: Type[BaseModel] = KnowledgeBaseInput
    agent_id: str

    def _run(self, query: str) -> str:
        docs = search_agent_index(self.agent_id, query)
        if not docs:
            return "No relevant information found in the knowledge base."
        
        results = []
        for i, doc in enumerate(docs):
            results.append(f"Result {i+1}: {doc.page_content}")
        
        return "\n\n".join(results)
