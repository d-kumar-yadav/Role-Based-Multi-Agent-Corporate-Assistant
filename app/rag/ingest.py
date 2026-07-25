import os
import copy
import shutil
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .vectorstore import get_vectorstore

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
# DOCS_DIR - "d:\Project_2_AI\ai-firewall\app\rag\documents"

def determine_roles_from_folder(folder_name: str) -> list[str]:
    """Determine which roles should have retrieval access based on the directory name."""
    folder_lower = folder_name.lower()
    
    
    if folder_lower in ["hr", "finance", "it", "public"]:
        return [folder_lower]
        
    #  for Cross-domain folders
    if folder_lower.startswith("crossdomain_"):
        roles = []
        if "it" in folder_lower: roles.append("it")
        if "finance" in folder_lower: roles.append("finance")
        if "hr" in folder_lower: roles.append("hr")
        return roles if roles else ["public"]
    
    # Fallback to public for safety (Fail Open for visibility)
    return ["public"]

def ingest_documents(reset: bool = True):
    """Load, chunk, tag, and store all PDFs by iterating through role folders."""
    
    vectorstore = get_vectorstore()
    
    if reset:
        # Proper way to reset Qdrant without locking the database twice!
        # We reuse the client that vectorstore already initialized.
        client = vectorstore.client
        if client.collection_exists("enterprise_docs"):
            client.delete_collection("enterprise_docs")
            # Recreate with 300 dimensions for Spacy
            from qdrant_client.http.models import Distance, VectorParams
            client.create_collection(
                collection_name="enterprise_docs",
                vectors_config=VectorParams(size=300, distance=Distance.COSINE)
            )
            print("Successfully dropped and recreated Qdrant collection for Spacy!")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    all_chunks = []
    
    if not os.path.exists(DOCS_DIR):
        print(f"Documents directory {DOCS_DIR} does not exist.")
        return

    role_counts: dict[str, int] = {}

   
    for root, dirs, files in os.walk(DOCS_DIR):
    
        folder_name = os.path.basename(root)
        # root- /dcumnets/finance
        
        # Determine roles based on folder name
        if root == DOCS_DIR:
            roles = ["public"] # Any files left in the root directory default to public
        else:
            roles = determine_roles_from_folder(folder_name)

        for filename in sorted(files):
            if not filename.endswith(".pdf"):
                continue
                
            file_path = os.path.join(root, filename)
            
            try:
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                chunks = text_splitter.split_documents(docs)
                
                for chunk in chunks:
                    for role in roles:
                        chunk_copy = copy.deepcopy(chunk)
                        # "Do not reuse the original object. Build me a 100%, physically distinct clone of this object in a new area of the computer's memory."
                        # if we donot use deepcopy  Python re-uses the exact same object in memory, changing the label the second time accidentally overwrites the label from the first time! When you look in the all_chunks bucket at the end, you would see two identical chunks, and both of them would be labeled "finance". The "it" label completely vanished.
                        chunk_copy.metadata["role"] = role
                        chunk_copy.metadata["source_file"] = filename
                        chunk_copy.metadata["source_folder"] = folder_name
                        all_chunks.append(chunk_copy)
                        role_counts[role] = role_counts.get(role, 0) + 1
                        
                print(f"Loaded [{folder_name}] {filename} -> {len(chunks)} chunks, mapped to roles: {roles}")
            except Exception as e:
                print(f"Failed to load {file_path}: {e}")
                
    if all_chunks:
        vectorstore.add_documents(all_chunks)
        print(f"\nSuccessfully ingested {len(all_chunks)} total document chunks into ChromaDB.")
        print("Chunk count by role tag:")
        for role, count in sorted(role_counts.items()):
            print(f"  {role}: {count}")
    else:
        print("No documents found to ingest.")

if __name__ == "__main__":
    ingest_documents(reset=True)