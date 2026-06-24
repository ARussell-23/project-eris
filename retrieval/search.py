from sentence_transformers import SentenceTransformer
import chromadb
from config import (
    CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL,
    MAX_RESULTS, NULL_THRESHOLD
)

client = chromadb.PersistentClient(path=CHROMA_DIR)
model = SentenceTransformer(EMBEDDING_MODEL)

def search(query):
    """
    Takes a natural language query, converts it to a vector,
    searches ChromaDB for the closest matching chunks,
    and returns a list of results with citation metadata.
    Returns an empty list if no results meet the null threshold.
    """
    collection = client.get_collection(COLLECTION_NAME)

    query_vector = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=MAX_RESULTS,
        include=["documents", "metadatas", "distances"]
    )

    hits = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, distance in zip(documents, metadatas, distances):
        similarity = 1 - distance
        if similarity >= NULL_THRESHOLD:
            hits.append({
                "text": doc,
                "similarity": round(similarity, 3),
                "title": meta["title"],
                "author": meta["author"],
                "doc_type": meta["doc_type"],
                "source_file": meta["source_file"],
                "page_number": meta["page_number"]
            })

    return hits
