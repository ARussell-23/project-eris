import ollama
from config import OLLAMA_MODEL
from guide.prompt import build_prompt
from retrieval.search import search

def ask_guide(query):
    print(f"DEBUG: starting search for: {query}", flush=True)
    results = search(query)
    print(f"DEBUG: search complete, {len(results)} results", flush=True)
    prompt = build_prompt(query, results)
    print(f"DEBUG: prompt built, sending to Ollama", flush=True)

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]}
        ],
        options={"num_predict": 300},
        keep_alive="1h"
    )
    print(f"DEBUG: Ollama responded", flush=True)

    return {
        "response": response["message"]["content"],
        "results": results
    }
