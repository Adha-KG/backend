# app/services/flashcard_strategy.py - Strategy Pattern for Flashcard Generation
"""
Strategy Pattern Implementation for different flashcard generation strategies.
This allows for extensible flashcard generation approaches.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from langchain.schema import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class FlashcardGenerationStrategy(ABC):
    """Abstract base class for flashcard generation strategies (Strategy Pattern)"""
    
    @abstractmethod
    def create_system_prompt(self) -> str:
        """Create the system prompt for the LLM"""
        pass
    
    @abstractmethod
    def create_human_prompt(
        self, 
        topic: str | None, 
        context: str, 
        num_flashcards: int
    ) -> str:
        """Create the human prompt for the LLM"""
        pass
    
    @abstractmethod
    def parse_response(self, response_text: str) -> list[dict[str, Any]]:
        """Parse the LLM response into flashcards"""
        pass


class StandardFlashcardStrategy(FlashcardGenerationStrategy):
    """Standard flashcard generation strategy - Q&A format"""
    
    def create_system_prompt(self) -> str:
        return """You are an expert educational content creator specializing in creating effective flashcards for studying.

Your task is to create high-quality flashcards that help students learn and memorize information effectively.

Guidelines for creating flashcards:
1. Each flashcard should focus on ONE key concept, fact, definition, or piece of information
2. The FRONT should be a clear, concise question or prompt (not more than 2-3 sentences)
3. The BACK should contain a complete, accurate answer based on the source material
4. Prioritize important concepts, definitions, formulas, dates, facts, and key relationships
5. Make questions specific and answerable from the provided content
6. Avoid vague or overly broad questions
7. Include technical terms and definitions when relevant
8. For formulas, put the formula name on the front and the formula on the back

Output format: Return ONLY a valid JSON array of flashcards. Each flashcard must have exactly two fields:
- "front": string (the question or prompt)
- "back": string (the answer)

Example format:
[
  {"front": "What is the definition of X?", "back": "X is defined as..."},
  {"front": "What is the formula for Y?", "back": "The formula for Y is: Y = ..."}
]

IMPORTANT: Return ONLY the JSON array, no additional text, explanations, or markdown formatting."""
    
    def create_human_prompt(
        self, 
        topic: str | None, 
        context: str, 
        num_flashcards: int
    ) -> str:
        topic_text = f"Focus on the topic: {topic}" if topic else "Generate flashcards covering key concepts from the material."
        return f"""Generate {num_flashcards} high-quality flashcards based on the following source material.

{topic_text}

Source Material:
{context}

Create {num_flashcards} flashcards that cover the most important and useful information from the source material. 
Make sure each flashcard is:
- Clear and specific
- Based directly on the provided source material
- Educational and useful for studying
- Focused on one key concept per card

Return the flashcards as a JSON array with "front" and "back" fields."""
    
    def parse_response(self, response_text: str) -> list[dict[str, Any]]:
        """Parse JSON response from LLM"""
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)
        
        try:
            flashcards = json.loads(response_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                flashcards = json.loads(json_match.group())
            else:
                logger.error(f"Failed to parse flashcard JSON: {response_text[:200]}")
                raise ValueError("Failed to parse flashcard generation response")
        
        validated_flashcards = []
        for card in flashcards:
            if isinstance(card, dict) and "front" in card and "back" in card:
                validated_flashcards.append({
                    "front": str(card["front"]).strip(),
                    "back": str(card["back"]).strip()
                })
        
        return validated_flashcards


class ConceptDefinitionStrategy(FlashcardGenerationStrategy):
    """Strategy focused on concept-definition pairs"""
    
    def create_system_prompt(self) -> str:
        return """You are an expert educational content creator. Create flashcards that focus on concept-definition pairs.

Guidelines:
1. Front: Concept or term name
2. Back: Clear, comprehensive definition
3. Include examples when relevant
4. Focus on key terminology and concepts

Output format: JSON array with "front" (concept) and "back" (definition) fields."""
    
    def create_human_prompt(
        self, 
        topic: str | None, 
        context: str, 
        num_flashcards: int
    ) -> str:
        topic_text = f"Focus on concepts related to: {topic}" if topic else "Extract key concepts and definitions."
        return f"""Generate {num_flashcards} concept-definition flashcards.

{topic_text}

Source Material:
{context}

Return JSON array with concept names on front and definitions on back."""
    
    def parse_response(self, response_text: str) -> list[dict[str, Any]]:
        # Use same parsing as standard strategy
        strategy = StandardFlashcardStrategy()
        return strategy.parse_response(response_text)


class FlashcardStrategyFactory:
    """Factory Pattern for creating flashcard generation strategies"""
    
    _strategies = {
        "standard": StandardFlashcardStrategy,
        "concept": ConceptDefinitionStrategy,
    }
    
    @classmethod
    def create_strategy(cls, strategy_type: str = "standard") -> FlashcardGenerationStrategy:
        """
        Factory method to create a flashcard generation strategy
        
        Args:
            strategy_type: Type of strategy ("standard" or "concept")
            
        Returns:
            FlashcardGenerationStrategy instance
        """
        strategy_class = cls._strategies.get(strategy_type.lower())
        if not strategy_class:
            logger.warning(f"Unknown strategy type: {strategy_type}, using standard")
            strategy_class = cls._strategies["standard"]
        return strategy_class()
    
    @classmethod
    def get_available_strategies(cls) -> list[str]:
        """Get list of available strategy types"""
        return list(cls._strategies.keys())

