# app/services/flashcard_service.py - AI-powered flashcard generation
"""
Service Layer Pattern: Separates business logic from API routes
Strategy Pattern: Uses FlashcardGenerationStrategy for different generation approaches
Factory Pattern: Uses FlashcardStrategyFactory to create strategies
Template Method Pattern: Defines the algorithm structure for flashcard generation
"""
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.services.retriever import semantic_search
from app.services.flashcard_strategy import (
    FlashcardStrategyFactory,
    FlashcardGenerationStrategy,
)

logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found.")

# Initialize LLM for flashcard generation
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.7,  # Slightly higher for creative flashcard generation
    max_output_tokens=4096
)


async def generate_flashcards(
    topic: str | None = None,
    document_ids: list[str] | None = None,
    num_flashcards: int = 10,
    collection_name: str = "pdf_chunks",
    user_id: str | None = None,
    strategy_type: str = "standard",
) -> list[dict[str, Any]]:
    """
    Generate flashcards from documents using AI.
    
    Args:
        topic: Optional topic to focus on. If None, generates general flashcards
        document_ids: Optional list of document IDs to focus on
        num_flashcards: Number of flashcards to generate
        collection_name: ChromaDB collection name
        user_id: User ID for filtering
        
    Returns:
        List of flashcards with 'front' and 'back' fields
    """
    try:
        # Build search query
        if topic:
            search_query = f"Key concepts, definitions, facts, and important information about {topic}"
        else:
            search_query = "Key concepts, definitions, facts, formulas, and important information"
        
        # Retrieve relevant documents - get more for comprehensive flashcard generation
        n_results = min(20, num_flashcards * 2)  # Get more context for better flashcards
        docs = semantic_search(search_query, n_results=n_results, collection_name=collection_name)
        
        if not docs:
            logger.warning("No documents found for flashcard generation")
            return []
        
        # Extract and combine content
        context_parts = []
        for i, doc in enumerate(docs):
            full_content = doc["content"]
            score = doc["score"]
            source = doc["metadata"].get("source", "unknown")
            context_parts.append(
                f"=== Document {i+1} (Relevance: {score:.3f}, Source: {source}) ===\n{full_content}\n"
            )
        
        full_context = "\n\n".join(context_parts)
        # Limit context size to avoid token limits
        max_context_chars = 20000
        if len(full_context) > max_context_chars:
            full_context = full_context[:max_context_chars]
        
        # Template Method Pattern: Use strategy to define generation steps
        # Factory Pattern: Create appropriate strategy
        strategy: FlashcardGenerationStrategy = FlashcardStrategyFactory.create_strategy(strategy_type)
        
        # Get prompts from strategy
        system_prompt = strategy.create_system_prompt()
        human_prompt = strategy.create_human_prompt(topic, full_context, num_flashcards)
        
        # Generate flashcards using LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = await llm.ainvoke(messages)
        response_text = response.content.strip()
        
        # Parse response using strategy's parsing method
        validated_flashcards = strategy.parse_response(response_text)
        
        if not validated_flashcards:
            logger.warning("No valid flashcards generated")
            return []
        
        logger.info(f"Generated {len(validated_flashcards)} flashcards")
        return validated_flashcards[:num_flashcards]  # Limit to requested number
        
    except Exception as e:
        logger.error(f"Error generating flashcards: {str(e)}")
        raise


async def generate_flashcards_stream(
    topic: str | None = None,
    document_ids: list[str] | None = None,
    num_flashcards: int = 10,
    collection_name: str = "pdf_chunks",
    user_id: str | None = None,
):
    """
    Stream flashcard generation process.
    Yields progress updates and final flashcards.
    """
    try:
        # Yield initial status
        yield f"data: {json.dumps({'status': 'searching', 'message': 'Searching relevant content...', 'done': False})}\n\n"
        
        # Build search query
        if topic:
            search_query = f"Key concepts, definitions, facts, and important information about {topic}"
        else:
            search_query = "Key concepts, definitions, facts, formulas, and important information"
        
        # Retrieve relevant documents
        n_results = min(20, num_flashcards * 2)
        docs = semantic_search(search_query, n_results=n_results, collection_name=collection_name)
        
        if not docs:
            yield f"data: {json.dumps({'status': 'error', 'message': 'No relevant documents found', 'done': True, 'error': True})}\n\n"
            return
        
        yield f"data: {json.dumps({'status': 'generating', 'message': f'Found {len(docs)} relevant sections. Generating flashcards...', 'done': False})}\n\n"
        
        # Extract and combine content
        context_parts = []
        for i, doc in enumerate(docs):
            full_content = doc["content"]
            score = doc["score"]
            source = doc["metadata"].get("source", "unknown")
            context_parts.append(
                f"=== Document {i+1} (Relevance: {score:.3f}, Source: {source}) ===\n{full_content}\n"
            )
        
        full_context = "\n\n".join(context_parts)
        max_context_chars = 20000
        if len(full_context) > max_context_chars:
            full_context = full_context[:max_context_chars]
        
        # Use Strategy Pattern for generation
        strategy: FlashcardGenerationStrategy = FlashcardStrategyFactory.create_strategy("standard")
        system_prompt = strategy.create_system_prompt()
        human_prompt = strategy.create_human_prompt(topic, full_context, num_flashcards)
        
        # Generate flashcards
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        yield f"data: {json.dumps({'status': 'processing', 'message': 'AI is generating flashcards...', 'done': False})}\n\n"
        
        response = await llm.ainvoke(messages)
        response_text = response.content.strip()
        
        # Parse using strategy
        validated_flashcards = strategy.parse_response(response_text)
        
        if not validated_flashcards:
            yield f"data: {json.dumps({'status': 'error', 'message': 'No valid flashcards generated', 'done': True, 'error': True})}\n\n"
            return
        
        # Limit to requested number
        final_flashcards = validated_flashcards[:num_flashcards]
        
        # Yield final result
        yield f"data: {json.dumps({'status': 'complete', 'message': f'Generated {len(final_flashcards)} flashcards', 'flashcards': final_flashcards, 'done': True})}\n\n"
        
    except Exception as e:
        logger.error(f"Error in flashcard generation stream: {str(e)}")
        yield f"data: {json.dumps({'status': 'error', 'message': f'Error: {str(e)}', 'done': True, 'error': True})}\n\n"

