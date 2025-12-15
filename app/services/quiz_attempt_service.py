# app/services/quiz_attempt_service.py - Quiz attempt management
"""
Service for managing quiz attempts, answer submission, and scoring.
"""
import logging
from datetime import datetime
from typing import Any

from app.auth.supabase_client import get_supabase

logger = logging.getLogger(__name__)


async def create_attempt(quiz_id: str, user_id: str) -> dict[str, Any]:
    """
    Create a new quiz attempt.
    
    Args:
        quiz_id: ID of the quiz to attempt
        user_id: ID of the user attempting the quiz
        
    Returns:
        Dictionary with attempt data
    """
    supabase = get_supabase()
    
    try:
        # Check if quiz exists and get details
        quiz_result = supabase.table('quizzes').select('*').eq('id', quiz_id).eq('user_id', user_id).execute()
        if not quiz_result.data:
            raise ValueError("Quiz not found or access denied")
        
        quiz = quiz_result.data[0]
        
        if quiz['status'] != 'ready':
            raise ValueError(f"Quiz is not ready (status: {quiz['status']})")
        
        # Check for existing in_progress attempt
        existing_attempt = supabase.table('quiz_attempts').select('*').eq('quiz_id', quiz_id).eq('user_id', user_id).eq('status', 'in_progress').execute()
        
        if existing_attempt.data:
            logger.info(f"Found existing in-progress attempt: {existing_attempt.data[0]['id']}")
            return existing_attempt.data[0]
        
        # Get total questions
        questions_result = supabase.table('quiz_questions').select('id').eq('quiz_id', quiz_id).execute()
        total_questions = len(questions_result.data) if questions_result.data else quiz['num_questions']
        
        # Create attempt
        attempt_data = {
            'quiz_id': quiz_id,
            'user_id': user_id,
            'started_at': datetime.utcnow().isoformat(),
            'status': 'in_progress',
            'total_questions': total_questions
        }
        
        attempt_result = supabase.table('quiz_attempts').insert(attempt_data).execute()
        
        if not attempt_result.data:
            raise ValueError("Failed to create attempt")
        
        attempt = attempt_result.data[0]
        
        # Create answer records for all questions (initially unanswered)
        questions_result = supabase.table('quiz_questions').select('id').eq('quiz_id', quiz_id).order('question_number').execute()
        
        if questions_result.data:
            answer_records = []
            for question in questions_result.data:
                answer_records.append({
                    'attempt_id': attempt['id'],
                    'question_id': question['id'],
                    'selected_answer': None,
                    'is_correct': None
                })
            
            if answer_records:
                supabase.table('quiz_answers').insert(answer_records).execute()
        
        logger.info(f"Created attempt {attempt['id']} for quiz {quiz_id}")
        return attempt
        
    except Exception as e:
        logger.error(f"Error creating attempt: {str(e)}")
        raise


async def submit_answer(attempt_id: str, question_id: str, selected_answer: int, user_id: str, time_spent_seconds: int | None = None) -> dict[str, Any]:
    """
    Submit an answer for a question in an attempt.
    
    Args:
        attempt_id: ID of the attempt
        question_id: ID of the question
        selected_answer: Index of selected option (0-3)
        user_id: ID of the user (for authorization)
        time_spent_seconds: Optional time spent on this question
        
    Returns:
        Dictionary with updated answer data
    """
    supabase = get_supabase()
    
    try:
        # Verify attempt belongs to user and is in progress
        attempt_result = supabase.table('quiz_attempts').select('*').eq('id', attempt_id).eq('user_id', user_id).execute()
        
        if not attempt_result.data:
            raise ValueError("Attempt not found or access denied")
        
        attempt = attempt_result.data[0]
        
        if attempt['status'] != 'in_progress':
            raise ValueError(f"Cannot submit answer for attempt with status: {attempt['status']}")
        
        # Validate selected_answer
        if selected_answer < 0 or selected_answer > 3:
            raise ValueError("selected_answer must be between 0 and 3")
        
        # Get question to check correct answer
        question_result = supabase.table('quiz_questions').select('*').eq('id', question_id).execute()
        
        if not question_result.data:
            raise ValueError("Question not found")
        
        question = question_result.data[0]
        
        # Check if answer record exists
        answer_result = supabase.table('quiz_answers').select('*').eq('attempt_id', attempt_id).eq('question_id', question_id).execute()
        
        is_correct = (selected_answer == question['correct_answer'])
        
        if answer_result.data:
            # Update existing answer
            answer_data = {
                'selected_answer': selected_answer,
                'is_correct': is_correct,
                'answered_at': datetime.utcnow().isoformat()
            }
            
            if time_spent_seconds is not None:
                answer_data['time_spent_seconds'] = time_spent_seconds
            
            updated = supabase.table('quiz_answers').update(answer_data).eq('id', answer_result.data[0]['id']).execute()
            
            if updated.data:
                return updated.data[0]
            else:
                raise ValueError("Failed to update answer")
        else:
            # Create new answer record
            answer_data = {
                'attempt_id': attempt_id,
                'question_id': question_id,
                'selected_answer': selected_answer,
                'is_correct': is_correct,
                'answered_at': datetime.utcnow().isoformat()
            }
            
            if time_spent_seconds is not None:
                answer_data['time_spent_seconds'] = time_spent_seconds
            
            created = supabase.table('quiz_answers').insert(answer_data).execute()
            
            if created.data:
                return created.data[0]
            else:
                raise ValueError("Failed to create answer")
        
    except Exception as e:
        logger.error(f"Error submitting answer: {str(e)}")
        raise


async def complete_attempt(attempt_id: str, user_id: str, time_spent_seconds: int | None = None) -> dict[str, Any]:
    """
    Complete a quiz attempt and calculate score.
    
    Args:
        attempt_id: ID of the attempt
        user_id: ID of the user (for authorization)
        time_spent_seconds: Total time spent (if not provided, calculated from started_at)
        
    Returns:
        Dictionary with completed attempt data including score
    """
    supabase = get_supabase()
    
    try:
        # Verify attempt belongs to user
        attempt_result = supabase.table('quiz_attempts').select('*').eq('id', attempt_id).eq('user_id', user_id).execute()
        
        if not attempt_result.data:
            raise ValueError("Attempt not found or access denied")
        
        attempt = attempt_result.data[0]
        
        if attempt['status'] not in ['in_progress', 'timeout']:
            raise ValueError(f"Cannot complete attempt with status: {attempt['status']}")
        
        # Calculate time spent if not provided
        if time_spent_seconds is None:
            started_at_str = attempt['started_at']
            # Handle timezone-aware and naive datetime strings
            if started_at_str.endswith('Z'):
                started_at_str = started_at_str[:-1] + '+00:00'
            try:
                started_at = datetime.fromisoformat(started_at_str)
                if started_at.tzinfo is not None:
                    started_at = started_at.replace(tzinfo=None)
            except ValueError:
                # Fallback for different formats
                started_at = datetime.utcnow()
            completed_at = datetime.utcnow()
            time_spent_seconds = int((completed_at - started_at).total_seconds())
        
        # Get all answers for this attempt
        answers_result = supabase.table('quiz_answers').select('*').eq('attempt_id', attempt_id).execute()
        
        answers = answers_result.data if answers_result.data else []
        
        # Calculate score
        correct_count = sum(1 for answer in answers if answer.get('is_correct') is True)
        total_questions = attempt['total_questions']
        percentage_score = (correct_count / total_questions * 100) if total_questions > 0 else 0
        
        # Update attempt
        update_data = {
            'status': 'completed',
            'completed_at': datetime.utcnow().isoformat(),
            'time_spent_seconds': time_spent_seconds,
            'score': correct_count,
            'percentage_score': round(percentage_score, 2)
        }
        
        updated = supabase.table('quiz_attempts').update(update_data).eq('id', attempt_id).execute()
        
        if not updated.data:
            raise ValueError("Failed to update attempt")
        
        logger.info(f"Completed attempt {attempt_id}: {correct_count}/{total_questions} correct ({percentage_score:.2f}%)")
        
        return updated.data[0]
        
    except Exception as e:
        logger.error(f"Error completing attempt: {str(e)}")
        raise


async def abandon_attempt(attempt_id: str, user_id: str) -> dict[str, Any]:
    """
    Mark an attempt as abandoned.
    
    Args:
        attempt_id: ID of the attempt
        user_id: ID of the user (for authorization)
        
    Returns:
        Dictionary with updated attempt data
    """
    supabase = get_supabase()
    
    try:
        # Verify attempt belongs to user
        attempt_result = supabase.table('quiz_attempts').select('*').eq('id', attempt_id).eq('user_id', user_id).execute()
        
        if not attempt_result.data:
            raise ValueError("Attempt not found or access denied")
        
        attempt = attempt_result.data[0]
        
        if attempt['status'] == 'completed':
            raise ValueError("Cannot abandon a completed attempt")
        
        # Calculate time spent
        started_at_str = attempt['started_at']
        # Handle timezone-aware and naive datetime strings
        if started_at_str.endswith('Z'):
            started_at_str = started_at_str[:-1] + '+00:00'
        try:
            started_at = datetime.fromisoformat(started_at_str)
            if started_at.tzinfo is not None:
                started_at = started_at.replace(tzinfo=None)
        except ValueError:
            # Fallback for different formats
            started_at = datetime.utcnow()
        abandoned_at = datetime.utcnow()
        time_spent_seconds = int((abandoned_at - started_at).total_seconds())
        
        # Update attempt
        update_data = {
            'status': 'abandoned',
            'time_spent_seconds': time_spent_seconds,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        updated = supabase.table('quiz_attempts').update(update_data).eq('id', attempt_id).execute()
        
        if not updated.data:
            raise ValueError("Failed to update attempt")
        
        logger.info(f"Abandoned attempt {attempt_id}")
        
        return updated.data[0]
        
    except Exception as e:
        logger.error(f"Error abandoning attempt: {str(e)}")
        raise


async def get_attempt(attempt_id: str, user_id: str, include_answers: bool = True) -> dict[str, Any] | None:
    """
    Get attempt details with answers.
    
    Args:
        attempt_id: ID of the attempt
        user_id: ID of the user (for authorization)
        include_answers: Whether to include answer details
        
    Returns:
        Dictionary with attempt data and answers, or None if not found
    """
    supabase = get_supabase()
    
    try:
        # Get attempt
        attempt_result = supabase.table('quiz_attempts').select('*').eq('id', attempt_id).eq('user_id', user_id).execute()
        
        if not attempt_result.data:
            return None
        
        attempt = attempt_result.data[0]
        
        if include_answers:
            # Get answers
            answers_result = supabase.table('quiz_answers').select('*').eq('attempt_id', attempt_id).execute()
            attempt['answers'] = answers_result.data if answers_result.data else []
        
        return attempt
        
    except Exception as e:
        logger.error(f"Error getting attempt: {str(e)}")
        raise


async def get_user_attempts(quiz_id: str | None, user_id: str, status: str | None = None) -> list[dict[str, Any]]:
    """
    Get all attempts for a user, optionally filtered by quiz and status.
    
    Args:
        quiz_id: Optional quiz ID to filter by
        user_id: ID of the user
        status: Optional status to filter by
        
    Returns:
        List of attempt dictionaries
    """
    supabase = get_supabase()
    
    try:
        query = supabase.table('quiz_attempts').select('*').eq('user_id', user_id)
        
        if quiz_id:
            query = query.eq('quiz_id', quiz_id)
        
        if status:
            query = query.eq('status', status)
        
        query = query.order('started_at', desc=False)
        
        result = query.execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        logger.error(f"Error getting user attempts: {str(e)}")
        return []

