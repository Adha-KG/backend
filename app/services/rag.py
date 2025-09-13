import os

import httpx
from dotenv import load_dotenv

from app.services.retriever import semantic_search

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found. Make sure it's set in your .env file.")


async def answer_question(question: str, n_results: int = 5, max_context_chars: int = 3000):
    """
    Answer a question using summarized relevant documents from semantic search
    and Google Gemini.

    Args:
        question: The user’s question string.
        n_results: Number of top documents to retrieve.
        max_context_chars: Max characters of combined context for the model.

    Returns:
        The generated answer text.
    """

    # 1️⃣ Retrieve relevant documents
    docs = semantic_search(question, n_results=n_results)
    if not docs:
        return "No relevant information found to answer the question."

    # 2️⃣ Summarize each document to a short snippet
    summarized_snippets = []
    for doc_id, doc_text, distance in docs:
        snippet = doc_text.strip().replace("\n", " ")
        # Keep first 300 characters (or less) per doc
        snippet = snippet[:300] + ("..." if len(snippet) > 300 else "")
        summarized_snippets.append(f"[ID: {doc_id}, Relevance: {distance:.4f}] {snippet}")

    # 3️⃣ Combine snippets and truncate to max_context_chars
    context = " ".join(summarized_snippets)
    if len(context) > max_context_chars:
        context = context[:max_context_chars] + " ..."

    # 4️⃣ Build the improved prompt
    prompt = f"""
You are an expert assistant. Use ONLY the context provided to answer the question.
Answer concisely in a single, clear response. Avoid listing multiple answers.
If the context does not contain the answer, answer using your own knowledge.

Context:
{context}

Question:
{question}

Answer:
"""

    # 5️⃣ Gemini API endpoint
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }

    # 6️⃣ Send request and parse
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{url}?key={GEMINI_API_KEY}", json=payload)
        response.raise_for_status()
        data = response.json()

        try:
            answer_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return answer_text
        except (KeyError, IndexError):
            return "Failed to generate an answer from the model."
