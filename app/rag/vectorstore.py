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
_dim = None

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
    global _client, _dim

    dense = get_embeddings()
    sparse = get_sparse_embeddings()
    if _dim is None:
        _dim = len(dense.embed_query("dim probe"))
    dim = _dim

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
    
    

# The short answer is: create_collection is defining a Database Table Schema (Columns), NOT running Python code.

# Think of it like creating a SQL Database Table 🗄️

# When you create a table in SQL, you write:

# CREATE TABLE users (
#     age INT,
#     name VARCHAR(100)
# );

# In SQL, you are defining the column names (age, name) and their data types (INT, VARCHAR).

# Inside _client.create_collection(), we are doing the exact same thing for Qdrant!

# 1. What does this code actually mean?

# vectors_config={
#     "dense": VectorParams(size=dim, distance=Distance.COSINE),
# },
# sparse_vectors_config={
#     "sparse": SparseVectorParams(),
# },

# You are telling the Qdrant database engine:

# "Hey Qdrant, create a table with two vector columns:

# Column 1 name: "dense". Every vector stored here must have 384 numbers (size=dim), and compare them using Cosine distance.
# Column 2 name: "sparse". This column will store keyword frequency numbers (BM25 sparse vectors)."*
# "dense" and "sparse" in quotes are just the column names inside Qdrant! (You could have named them "column_a" and "column_b" if you wanted).

# 2. Why can't we just pass dense=dense and sparse=sparse here?

# Because dense = get_embeddings() is a Python Neural Network object (HuggingFaceEmbeddings).

# The Qdrant database (written in Rust/C++) knows nothing about Python neural networks.
# A database only stores raw numbers. It cannot store a Python machine learning model inside its table definition!
# When creating a table, Qdrant only needs to know:
# What is the column name? ("dense")
# How many numbers per vector? (size=384)
# What math metric? (Distance.COSINE)
# 3. Where DO we connect dense and sparse? Look at lines 73–81!

# Right after creating the table, look at the return statement:

# return QdrantVectorStore(
#     client=_client,
#     collection_name=COLLECTION_NAME,
#     embedding=dense,              # 👈 HERE is your Python dense model!
#     sparse_embedding=sparse,      # 👈 HERE is your Python sparse model!
#     retrieval_mode=RetrievalMode.HYBRID,
#     vector_name="dense",          # 👈 Tells LangChain: save dense numbers into the "dense" column!
#     sparse_vector_name="sparse",  # 👈 Tells LangChain: save sparse numbers into the "sparse" column!
# )


# The Big Picture Connection:

# Python Machine Learning Models                Qdrant Database Columns
# ┌─────────────────────────────┐               ┌───────────────────────┐
# │ dense = get_embeddings()   │ ──(generates)─►│ Column: "dense"       │
# │                             │               │ (size=384, COSINE)    │
# ├─────────────────────────────┤               ├───────────────────────┤
# │ sparse = get_sparse...()    │ ──(generates)─►│ Column: "sparse"      │
# │                             │               │ (BM25 keywords)       │
# └─────────────────────────────┘               └───────────────────────┘
# create_collection: Creates the empty storage columns named "dense" and "sparse" inside Qdrant.
# QdrantVectorStore: Takes your Python models (dense and sparse), converts the text into numbers, and deposits those numbers into the matching "dense" and "sparse" columns!
   
   
   