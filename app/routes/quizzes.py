"""Quiz management routes."""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth.auth import get_current_user
from app.auth.supabase_client import get_supabase
from app.schemas import (
    QuizGenerateRequest,
    QuizResponse,
    QuizQuestion,
    QuizListResponse,
    QuizAttemptCreate,
    QuizAnswerSubmit,
    QuizAttemptResponse,
    QuizAttemptListResponse,
    QuizAnswerResponse,
)
from app.services.quiz_service import generate_quiz
from app.services.quiz_attempt_service import (
    create_attempt,
    submit_answer,
    complete_attempt,
    abandon_attempt,
    get_attempt,
    get_user_attempts,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["quizzes"])


@router.post("/generate")
async def generate_quiz_endpoint(
    request: QuizGenerateRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Generate a quiz from user's documents"""
    try:
        user_id = current_user["id"]
        collection_name = f"user_{user_id}_docs"
        
        # Validate inputs
        num_questions = min(max(1, request.num_questions), 50)  # Limit between 1 and 50
        time_limit_minutes = min(max(1, request.time_limit_minutes), 180)  # Limit between 1 and 180
        
        if request.difficulty and request.difficulty not in ['easy', 'medium', 'hard']:
            raise HTTPException(
                status_code=400,
                detail="Difficulty must be 'easy', 'medium', or 'hard'"
            )
        
        # Validate document_ids belong to user
        supabase = get_supabase()
        if request.document_ids:
            docs_result = supabase.table('documents').select('id').eq('user_id', user_id).in_('id', request.document_ids).execute()
            if len(docs_result.data) != len(request.document_ids):
                raise HTTPException(
                    status_code=400,
                    detail="One or more document IDs are invalid or do not belong to you"
                )
        
        result = await generate_quiz(
            document_ids=request.document_ids,
            num_questions=num_questions,
            time_limit_minutes=time_limit_minutes,
            difficulty=request.difficulty,
            title=request.title,
            collection_name=collection_name,
            user_id=user_id,
        )
        
        quiz = result['quiz']
        questions = result['questions']
        
        # Format response
        quiz_response = QuizResponse(
            id=quiz['id'],
            user_id=quiz['user_id'],
            title=quiz.get('title'),
            document_ids=quiz['document_ids'],
            num_questions=quiz['num_questions'],
            time_limit_minutes=quiz['time_limit_minutes'],
            difficulty=quiz.get('difficulty'),
            status=quiz['status'],
            questions=[
                QuizQuestion(
                    id=q['id'],
                    question_text=q['question_text'],
                    options=q['options'],
                    correct_answer=q['correct_answer'],
                    explanation=q.get('explanation'),
                    question_number=q['question_number']
                ) for q in questions
            ] if questions else None,
            created_at=quiz['created_at'],
            updated_at=quiz['updated_at']
        )
        
        return quiz_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error generating quiz: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate quiz: {str(e)}"
        ) from None


@router.post("/generate/stream", response_model=QuizResponse)
async def generate_quiz_stream_endpoint(
    request: QuizGenerateRequest,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Generate quiz and return complete result as JSON (non-streaming)"""
    try:
        user_id = current_user["id"]
        collection_name = f"user_{user_id}_docs"
        
        # Validate user exists in database (users table, not auth.users)
        supabase = get_supabase()
        try:
            user_check = supabase.table('users').select('id').eq('id', user_id).execute()
            if not user_check.data:
                logger.warning(f"User {user_id} not found in users table")
                raise HTTPException(
                    status_code=400,
                    detail="User account not found. Please contact support or try signing up again."
                )
        except HTTPException:
            raise
        except Exception as user_check_error:
            logger.error(f"Error checking user existence: {user_check_error}")
            raise HTTPException(
                status_code=500,
                detail="Error validating user account. Please try again."
            ) from user_check_error
        
        # Validate inputs
        num_questions = min(max(1, request.num_questions), 50)
        time_limit_minutes = min(max(1, request.time_limit_minutes), 180)
        
        if request.difficulty and request.difficulty not in ['easy', 'medium', 'hard']:
            raise HTTPException(
                status_code=400,
                detail="Difficulty must be 'easy', 'medium', or 'hard'"
            )
        
        # Validate document_ids belong to user
        if request.document_ids:
            docs_result = supabase.table('documents').select('id').eq('user_id', user_id).in_('id', request.document_ids).execute()
            if len(docs_result.data) != len(request.document_ids):
                raise HTTPException(
                    status_code=400,
                    detail="One or more document IDs are invalid or do not belong to you"
                )
        
        # Generate quiz (non-streaming)
        result = await generate_quiz(
            document_ids=request.document_ids,
            num_questions=num_questions,
            time_limit_minutes=time_limit_minutes,
            difficulty=request.difficulty,
            title=request.title,
            collection_name=collection_name,
            user_id=user_id,
        )
        
        quiz = result['quiz']
        questions = result['questions']
        
        # Format response
        quiz_response = QuizResponse(
            id=quiz.get('id'),
            user_id=quiz.get('user_id'),
            title=quiz.get('title'),
            document_ids=quiz.get('document_ids', request.document_ids),
            num_questions=quiz.get('num_questions', len(questions) if questions else 0),
            time_limit_minutes=quiz.get('time_limit_minutes', time_limit_minutes),
            difficulty=quiz.get('difficulty', request.difficulty),
            status=quiz.get('status', 'ready'),
            questions=[
                QuizQuestion(
                    id=q.get('id'),
                    question_text=q.get('question_text'),
                    options=q.get('options'),
                    correct_answer=q.get('correct_answer'),
                    explanation=q.get('explanation'),
                    question_number=q.get('question_number')
                ) for q in questions
            ] if questions else None,
            created_at=quiz.get('created_at', ''),
            updated_at=quiz.get('updated_at', '')
        )
        
        return quiz_response
        
    except HTTPException:
        raise
    except Exception as err:
        logger.exception(f"Error during quiz generation: {err}")
        error_message = str(err)
        # Handle specific error types
        if 'User account not found' in error_message or 'foreign key constraint' in error_message.lower():
            error_message = "User account not found in database. Please contact support or try signing up again."
        elif 'APIError' in str(type(err)):
            if hasattr(err, 'message'):
                error_message = err.message
            elif 'foreign key constraint' in error_message.lower():
                error_message = "User account not found in database. Please contact support."
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate quiz: {error_message}"
        ) from None


@router.get("", response_model=list[QuizListResponse])
async def get_user_quizzes_endpoint(
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Get all quizzes for the current user"""
    try:
        user_id = current_user["id"]
        supabase = get_supabase()
        
        result = supabase.table('quizzes').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        
        quizzes = result.data if result.data else []
        
        return [
            QuizListResponse(
                id=q['id'],
                title=q.get('title'),
                document_ids=q['document_ids'],
                num_questions=q['num_questions'],
                time_limit_minutes=q['time_limit_minutes'],
                difficulty=q.get('difficulty'),
                status=q['status'],
                created_at=q['created_at'],
                updated_at=q['updated_at']
            ) for q in quizzes
        ]
        
    except Exception as e:
        logger.exception(f"Error getting user quizzes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get quizzes: {str(e)}"
        ) from None


@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz_endpoint(
    quiz_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Get quiz details with questions"""
    try:
        user_id = current_user["id"]
        
        # Check if this is a temp quiz ID (quiz couldn't be stored in database)
        if quiz_id.startswith('temp_'):
            raise HTTPException(
                status_code=404,
                detail="Quiz not found. This quiz was generated but could not be saved to the database. Please ensure your user account is properly set up and try generating a new quiz."
            )
        
        supabase = get_supabase()
        
        # Get quiz
        quiz_result = supabase.table('quizzes').select('*').eq('id', quiz_id).eq('user_id', user_id).execute()
        
        if not quiz_result.data:
            raise HTTPException(
                status_code=404,
                detail="Quiz not found or access denied"
            )
        
        quiz = quiz_result.data[0]
        
        # Get questions (only if quiz is ready)
        questions = None
        if quiz['status'] == 'ready':
            questions_result = supabase.table('quiz_questions').select('*').eq('quiz_id', quiz_id).order('question_number').execute()
            questions = questions_result.data if questions_result.data else []
        
        return QuizResponse(
            id=quiz['id'],
            user_id=quiz['user_id'],
            title=quiz.get('title'),
            document_ids=quiz['document_ids'],
            num_questions=quiz['num_questions'],
            time_limit_minutes=quiz['time_limit_minutes'],
            difficulty=quiz.get('difficulty'),
            status=quiz['status'],
            questions=[
                QuizQuestion(
                    id=q['id'],
                    question_text=q['question_text'],
                    options=q['options'],
                    correct_answer=q['correct_answer'],
                    explanation=q.get('explanation'),
                    question_number=q['question_number']
                ) for q in questions
            ] if questions else None,
            created_at=quiz['created_at'],
            updated_at=quiz['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting quiz: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get quiz: {str(e)}"
        ) from None


@router.post("/{quiz_id}/attempts", response_model=QuizAttemptResponse)
async def create_attempt_endpoint(
    quiz_id: str,
    request: QuizAttemptCreate,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Start a new quiz attempt"""
    try:
        user_id = current_user["id"]
        
        # Check if this is a temp quiz ID (quiz couldn't be stored in database)
        if quiz_id.startswith('temp_'):
            raise HTTPException(
                status_code=400,
                detail="Cannot create attempt for a temporary quiz. This quiz was generated but could not be saved to the database. Please ensure your user account is properly set up and try generating a new quiz."
            )
        
        attempt = await create_attempt(quiz_id, user_id)
        
        return QuizAttemptResponse(
            id=attempt['id'],
            quiz_id=attempt['quiz_id'],
            user_id=attempt['user_id'],
            started_at=attempt['started_at'],
            completed_at=attempt.get('completed_at'),
            time_spent_seconds=attempt.get('time_spent_seconds'),
            status=attempt['status'],
            score=attempt.get('score'),
            total_questions=attempt['total_questions'],
            percentage_score=float(attempt['percentage_score']) if attempt.get('percentage_score') else None,
            answers=None,  # Don't include answers when creating
            created_at=attempt['created_at'],
            updated_at=attempt['updated_at']
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from None
    except Exception as e:
        logger.exception(f"Error creating attempt: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create attempt: {str(e)}"
        ) from None


@router.get("/{quiz_id}/attempts", response_model=list[QuizAttemptListResponse])
async def get_quiz_attempts_endpoint(
    quiz_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Get all attempts for a quiz"""
    try:
        user_id = current_user["id"]
        
        # Check if this is a temp quiz ID (quiz couldn't be stored in database)
        if quiz_id.startswith('temp_'):
            raise HTTPException(
                status_code=404,
                detail="Quiz not found. This quiz was generated but could not be saved to the database. Please ensure your user account is properly set up and try generating a new quiz."
            )
        
        attempts = await get_user_attempts(quiz_id=quiz_id, user_id=user_id)
        
        return [
            QuizAttemptListResponse(
                id=a['id'],
                quiz_id=a['quiz_id'],
                started_at=a['started_at'],
                completed_at=a.get('completed_at'),
                status=a['status'],
                score=a.get('score'),
                total_questions=a['total_questions'],
                percentage_score=float(a['percentage_score']) if a.get('percentage_score') else None
            ) for a in attempts
        ]
        
    except Exception as e:
        logger.exception(f"Error getting quiz attempts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get attempts: {str(e)}"
        ) from None


@router.post("/attempts/{attempt_id}/answers", response_model=QuizAnswerResponse)
async def submit_answer_endpoint(
    attempt_id: str,
    request: QuizAnswerSubmit,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Submit an answer for a question"""
    try:
        user_id = current_user["id"]
        
        # Validate selected_answer
        if request.selected_answer < 0 or request.selected_answer > 3:
            raise HTTPException(
                status_code=400,
                detail="selected_answer must be between 0 and 3"
            )
        
        answer = await submit_answer(
            attempt_id=attempt_id,
            question_id=request.question_id,
            selected_answer=request.selected_answer,
            user_id=user_id,
            time_spent_seconds=request.time_spent_seconds
        )
        
        return QuizAnswerResponse(
            id=answer['id'],
            question_id=answer['question_id'],
            selected_answer=answer.get('selected_answer'),
            is_correct=answer.get('is_correct'),
            time_spent_seconds=answer.get('time_spent_seconds'),
            answered_at=answer.get('answered_at')
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from None
    except Exception as e:
        logger.exception(f"Error submitting answer: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit answer: {str(e)}"
        ) from None


@router.post("/attempts/{attempt_id}/complete", response_model=QuizAttemptResponse)
async def complete_attempt_endpoint(
    attempt_id: str,
    time_spent_seconds: int | None = None,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Complete a quiz attempt"""
    try:
        user_id = current_user["id"]
        
        attempt = await complete_attempt(attempt_id, user_id, time_spent_seconds)
        
        # Get answers for response
        supabase = get_supabase()
        answers_result = supabase.table('quiz_answers').select('*').eq('attempt_id', attempt_id).execute()
        answers = answers_result.data if answers_result.data else []
        
        return QuizAttemptResponse(
            id=attempt['id'],
            quiz_id=attempt['quiz_id'],
            user_id=attempt['user_id'],
            started_at=attempt['started_at'],
            completed_at=attempt.get('completed_at'),
            time_spent_seconds=attempt.get('time_spent_seconds'),
            status=attempt['status'],
            score=attempt.get('score'),
            total_questions=attempt['total_questions'],
            percentage_score=float(attempt['percentage_score']) if attempt.get('percentage_score') else None,
            answers=[
                QuizAnswerResponse(
                    id=a['id'],
                    question_id=a['question_id'],
                    selected_answer=a.get('selected_answer'),
                    is_correct=a.get('is_correct'),
                    time_spent_seconds=a.get('time_spent_seconds'),
                    answered_at=a.get('answered_at')
                ) for a in answers
            ],
            created_at=attempt['created_at'],
            updated_at=attempt['updated_at']
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from None
    except Exception as e:
        logger.exception(f"Error completing attempt: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete attempt: {str(e)}"
        ) from None


@router.get("/attempts/{attempt_id}", response_model=QuizAttemptResponse)
async def get_attempt_endpoint(
    attempt_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Get attempt details with answers"""
    try:
        user_id = current_user["id"]
        
        attempt = await get_attempt(attempt_id, user_id, include_answers=True)
        
        if not attempt:
            raise HTTPException(
                status_code=404,
                detail="Attempt not found or access denied"
            )
        
        return QuizAttemptResponse(
            id=attempt['id'],
            quiz_id=attempt['quiz_id'],
            user_id=attempt['user_id'],
            started_at=attempt['started_at'],
            completed_at=attempt.get('completed_at'),
            time_spent_seconds=attempt.get('time_spent_seconds'),
            status=attempt['status'],
            score=attempt.get('score'),
            total_questions=attempt['total_questions'],
            percentage_score=float(attempt['percentage_score']) if attempt.get('percentage_score') else None,
            answers=[
                QuizAnswerResponse(
                    id=a['id'],
                    question_id=a['question_id'],
                    selected_answer=a.get('selected_answer'),
                    is_correct=a.get('is_correct'),
                    time_spent_seconds=a.get('time_spent_seconds'),
                    answered_at=a.get('answered_at')
                ) for a in (attempt.get('answers', []) or [])
            ],
            created_at=attempt['created_at'],
            updated_at=attempt['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting attempt: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get attempt: {str(e)}"
        ) from None


@router.put("/attempts/{attempt_id}/abandon", response_model=QuizAttemptResponse)
async def abandon_attempt_endpoint(
    attempt_id: str,
    current_user: dict[str, Any] = Depends(get_current_user)
):
    """Mark an attempt as abandoned"""
    try:
        user_id = current_user["id"]
        
        attempt = await abandon_attempt(attempt_id, user_id)
        
        return QuizAttemptResponse(
            id=attempt['id'],
            quiz_id=attempt['quiz_id'],
            user_id=attempt['user_id'],
            started_at=attempt['started_at'],
            completed_at=attempt.get('completed_at'),
            time_spent_seconds=attempt.get('time_spent_seconds'),
            status=attempt['status'],
            score=attempt.get('score'),
            total_questions=attempt['total_questions'],
            percentage_score=float(attempt['percentage_score']) if attempt.get('percentage_score') else None,
            answers=None,
            created_at=attempt['created_at'],
            updated_at=attempt['updated_at']
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from None
    except Exception as e:
        logger.exception(f"Error abandoning attempt: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to abandon attempt: {str(e)}"
        ) from None

