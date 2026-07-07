import ollama
import chromadb
from sentence_transformers import SentenceTransformer
from config import (
    CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL,
    MAX_RESULTS, NULL_THRESHOLD, OLLAMA_MODEL, QUERY_VARIANTS
)

client = chromadb.PersistentClient(path=CHROMA_DIR)
model = SentenceTransformer(EMBEDDING_MODEL)

def expand_query(query):
    """
    Uses Ollama to generate QUERY_VARIANTS semantic variants of the user's query.
    Returns a list of query strings including the original.
    Falls back to the original query only if Ollama fails.
    """
    try:
        prompt = (
            f"Generate {QUERY_VARIANTS} alternative ways to ask the following question. "
            f"Each variant should capture the same intent but use different phrasing or vocabulary. "
            f"Return only the variants, one per line, no numbering, no explanation.\n\n"
            f"Original query: {query}"
        )
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 150},
            keep_alive="1h"
        )
        variants = [
            line.strip()
            for line in response["message"]["content"].strip().splitlines()
            if line.strip() and len(line.strip()) > 5
        ]
        # Always include the original query
        all_queries = [query] + variants[:QUERY_VARIANTS]
        return all_queries
    except Exception as e:
        print(f"Query expansion failed, using original: {e}")
        return [query]

def search(query):
    """
    Expands the query into multiple variants, runs each against ChromaDB,
    deduplicates by highest similarity score, and returns top MAX_RESULTS
    above NULL_THRESHOLD.
    """
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    # Expand query into variants
    queries = expand_query(query)

    # Run each variant against ChromaDB
    seen = {}  # source_file::page_number -> best result dict

    for q in queries:
        try:
            query_vector = model.encode(q).tolist()
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=MAX_RESULTS,
                include=["documents", "metadatas", "distances"]
            )

            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                similarity = round(1 - dist, 3)
                if similarity < NULL_THRESHOLD:
                    continue

                # Deduplicate by source_file + page_number, keeping highest score
                key = f"{meta.get('source_file', '')}::p{meta.get('page_number', 0)}"
                if key not in seen or similarity > seen[key]["similarity"]:
                    seen[key] = {
                        "title": meta.get("title", "Unknown"),
                        "author": meta.get("author", ""),
                        "doc_type": meta.get("doc_type", "DOCUMENT"),
                        "source_file": meta.get("source_file", ""),
                        "page_number": meta.get("page_number", 0),
                        "text": doc,
                        "similarity": similarity
                    }
        except Exception as e:
            print(f"Search failed for variant '{q}': {e}")
            continue

    # Sort by similarity descending, return top MAX_RESULTS
    ranked = sorted(seen.values(), key=lambda x: x["similarity"], reverse=True)
    return ranked[:MAX_RESULTS]
