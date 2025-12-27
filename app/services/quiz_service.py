# app/services/quiz_service.py - AI-powered quiz generation
"""
Service for generating MCQ quizzes from documents using LLM.
Similar pattern to flashcard_service.py but generates multiple choice questions.
"""
import json
import logging
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.auth.supabase_client import get_supabase
from app.services.retriever import semantic_search

logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found.")

# Initialize LLM for quiz generation
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GEMINI_API_KEY,
    temperature=0.7,  # Balanced for creative but accurate question generation
    max_output_tokens=8192  # Higher for multiple questions
)


async def generate_quiz(
    document_ids: list[str],
    num_questions: int = 10,
    time_limit_minutes: int = 30,
    difficulty: str | None = None,
    title: str | None = None,
    collection_name: str = "pdf_chunks",
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Generate a quiz with MCQ questions from documents using AI.
        
    Args:
        document_ids: List of document IDs to generate questions from
        num_questions: Number of questions to generate
        time_limit_minutes: Time limit for the quiz
        difficulty: Optional difficulty level ('easy', 'medium', 'hard')
        title: Optional quiz title
        collection_name: ChromaDB collection name
        user_id: User ID for database operations
        
    Returns:
        Dictionary with quiz data including questions
    """
    try:
        supabase = get_supabase()
        quiz_id = None
        store_in_db = True
        
        # Try to create quiz record with 'generating' status
        quiz_data = {
            'user_id': user_id,
            'title': title,
            'document_ids': document_ids,
            'num_questions': num_questions,
            'time_limit_minutes': time_limit_minutes,
            'difficulty': difficulty,
            'status': 'generating'
        }
        
        try:
            quiz_result = supabase.table('quizzes').insert(quiz_data).execute()
            if not quiz_result.data:
                logger.warning("Failed to create quiz record, continuing without database storage")
                store_in_db = False
            else:
                quiz_id = quiz_result.data[0]['id']
                logger.info(f"Created quiz record {quiz_id} with status 'generating'")
        except Exception as insert_error:
            error_msg = str(insert_error)
            # Check for foreign key constraint violation
            if 'quizzes_user_id_fkey' in error_msg or '23503' in error_msg or 'foreign key constraint' in error_msg.lower():
                logger.error(f"Foreign key constraint violation - user_id not in users table: {error_msg}")
                raise ValueError("User account not found in database. Please ensure your account is properly set up. This may require re-authentication or contacting support.")
            else:
                logger.warning(f"Failed to create quiz record, continuing without database storage: {error_msg}")
                store_in_db = False
        
        # Build search query based on difficulty
        if difficulty == 'easy':
            search_query = "Basic concepts, definitions, and fundamental information"
        elif difficulty == 'hard':
            search_query = "Advanced concepts, complex relationships, detailed analysis, and nuanced information"
        else:  # medium or None
            search_query = "Key concepts, important information, definitions, and significant details"
        
        # Build filter for document_ids if provided
        where_filter = None
        if document_ids:
            if len(document_ids) > 1:
                where_filter = {"document_id": {"$in": document_ids}}
            else:
                where_filter = {"document_id": document_ids[0]}
        
        # Retrieve relevant documents - get more context for better questions
        # Filter is applied BEFORE search to ensure only selected documents are searched
        n_results = min(30, num_questions * 3)  # Get more context for comprehensive quiz
        docs = semantic_search(search_query, n_results=n_results, collection_name=collection_name, where=where_filter)
        
        if not docs:
            # Update quiz status to failed if stored in DB
            if store_in_db and quiz_id:
                try:
                    supabase.table('quizzes').update({'status': 'failed'}).eq('id', quiz_id).execute()
                except Exception:
                    pass
            logger.warning("No documents found for quiz generation")
            raise ValueError("No relevant content found to generate quiz. Make sure documents are processed.")
        
        # Extract and combine content
        context_parts = []
        for i, doc in enumerate(docs):
            full_content = doc["content"]
            score = doc["score"]
            source = doc["metadata"].get("source", "unknown")
            context_parts.append(
                f"=== Document Section {i+1} (Relevance: {score:.3f}, Source: {source}) ===\n{full_content}\n"
            )
        
        full_context = "\n\n".join(context_parts)
        # Limit context size to avoid token limits
        max_context_chars = 30000
        if len(full_context) > max_context_chars:
            full_context = full_context[:max_context_chars]
        
        # Generate questions using LLM
        system_prompt = """You are an expert educational content creator specializing in creating high-quality multiple choice questions (MCQ) for assessments.

Your task is to create well-structured MCQ questions that effectively test understanding of the provided material.

Guidelines for creating MCQ questions:
1. Each question should test ONE key concept, fact, definition, or piece of information
2. Questions should be clear, unambiguous, and answerable from the source material
3. Provide exactly 4 options (A, B, C, D) for each question
4. One option must be clearly correct based on the source material
5. Incorrect options (distractors) should be plausible but clearly wrong
6. Avoid trick questions or ambiguous wording
7. Include technical terms and definitions when relevant
8. For formulas, test understanding of when/how to use them
9. Prioritize important concepts, definitions, facts, and key relationships

Output format: Return ONLY a valid JSON object with this exact structure:
{
  "questions": [
    {
      "question": "Question text here?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": 0,
      "explanation": "Brief explanation of why this is correct (optional)"
    }
  ]
}

The correct_answer field should be an integer index (0-3) indicating which option is correct.
- 0 = first option (Option A)
- 1 = second option (Option B)
- 2 = third option (Option C)
- 3 = fourth option (Option D)

IMPORTANT: Return ONLY the JSON object, no additional text, explanations, or markdown formatting."""

        difficulty_text = f"Generate {difficulty} difficulty level questions." if difficulty else "Generate questions of moderate difficulty."
        
        human_prompt = f"""Generate {num_questions} high-quality multiple choice questions based on the following source material.

{difficulty_text}

Source Material:
{full_context}

Create {num_questions} MCQ questions that:
- Cover the most important and useful information from the source material
- Are clear and specific
- Have exactly 4 options each
- Have one clearly correct answer based on the provided material
- Include plausible but incorrect distractors
- Test understanding of key concepts, definitions, facts, and relationships

Return the questions as a JSON object with the structure specified in the system prompt."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = await llm.ainvoke(messages)
        response_text = response.content.strip()
        
        # Parse response
        questions = _parse_quiz_response(response_text)
        
        if not questions or len(questions) < num_questions:
            logger.warning(f"Generated only {len(questions) if questions else 0} questions, expected {num_questions}")
            # Still proceed with what we have
        
        # Limit to requested number
        questions = questions[:num_questions]
        
        # Store questions in database if we're storing in DB
        questions_data = []
        for idx, question in enumerate(questions):
            question_data = {
                'question_text': question['question'],
                'options': question['options'],
                'correct_answer': question['correct_answer'],
                'explanation': question.get('explanation'),
                'question_number': idx + 1
            }
            if store_in_db and quiz_id:
                question_data['quiz_id'] = quiz_id
            questions_data.append(question_data)
        
        # Insert all questions if storing in DB
        if store_in_db and quiz_id and questions_data:
            try:
                supabase.table('quiz_questions').insert(questions_data).execute()
            except Exception as insert_error:
                logger.warning(f"Failed to insert questions into database, continuing without storage: {insert_error}")
                store_in_db = False
        
        # Update quiz status to ready if storing in DB
        if store_in_db and quiz_id:
            try:
                supabase.table('quizzes').update({
                    'status': 'ready',
                    'num_questions': len(questions)
                }).eq('id', quiz_id).execute()
            except Exception as update_error:
                logger.warning(f"Failed to update quiz status, continuing without storage: {update_error}")
                store_in_db = False
        
        logger.info(f"Generated {len(questions)} questions" + (f" for quiz {quiz_id}" if quiz_id else " (not stored in database)"))
        
        # Return quiz with questions
        if store_in_db and quiz_id:
            try:
                quiz_result = supabase.table('quizzes').select('*').eq('id', quiz_id).execute()
                questions_result = supabase.table('quiz_questions').select('*').eq('quiz_id', quiz_id).order('question_number').execute()
                
                quiz = quiz_result.data[0] if quiz_result.data else None
                questions_list = questions_result.data if questions_result.data else []
            except Exception as fetch_error:
                logger.warning(f"Failed to fetch quiz from database, using generated data: {fetch_error}")
                store_in_db = False
        
        # If not storing in DB or fetch failed, create response from generated data
        if not store_in_db or not quiz_id:
            now = datetime.utcnow().isoformat()
            quiz = {
                'id': f'temp_{user_id}_{int(datetime.utcnow().timestamp())}' if user_id else 'temp_quiz',
                'user_id': user_id or 'unknown',
                'title': title,
                'document_ids': document_ids,
                'num_questions': len(questions),
                'time_limit_minutes': time_limit_minutes,
                'difficulty': difficulty,
                'status': 'ready',
                'created_at': now,
                'updated_at': now
            }
            questions_list = [
                {
                    'id': f'temp_q_{i}',
                    'quiz_id': quiz['id'],
                    'question_text': q['question'],
                    'options': q['options'],
                    'correct_answer': q['correct_answer'],
                    'explanation': q.get('explanation'),
                    'question_number': i + 1
                } for i, q in enumerate(questions)
            ]
        
        return {
            'quiz': quiz,
            'questions': questions_list
        }
        
    except Exception as e:
        logger.error(f"Error generating quiz: {str(e)}")
        # Try to update quiz status to failed if quiz_id exists and we're storing in DB
        try:
            if 'quiz_id' in locals() and 'store_in_db' in locals() and store_in_db and quiz_id:
                supabase = get_supabase()
                supabase.table('quizzes').update({'status': 'failed'}).eq('id', quiz_id).execute()
        except Exception:
            pass
        raise


async def generate_quiz_stream(
    document_ids: list[str],
    num_questions: int = 10,
    time_limit_minutes: int = 30,
    difficulty: str | None = None,
    title: str | None = None,
    collection_name: str = "pdf_chunks",
    user_id: str | None = None,
):
    """
    Stream quiz generation process.
    Yields progress updates and final quiz data.
    """
    try:
        supabase = get_supabase()
        
        # Yield initial status
        yield f"data: {json.dumps({'status': 'creating', 'message': 'Creating quiz record...', 'done': False})}\n\n"
        
        # Create quiz record
        quiz_data = {
            'user_id': user_id,
            'title': title,
            'document_ids': document_ids,
            'num_questions': num_questions,
            'time_limit_minutes': time_limit_minutes,
            'difficulty': difficulty,
            'status': 'generating'
        }
        
        try:
            quiz_result = supabase.table('quizzes').insert(quiz_data).execute()
            if not quiz_result.data:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Failed to create quiz record', 'done': True, 'error': True})}\n\n"
                return
        except Exception as insert_error:
            error_msg = str(insert_error)
            # Check for foreign key constraint violation
            if 'quizzes_user_id_fkey' in error_msg or '23503' in error_msg:
                yield f"data: {json.dumps({'status': 'error', 'message': 'User account not found in database. Please contact support.', 'done': True, 'error': True})}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'error', 'message': f'Failed to create quiz record: {error_msg}', 'done': True, 'error': True})}\n\n"
            return
        
        quiz_id = quiz_result.data[0]['id']
        
        yield f"data: {json.dumps({'status': 'searching', 'message': 'Searching relevant content...', 'quiz_id': quiz_id, 'done': False})}\n\n"
        
        # Build search query
        if difficulty == 'easy':
            search_query = "Basic concepts, definitions, and fundamental information"
        elif difficulty == 'hard':
            search_query = "Advanced concepts, complex relationships, detailed analysis, and nuanced information"
        else:
            search_query = "Key concepts, important information, definitions, and significant details"
        
        # Build filter for document_ids if provided
        where_filter = None
        if document_ids:
            if len(document_ids) > 1:
                where_filter = {"document_id": {"$in": document_ids}}
            else:
                where_filter = {"document_id": document_ids[0]}
        
        # Retrieve relevant documents
        # Filter is applied BEFORE search to ensure only selected documents are searched
        n_results = min(30, num_questions * 3)
        docs = semantic_search(search_query, n_results=n_results, collection_name=collection_name, where=where_filter)
        
        if not docs:
            supabase.table('quizzes').update({'status': 'failed'}).eq('id', quiz_id).execute()
            yield f"data: {json.dumps({'status': 'error', 'message': 'No relevant documents found', 'done': True, 'error': True})}\n\n"
            return
        
        yield f"data: {json.dumps({'status': 'processing', 'message': f'Found {len(docs)} relevant sections. Generating questions...', 'done': False})}\n\n"
        
        # Extract and combine content
        context_parts = []
        for i, doc in enumerate(docs):
            full_content = doc["content"]
            score = doc["score"]
            source = doc["metadata"].get("source", "unknown")
            context_parts.append(
                f"=== Document Section {i+1} (Relevance: {score:.3f}, Source: {source}) ===\n{full_content}\n"
            )
        
        full_context = "\n\n".join(context_parts)
        max_context_chars = 30000
        if len(full_context) > max_context_chars:
            full_context = full_context[:max_context_chars]
        
        # Generate questions
        system_prompt = """You are an expert educational content creator specializing in creating high-quality multiple choice questions (MCQ) for assessments.

Your task is to create well-structured MCQ questions that effectively test understanding of the provided material.

Guidelines for creating MCQ questions:
1. Each question should test ONE key concept, fact, definition, or piece of information
2. Questions should be clear, unambiguous, and answerable from the source material
3. Provide exactly 4 options (A, B, C, D) for each question
4. One option must be clearly correct based on the source material
5. Incorrect options (distractors) should be plausible but clearly wrong
6. Avoid trick questions or ambiguous wording
7. Include technical terms and definitions when relevant
8. For formulas, test understanding of when/how to use them
9. Prioritize important concepts, definitions, facts, and key relationships

Output format: Return ONLY a valid JSON object with this exact structure:
{
  "questions": [
    {
      "question": "Question text here?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": 0,
      "explanation": "Brief explanation of why this is correct (optional)"
    }
  ]
}

The correct_answer field should be an integer index (0-3) indicating which option is correct.
- 0 = first option (Option A)
- 1 = second option (Option B)
- 2 = third option (Option C)
- 3 = fourth option (Option D)

IMPORTANT: Return ONLY the JSON object, no additional text, explanations, or markdown formatting."""

        difficulty_text = f"Generate {difficulty} difficulty level questions." if difficulty else "Generate questions of moderate difficulty."
        
        human_prompt = f"""Generate {num_questions} high-quality multiple choice questions based on the following source material.

{difficulty_text}

Source Material:
{full_context}

Create {num_questions} MCQ questions that:
- Cover the most important and useful information from the source material
- Are clear and specific
- Have exactly 4 options each
- Have one clearly correct answer based on the provided material
- Include plausible but incorrect distractors
- Test understanding of key concepts, definitions, facts, and relationships

Return the questions as a JSON object with the structure specified in the system prompt."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        yield f"data: {json.dumps({'status': 'generating', 'message': 'AI is generating questions...', 'done': False})}\n\n"
        
        response = await llm.ainvoke(messages)
        response_text = response.content.strip()
        
        # Parse response
        questions = _parse_quiz_response(response_text)
        
        if not questions:
            supabase.table('quizzes').update({'status': 'failed'}).eq('id', quiz_id).execute()
            yield f"data: {json.dumps({'status': 'error', 'message': 'No valid questions generated', 'done': True, 'error': True})}\n\n"
            return
        
        questions = questions[:num_questions]
        
        yield f"data: {json.dumps({'status': 'saving', 'message': f'Saving {len(questions)} questions...', 'done': False})}\n\n"
        
        # Store questions
        questions_data = []
        for idx, question in enumerate(questions):
            question_data = {
                'quiz_id': quiz_id,
                'question_text': question['question'],
                'options': question['options'],
                'correct_answer': question['correct_answer'],
                'explanation': question.get('explanation'),
                'question_number': idx + 1
            }
            questions_data.append(question_data)
        
        if questions_data:
            try:
                insert_result = supabase.table('quiz_questions').insert(questions_data).execute()
                logger.info(f"Inserted {len(questions_data)} questions into database for quiz {quiz_id}")
                if not insert_result.data:
                    logger.warning(f"Question insert returned no data for quiz {quiz_id}")
            except Exception as insert_error:
                logger.error(f"Failed to insert questions into database: {insert_error}", exc_info=True)
                raise  # Re-raise to be caught by outer handler
        
        # Update quiz status
        supabase.table('quizzes').update({
            'status': 'ready',
            'num_questions': len(questions)
        }).eq('id', quiz_id).execute()
        
        # Get final quiz data
        try:
            quiz_result = supabase.table('quizzes').select('*').eq('id', quiz_id).execute()
            questions_result = supabase.table('quiz_questions').select('*').eq('quiz_id', quiz_id).order('question_number').execute()
            
            quiz = quiz_result.data[0] if quiz_result.data else None
            questions_list = questions_result.data if questions_result.data else []
            
            # If questions list is empty but we just inserted them, use the data we have
            if not questions_list and questions_data:
                logger.warning(f"Fetched questions list is empty, using inserted data for quiz {quiz_id}")
                questions_list = questions_data
        except Exception as fetch_error:
            logger.warning(f"Error fetching final quiz data: {fetch_error}, using saved data")
            # Fallback: use the data we already have
            quiz = {'id': quiz_id, 'status': 'ready', 'num_questions': len(questions)}
            questions_list = questions_data if questions_data else []
        
        # Ensure we have valid data
        if not quiz:
            logger.warning(f"Quiz data is None for quiz_id={quiz_id}, creating minimal quiz object")
            quiz = {'id': quiz_id, 'status': 'ready', 'num_questions': len(questions)}
        if not questions_list:
            logger.warning(f"Questions list is empty for quiz_id={quiz_id}")
            questions_list = []
        
        # Format quiz response to match QuizResponse schema (combine quiz and questions)
        # This matches the structure expected by the frontend
        formatted_questions = None
        if questions_list:
            formatted_questions = [
                {
                    'id': q.get('id'),
                    'question_text': q.get('question_text'),
                    'options': q.get('options'),
                    'correct_answer': q.get('correct_answer'),
                    'explanation': q.get('explanation'),
                    'question_number': q.get('question_number')
                } for q in questions_list
            ]
        
        formatted_quiz = {
            'id': quiz.get('id', quiz_id),
            'user_id': quiz.get('user_id', user_id),
            'title': quiz.get('title'),
            'document_ids': quiz.get('document_ids', document_ids),
            'num_questions': quiz.get('num_questions', len(questions)),
            'time_limit_minutes': quiz.get('time_limit_minutes', time_limit_minutes),
            'difficulty': quiz.get('difficulty', difficulty),
            'status': quiz.get('status', 'ready'),
            'questions': formatted_questions,
            'created_at': quiz.get('created_at', ''),
            'updated_at': quiz.get('updated_at', '')
        }
        
        # Yield final result
        try:
            final_data = {
                'status': 'complete',
                'message': f'Generated {len(questions)} questions',
                'quiz': formatted_quiz,
                'done': True
            }
            logger.info(f"Yielding final quiz data: quiz_id={quiz_id}, questions_count={len(questions_list)}, quiz_keys={list(formatted_quiz.keys()) if formatted_quiz else 'None'}")
            final_json = json.dumps(final_data, default=str)
            logger.debug(f"Final JSON length: {len(final_json)}")
            yield f"data: {final_json}\n\n"
        except Exception as json_error:
            logger.error(f"Error serializing final quiz data: {json_error}", exc_info=True)
            # Send minimal data if serialization fails
            minimal_data = {
                'status': 'complete',
                'message': f'Generated {len(questions)} questions',
                'quiz_id': quiz_id,
                'num_questions': len(questions),
                'done': True
            }
            yield f"data: {json.dumps(minimal_data)}\n\n"
        
    except Exception as e:
        logger.error(f"Error in quiz generation stream: {str(e)}", exc_info=True)
        try:
            if 'quiz_id' in locals():
                supabase = get_supabase()
                supabase.table('quizzes').update({'status': 'failed'}).eq('id', quiz_id).execute()
        except Exception as update_error:
            logger.warning(f"Failed to update quiz status to failed: {update_error}")
        error_data = {
            'status': 'error',
            'message': f'Error: {str(e)}',
            'done': True,
            'error': True
        }
        try:
            yield f"data: {json.dumps(error_data)}\n\n"
        except Exception as yield_error:
            logger.error(f"Failed to yield error message: {yield_error}")


def _parse_quiz_response(response_text: str) -> list[dict[str, Any]]:
    """Parse LLM response to extract quiz questions"""
    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)
        
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        import re
        # Try to extract JSON from text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            logger.error(f"Failed to parse quiz JSON: {response_text[:200]}")
            raise ValueError("Failed to parse quiz generation response")
        
    # Extract questions from response
    if isinstance(data, dict) and 'questions' in data:
        questions = data['questions']
    elif isinstance(data, list):
        questions = data
    else:
        logger.error(f"Unexpected response format: {type(data)}")
        raise ValueError("Invalid response format from LLM")
        
    # Validate and clean questions
    validated_questions = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        
        question_text = q.get('question') or q.get('question_text')
        options = q.get('options', [])
        correct_answer = q.get('correct_answer')
        
        if not question_text:
            continue
        
        if not isinstance(options, list) or len(options) != 4:
            logger.warning(f"Question has invalid options: {len(options) if isinstance(options, list) else 'not a list'}")
            continue
        
        if not isinstance(correct_answer, int) or correct_answer < 0 or correct_answer > 3:
            logger.warning(f"Question has invalid correct_answer: {correct_answer}")
            continue
        
        validated_questions.append({
            'question': str(question_text).strip(),
            'options': [str(opt).strip() for opt in options],
            'correct_answer': int(correct_answer),
            'explanation': str(q.get('explanation', '')).strip() if q.get('explanation') else None
        })
        
    return validated_questions