import os
from pathlib import Path
from django.conf import settings
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# Define where to store the indexes
VECTOR_STORE_DIR = getattr(settings, "VECTOR_STORE_DIR", settings.BASE_DIR / "agent_knowledge_base")

def get_agent_index_path(agent_id: str) -> str:
    """Returns the path to the agent's FAISS index directory."""
    path = VECTOR_STORE_DIR / str(agent_id)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)

def rebuild_agent_index(agent_id: str, texts: list[str], metadatas: list[dict] = None) -> None:
    """
    Rebuilds the FAISS index for a specific agent from scratch.
    """
    if not texts:
        return

    embeddings = OpenAIEmbeddings()
    vector_store = FAISS.from_texts(texts, embeddings, metadatas=metadatas)
    
    # Save local
    path = get_agent_index_path(agent_id)
    vector_store.save_local(path)
    print(f"Index rebuilt for agent {agent_id} at {path}")

def search_agent_index(agent_id: str, query: str, k: int = 4):
    """
    Searches the agent's FAISS index.
    Returns a list of documents.
    """
    path = get_agent_index_path(agent_id)
    if not os.path.exists(os.path.join(path, "index.faiss")):
        return []

    embeddings = OpenAIEmbeddings()
    # allow_dangerous_deserialization is needed for loading local pickles
    # Since we created them, it is safe.
    vector_store = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
    
    return vector_store.similarity_search(query, k=k)
