# app/services/rag.py - RAG service for concise, accurate answers
import json
import logging
import os

from dotenv import load_dotenv
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.services.retriever import semantic_search

logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found.")

# Initialize LLM with balanced settings
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.5,  # Balanced for clear, focused responses
    max_output_tokens=4096  # Reasonable limit for concise answers
)


async def answer_question(
    question: str,
    n_results: int = 10,
    max_context_chars: int = 15000,
    collection_name: str = "pdf_chunks",
    chat_history: list = None,
    user_id: str = None,):
    """
    Generate concise, accurate answers based on retrieved documents.
    """
    try:
        # 1️⃣ Retrieve relevant documents
        docs = semantic_search(question, n_results=n_results, collection_name=collection_name)
        if not docs:
            return "No relevant information found."

        # 2️⃣ Extract FULL content, not just snippets
        context_parts = []
        total_content = []

        for i, doc in enumerate(docs):
            # Get the FULL content of each document
            full_content = doc["content"]
            score = doc["score"]
            source = doc["metadata"].get("source", "unknown")  # noqa: F841

            # Add full content to context
            context_parts.append(f"=== Document {i+1} (Relevance: {score:.3f}) ===\n{full_content}\n")
            total_content.append(full_content)

        # Combine all content
        full_context = "\n\n".join(context_parts)
        if len(full_context) > max_context_chars:
            full_context = full_context[:max_context_chars]

        # 3️⃣ Build conversation history context
        history_text = ""
        if chat_history and len(chat_history) > 0:
            # Get last 3-4 messages for context
            recent_history = chat_history[-4:]
            history_parts = []

            for msg in recent_history:
                content = msg.get('content', '').strip()
                if content:
                    # Truncate very long messages
                    if len(content) > 300:
                        content = content[:300] + "..."
                    history_parts.append(content)
            if history_parts:
                history_text = f"""Previous conversation context:
{chr(10).join(history_parts)}

---

"""

        # 3️⃣ Prompt for concise, direct answers
        system_prompt = """You are a helpful assistant that provides clear, concise answers based on provided documents.

Your role is to:
1. READ all provided documents thoroughly
2. ANSWER the question directly using information from the documents
3. BE CONCISE - provide essential information without unnecessary elaboration
4. BE ACCURATE - only use information found in the provided documents

Requirements:
- Answer directly and clearly
- DO NOT reference documents explicitly (e.g., "Document X says...")
- DO NOT add unnecessary background or filler text
- DO include relevant technical details, formulas, and procedures when needed
- Use clear formatting (headings, bullet points) only when helpful
- Be thorough but brief - focus on answering the question"""

        human_prompt = f"""{history_text}Question: {question}

Source Materials:
{full_context}

Answer the question concisely using the information from the source materials above. 
Be direct and focused - provide a clear answer without unnecessary elaboration.
Include relevant details, formulas, and procedures only when they are essential to answering the question.

IMPORTANT: Don't reference the documents directly. Integrate the information naturally into your answer.

Answer:"""  # noqa: W291

        # 4️⃣ Generate response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]

        response = await llm.ainvoke(messages)
        return response.content.strip()

    except Exception as e:
        logger.error(f"Error in answer_question: {str(e)}")
        return f"Error generating answer: {str(e)}"


async def answer_question_stream(
    question: str,
    n_results: int = 10,
    max_context_chars: int = 15000,
    collection_name: str = "pdf_chunks",
    chat_history: list = None,
    user_id: str = None,
):
    """
    Stream concise, accurate answers based on retrieved documents.
    Yields chunks of text as they're generated in SSE format.
    """
    try:
        # 1️⃣ Retrieve relevant documents
        docs = semantic_search(question, n_results=n_results, collection_name=collection_name)
        if not docs:
            yield f"data: {json.dumps({'content': 'No relevant information found.', 'done': True})}\n\n"
            return

        # 2️⃣ Extract content
        context_parts = []
        for i, doc in enumerate(docs):
            full_content = doc["content"]
            score = doc["score"]
            context_parts.append(f"=== Document {i+1} (Relevance: {score:.3f}) ===\n{full_content}\n")

        # Combine all content
        full_context = "\n\n".join(context_parts)
        if len(full_context) > max_context_chars:
            full_context = full_context[:max_context_chars]

        # 3️⃣ Build conversation history context
        history_text = ""
        if chat_history and len(chat_history) > 0:
            recent_history = chat_history[-4:]
            history_parts = []
            for msg in recent_history:
                content = msg.get('content', '').strip()
                if content:
                    if len(content) > 300:
                        content = content[:300] + "..."
                    history_parts.append(content)
            if history_parts:
                history_text = f"""Previous conversation context:
{chr(10).join(history_parts)}

---

"""

        # 4️⃣ Prompt for concise, direct answers
        system_prompt = """You are a helpful assistant that provides clear, concise answers based on provided documents.

Your role is to:
1. READ all provided documents thoroughly
2. ANSWER the question directly using information from the documents
3. BE CONCISE - provide essential information without unnecessary elaboration
4. BE ACCURATE - only use information found in the provided documents

Requirements:
- Answer directly and clearly
- DO NOT reference documents explicitly (e.g., "Document X says...")
- DO NOT add unnecessary background or filler text
- DO include relevant technical details, formulas, and procedures when needed
- Use clear formatting (headings, bullet points) only when helpful
- Be thorough but brief - focus on answering the question"""

        human_prompt = f"""{history_text}Question: {question}

Source Materials:
{full_context}

Answer the question concisely using the information from the source materials above. 
Be direct and focused - provide a clear answer without unnecessary elaboration.
Include relevant details, formulas, and procedures only when they are essential to answering the question.

IMPORTANT: Don't reference the documents directly. Integrate the information naturally into your answer.

Answer:"""  # noqa: W291

        # 5️⃣ Stream response
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]

        full_response = ""
        async for chunk in llm.astream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                content = chunk.content
                full_response += content
                # Send chunk as Server-Sent Events (SSE) format
                yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"

        # Send final done message
        yield f"data: {json.dumps({'content': '', 'done': True, 'full_response': full_response.strip()})}\n\n"

    except Exception as e:
        logger.error(f"Error in answer_question_stream: {str(e)}")
        error_msg = f"Error generating answer: {str(e)}"
        yield f"data: {json.dumps({'content': error_msg, 'done': True, 'error': True})}\n\n"


# Specialized function for creating study notes
async def create_detailed_notes(topic: str, n_results: int = 15):
    """
    Create well-organized study notes by retrieving relevant content.
    """
    try:
        # Get even more documents
        docs = semantic_search(topic, n_results=n_results)
        if not docs:
            return "No relevant information found."

        # Compile ALL content without truncation
        all_content = []
        for doc in docs:
            all_content.append(doc["content"])

        # Join all content
        combined_content = "\n\n---\n\n".join(all_content)

        # Concise note-making prompt
        prompt = f"""Create well-organized study notes on: {topic}

Source material:
{combined_content}

Create structured study notes that cover the key information. Be comprehensive but concise - include all important points without unnecessary repetition or filler.

Structure:
- Overview: Brief introduction
- Key Concepts: Essential concepts explained clearly
- Important Details: Technical details, formulas, procedures
- Examples: Relevant examples when available

Focus on clarity and completeness, not length. Include all essential information from the source material in a clear, organized format."""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()

    except Exception as e:
        logger.error(f"Error in create_detailed_notes: {str(e)}")
        return f"Error generating notes: {str(e)}"
