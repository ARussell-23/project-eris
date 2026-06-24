import chromadb
from sentence_transformers import SentenceTransformer
from config import CHROMA_DIR, EMBEDDING_MODEL, COLLECTION_NAME

client = chromadb.PersistentClient(path=CHROMA_DIR)
model = SentenceTransformer(EMBEDDING_MODEL)

def get_collection():
    """
    Returns the ChromaDB collection, creating it if it doesn't exist yet.
    """
    return client.get_or_create_collection(name=COLLECTION_NAME)

def store_chunks(chunks):
    """
    Embeds a list of chunk dictionaries and stores them in ChromaDB.
    Each chunk gets a unique ID, its text embedded as a vector,
    and its citation metadata stored alongside it.
    """
    collection = get_collection()

    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    ids = [
        f"{chunk['source_file']}::p{chunk['page_number']}::{i}"
        for i, chunk in enumerate(chunks)
    ]

    metadatas = [
        {
            "title": chunk["title"],
            "author": chunk["author"],
            "doc_type": chunk["doc_type"],
            "source_file": chunk["source_file"],
            "page_number": chunk["page_number"]
        }
        for chunk in chunks
    ]

    collection.add(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )

    return len(chunks)
