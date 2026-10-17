import os
import threading
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import (
    QdrantVectorStore, FastEmbedSparse, RetrievalMode,
)
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance, VectorParams, SparseVectorParams,
)

load_dotenv()

_lock = threading.Lock()
_embeddings = None
_sparse = None
_client = None

COLLECTION_NAME = "enterprise_docs"


def get_embeddings():
    global _embeddings
    with _lock:
        if _embeddings is None:
            _embeddings = HuggingFaceEmbeddings(
                model_name="BAAI/bge-small-en-v1.5",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
    return _embeddings


def get_sparse_embeddings():
    global _sparse
    with _lock:
        if _sparse is None:
            _sparse = FastEmbedSparse(model_name="Qdrant/bm25")
    return _sparse


def get_vectorstore():
    global _client

    dense = get_embeddings()
    sparse = get_sparse_embeddings()
    dim = len(dense.embed_query("dim probe"))

    with _lock:
        if _client is None:
            qdrant_url = os.getenv("QDRANT_URL")
            if qdrant_url:
                _client = QdrantClient(url=qdrant_url, timeout=10)
            else:
                path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "qdrant_db",
                )
                _client = QdrantClient(path=path)

        if not _client.collection_exists(COLLECTION_NAME):
            _client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={
                    "dense": VectorParams(size=dim, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(),
                },
            )

    return QdrantVectorStore(
        client=_client,
        collection_name=COLLECTION_NAME,
        embedding=dense,
        sparse_embedding=sparse,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",
    )