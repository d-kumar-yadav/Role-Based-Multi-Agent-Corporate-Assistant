import os
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_core.embeddings.fake import FakeEmbeddings
from dotenv import load_dotenv

load_dotenv()

import threading

QDRANT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_db")

_lock = threading.Lock()
_embeddings = None
_client = None

def get_embeddings():
    global _embeddings
    with _lock:
        if _embeddings is None:
            # We use SpacyEmbeddings with the 'en_core_web_lg' model we downloaded via GitHub in the Dockerfile!
            # This generates REAL semantic embeddings (size 300) without ever contacting HuggingFace!
            from langchain_community.embeddings.spacy_embeddings import SpacyEmbeddings
            _embeddings = SpacyEmbeddings(model_name="en_core_web_lg")
    return _embeddings

def get_vectorstore():
    global _client
    with _lock:
        if _client is None:
            _client = QdrantClient(path=QDRANT_PATH)
            
            # Ensure the collection exists before LangChain tries to wrap it!
            from qdrant_client.http.models import Distance, VectorParams
            if not _client.collection_exists("enterprise_docs"):
                _client.create_collection(
                    collection_name="enterprise_docs",
                    vectors_config=VectorParams(size=300, distance=Distance.COSINE)
                )
    
    # Wrap it in LangChain's QdrantVectorStore
    return QdrantVectorStore(
        client=_client,
        collection_name="enterprise_docs",
        embedding=get_embeddings()
    )




#  The Core Purpose
# ChromaDB was built specifically to be the absolute easiest database for AI developers to use on their laptops. It is incredibly popular for prototyping, hackathons, and small projects because you don't need to run a server—it just saves data to a local folder (like we were doing).
# Qdrant was built for heavy-duty, enterprise production. If you have 50 million documents and 10,000 users querying the database at the exact same time, Qdrant handles it effortlessly.

# 2. Under the Hood (Performance)
# ChromaDB is written in Python and TypeScript. It is fast enough for small projects, but it can struggle with complex metadata filtering on massive datasets.
# Qdrant is written entirely in Rust. Because it is written in Rust, it is blazingly fast and uses very little RAM. It is widely considered one of the most performant vector databases on the market today.

# 3. Metadata Filtering (Our Access Control!)
# ChromaDB has basic filtering. It gets the job done, but it isn't its strongest feature.
# Qdrant has a highly advanced "Payload Filtering" engine. When we set up our Role-Based Access Control (saying "Only show IT documents or Public documents"), Qdrant processes that logic significantly faster than Chroma, especially when you have millions of document chunks to sort through.