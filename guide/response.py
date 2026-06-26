import ollama
from config import OLLAMA_MODEL
from guide.prompt import build_prompt
from retrieval.search import search

def ask_guide(query):
    """
    Takes a user query, retrieves relevant results, builds the prompt,
    sends it to Ollama, and returns GUIDE's response.
    Non-streaming version used internally for non-SSE contexts.
    """
    results = search(query)
    prompt = build_prompt(query, results)

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]}
        ],
        options={"num_predict": 300},
        keep_alive="1h"
    )

    return {
        "response": response["message"]["content"],
        "results": results
    }

def ask_guide_stream(query):
    """
    Generator function that streams GUIDE's response token by token.
    Yields search results first, then streams Ollama tokens.
    """
    results = search(query)
    prompt = build_prompt(query, results)

    # Yield results metadata first so UI can show cards immediately
    import json
    yield f"data: {json.dumps({'type': 'results', 'results': results})}\n\n"

    # Stream Ollama response
    stream = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]}
        ],
        options={"num_predict": 300},
        keep_alive="1h",
        stream=True
    )

    for chunk in stream:
        token = chunk["message"]["content"]
        if token:
            yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
