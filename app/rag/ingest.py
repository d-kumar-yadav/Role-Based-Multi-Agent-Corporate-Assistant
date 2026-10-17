import argparse
import hashlib
import logging
from pathlib import Path
import frontmatter
from langchain_text_splitters import MarkdownHeaderTextSplitter
from .vectorstore import COLLECTION_NAME, get_vectorstore

logger = logging.getLogger("rag.ingest")

POLICIES_DIR = "data/policies"
REQUIRED_FRONTMATTER_KEYS = ["doc_id", "title", "department", "access_level", "roles", "version"]


def parse_and_validate_policy(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        content_bytes = f.read().encode("utf-8")
        post = frontmatter.loads(content_bytes.decode("utf-8"))

    missing_keys = [k for k in REQUIRED_FRONTMATTER_KEYS if k not in post.metadata]
    if missing_keys:
        raise ValueError(f"Missing required frontmatter keys: {missing_keys}")

    roles = post.metadata["roles"]
    if not isinstance(roles, list):
        raise ValueError(f"'roles' must be a list, got {type(roles).__name__}")

    content_hash = hashlib.sha256(content_bytes).hexdigest()
    return post.metadata, post.content, content_hash


def ingest_documents(reset: bool = False, policies_dir: str = POLICIES_DIR):
    if reset:
        vs = get_vectorstore()
        if vs.client.collection_exists(COLLECTION_NAME):
            vs.client.delete_collection(COLLECTION_NAME)
            print(f"Deleted collection '{COLLECTION_NAME}'.")

    vectorstore = get_vectorstore()

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )

    path_obj = Path(policies_dir)
    md_files = sorted(list(path_obj.rglob("*.md")))

    all_chunks = []
    access_level_counts: dict[str, int] = {}
    errors: list[str] = []

    for file_path in md_files:
        try:
            metadata, text, content_hash = parse_and_validate_policy(file_path)
            chunks = splitter.split_text(text)

            for idx, chunk in enumerate(chunks):
                h1 = chunk.metadata.get("h1")
                h2 = chunk.metadata.get("h2")
                section = h2 if h2 is not None else h1

                chunk.metadata = {
                    "doc_id": metadata["doc_id"],
                    "title": metadata["title"],
                    "department": metadata["department"],
                    "access_level": metadata["access_level"],
                    "roles": metadata["roles"],
                    "version": str(metadata["version"]),
                    "section": section,
                    "chunk_index": idx,
                    "content_hash": content_hash,
                    "source_file": file_path.name,
                }
                all_chunks.append(chunk)

                al = metadata["access_level"]
                access_level_counts[al] = access_level_counts.get(al, 0) + 1

        except Exception as e:
            err_msg = f"Error processing {file_path}: {e}"
            logger.error(err_msg)
            errors.append(err_msg)

    if all_chunks:
        vectorstore.add_documents(all_chunks)
        print(f"\nSuccessfully ingested {len(all_chunks)} chunks.")
        print("\nChunks per access_level:")
        for al, count in sorted(access_level_counts.items()):
            print(f"  {al}: {count}")
    else:
        print("\nNo chunks were ingested.")

    if errors:
        print("\nValidation / Ingestion Failures:")
        for err in errors:
            print(f"  - {err}")

    return len(all_chunks), access_level_counts, errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest markdown policy documents into Qdrant.")
    parser.add_argument("--reset", action="store_true", default=False, help="Delete and recreate collection")
    parser.add_argument("--path", type=str, default=POLICIES_DIR, help="Path to policies directory")
    args = parser.parse_args()

    ingest_documents(reset=args.reset, policies_dir=args.path)