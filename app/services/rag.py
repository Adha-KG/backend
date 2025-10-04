# app/services/rag.py - Enhanced version for detailed responses
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

# Initialize with higher token limit
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.8,  # Slightly higher for more creative elaboration
    max_output_tokens=8192  # Maximum tokens for detailed response
)


async def answer_question(question: str, n_results: int = 10, max_context_chars: int = 15000):
    """
    Generate detailed, comprehensive answers with full explanations.
    """
    try:
        # 1️⃣ Retrieve MORE documents for comprehensive coverage
        docs = semantic_search(question, n_results=n_results)
        if not docs:
            return "No relevant information found."

        # 2️⃣ Extract FULL content, not just snippets
        context_parts = []
        total_content = []
  # noqa: W293
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

        # 3️⃣ Enhanced prompt for detailed explanation
        system_prompt = """You are an expert educator creating comprehensive study materials. Your role is to:

1. READ all provided documents thoroughly
2. SYNTHESIZE the information into detailed, educational content
3. EXPAND on concepts with explanations, not just summaries
4. CREATE comprehensive notes that would help a student fully understand the topic

Requirements:
- DO NOT just summarize what documents contain
- DO NOT say "Document X mentions..." or "The context provides..."
- INSTEAD, teach the topic as if writing a textbook chapter
- Include ALL technical details, formulas, procedures, and examples
- Explain concepts in depth with proper context
- Use the documents as source material to create a complete explanation
- Format with clear headings, subheadings, and bullet points
- Make it detailed enough for exam preparation"""

        human_prompt = f"""Topic/Question: {question}

Source Materials:
{full_context}

Based on ALL the information above, create a COMPREHENSIVE, DETAILED explanation of the topic. 
Write as if you're creating study notes for a student who needs to understand this topic thoroughly.
Include every important concept, formula, procedure, and detail mentioned in the materials.

IMPORTANT: Don't reference the documents directly. Instead, integrate all information into a cohesive, detailed explanation.

Comprehensive Explanation:"""  # noqa: W291

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


# Specialized function for creating study notes
async def create_detailed_notes(topic: str, n_results: int = 15):
    """
    Create extremely detailed study notes by retrieving maximum content.
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

        # Detailed note-making prompt
        prompt = f"""You are creating a comprehensive study guide on: {topic}

Using the following source material:
{combined_content}

Create an EXTENSIVE study guide following this structure:

# {topic.upper()} - COMPREHENSIVE STUDY GUIDE

## 1. INTRODUCTION AND OVERVIEW
[Write 2-3 detailed paragraphs introducing the topic]

## 2. FUNDAMENTAL CONCEPTS
[List and thoroughly explain each concept with multiple paragraphs each]

## 3. DETAILED TECHNICAL EXPLANATION
### 3.1 [First Major Component/Concept]
[Multiple paragraphs with full technical details]

### 3.2 [Second Major Component/Concept]
[Multiple paragraphs with full technical details]

[Continue for all major components]

## 4. IMPLEMENTATION DETAILS
[Step-by-step procedures, circuit designs, algorithms, etc.]

## 5. MATHEMATICAL FORMULATIONS
[All relevant equations, derivations, and calculations]

## 6. PRACTICAL EXAMPLES
[Detailed worked examples with explanations]

## 7. IMPORTANT PARAMETERS AND SPECIFICATIONS
[Tables, lists, and detailed specifications]

## 8. COMMON APPLICATIONS
[Real-world uses and implementations]

## 9. TROUBLESHOOTING AND CONSIDERATIONS
[Potential issues, solutions, and best practices]

## 10. COMPREHENSIVE SUMMARY
[Detailed summary touching all major points]

## 11. KEY POINTS FOR REVISION
[Detailed bullet points covering everything important]

Write AT LEAST 2000 words. Be extremely thorough and educational. Include EVERYTHING from the source material."""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()

    except Exception as e:
        logger.error(f"Error in create_detailed_notes: {str(e)}")
        return f"Error generating notes: {str(e)}"
