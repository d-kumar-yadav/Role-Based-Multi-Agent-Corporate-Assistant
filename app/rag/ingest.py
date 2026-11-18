import argparse
import hashlib
import logging
import sys 
import uuid 
from pathlib import Path
import frontmatter
from langchain_text_splitters import MarkdownHeaderTextSplitter
from .vectorstore import COLLECTION_NAME, get_vectorstore

logger = logging.getLogger("rag.ingest")

POLICIES_DIR = "data/policies"
REQUIRED_FRONTMATTER_KEYS = ["doc_id", "title", "department", "access_level", "roles", "version"]
ALLOWED_DEPARTMENTS = {"hr", "finance", "it", "public", "crossdomain"}  
NAMESPACE = uuid.UUID("6f1c2d3e-0000-4000-8000-000000000001")  
BATCH_SIZE = 100  


# automatic cleanup (closing files, releasing locks, freeing memory) as soon as you are done, even if an error or crash happens!
def parse_and_validate_policy(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        content_bytes = f.read().encode("utf-8")  # read the entire file and convert the string into bytes
        # python's cryptographic hashing library (hashlib.sha256) does NOT accept strings (str)!
        # f.reads() return a str
        post = frontmatter.loads(content_bytes.decode("utf-8"))

    missing_keys = [k for k in REQUIRED_FRONTMATTER_KEYS if k not in post.metadata]
    if missing_keys:
        raise ValueError(f"Missing required frontmatter keys: {missing_keys}")

    roles = post.metadata["roles"]
    if not isinstance(roles, list):  # isisntance check is this variable of this specific type
        # beacuse quadrant need a list in must clause
        raise ValueError(f"'roles' must be a list, got {type(roles).__name__}")

   
    if not roles or not all(isinstance(r, str) and r.strip() for r in roles):
        raise ValueError("'roles' must be a non-empty list of strings")

    #  department must be lowercase and one of the allowed values (typos silently break RBAC)
    dept = str(post.metadata["department"]).strip().lower()
    if dept not in ALLOWED_DEPARTMENTS:
        raise ValueError(f"'department' must be lowercase and one of {sorted(ALLOWED_DEPARTMENTS)}, got '{dept}'")

   
    if not post.content.strip():
        raise ValueError("document body is empty")

    content_hash = hashlib.sha256(content_bytes).hexdigest()
    return post.metadata, post.content, content_hash


def ingest_documents(reset: bool = False, policies_dir: str = POLICIES_DIR):
    if reset:  # just to wipe out old chunk
        vs = get_vectorstore()
        if vs.client.collection_exists(COLLECTION_NAME):
            vs.client.delete_collection(COLLECTION_NAME)
            print(f"Deleted collection '{COLLECTION_NAME}'.")

    vectorstore = get_vectorstore()

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],  # we are creating chunk on each header deefinbe as #, ##, ###
        strip_headers=False,  # it keep header tittle if we do true it will remvove , it help llm to get context
    )

    path_obj = Path(policies_dir)  # convert the string  "data/policies" into path object
    # plain string like "data/policies" is just characters in Python memory. It cannot search your hard drive or find files
    md_files = sorted(list(path_obj.rglob("*.md")))
    # rglob-recursive globbling  it tells Dive into data/policies/, search every sub-folder (finance/, hr/, it/, public/), and find every single file ending with .md!"

    all_chunks = []
    all_ids = [] 
    seen_doc_ids: dict[str, str] = {}  #  remembers doc_id -> file name to catch duplicates
    access_level_counts: dict[str, int] = {}
    errors: list[str] = []

    for file_path in md_files:
        try:
            metadata, text, content_hash = parse_and_validate_policy(file_path)

            # two files with the same doc_id would overwrite each other, so stop here
            doc_id = metadata["doc_id"]
            if doc_id in seen_doc_ids:
                raise ValueError(f"duplicate doc_id '{doc_id}' (also in {seen_doc_ids[doc_id]})")
            seen_doc_ids[doc_id] = file_path.name

            chunks = splitter.split_text(text)

            for idx, chunk in enumerate(chunks):
                h1 = chunk.metadata.get("h1")  # section
                h2 = chunk.metadata.get("h2")  # their subsection
                h3 = chunk.metadata.get("h3")  #  sub-subsection
                section = h3 or h2 or h1  # use the most specific header available

               
                chunk.page_content = f"[{metadata['title']}]\n{chunk.page_content}"

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
                #same doc + same chunk number -> same ID, so running ingest again overwrites instead of duplicating
                all_ids.append(str(uuid.uuid5(NAMESPACE, f"{doc_id}:{idx}")))

                al = metadata["access_level"]
                access_level_counts[al] = access_level_counts.get(al, 0) + 1

        except Exception as e:
            err_msg = f"Error processing {file_path}: {e}"
            logger.error(err_msg)
            errors.append(err_msg)

    if all_chunks:
        # save in batches, with the fixed IDs
        for i in range(0, len(all_chunks), BATCH_SIZE):
            vectorstore.add_documents(all_chunks[i:i + BATCH_SIZE], ids=all_ids[i:i + BATCH_SIZE])
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


if __name__ == "__main__":  # if someone directly run from terminal and name==main then run belwo code
    # create a listner , parsing engine that will read a terminal command
    parser = argparse.ArgumentParser(description="Ingest markdown policy documents into Qdrant.")
    parser.add_argument("--reset", action="store_true", default=False, help="Delete and recreate collection")
    parser.add_argument("--path", type=str, default=POLICIES_DIR, help="Path to policies directory")
    args = parser.parse_args()
    # this helps us to directely run for terminal command

    _, _, errs = ingest_documents(reset=args.reset, policies_dir=args.path)  # NEW: keep the result
    sys.exit(1 if errs else 0)  # NEW: exit code 1 if any file failed, useful for scripts