# app/services/chat_service.py
from datetime import datetime, timedelta
from typing import Any

from app.auth.supabase_client import get_supabase


async def create_chat_session(user_id: str, session_name: str = None,
                            session_type: str = 'general',
                            document_ids: list[str] = None) -> dict[str, Any]:
    """Create a new chat session"""
    supabase = get_supabase()
    try:
        session = supabase.table('chat_sessions').insert({
            'user_id': user_id,
            'session_name': session_name,
            'session_type': session_type,
            'document_ids': document_ids or [],
            'is_active': True
        }).execute()
        return session.data[0]
    except Exception as e:
        print(f"Error creating chat session: {e}")
        raise

async def get_user_chat_sessions(user_id: str) -> list[dict[str, Any]]:
    """Get all chat sessions for a user"""
    supabase = get_supabase()
    try:
        result = supabase.table('chat_sessions').select('*').eq('user_id', user_id).eq('is_active', True).order('updated_at', desc=True).execute()
        return result.data
    except Exception as e:
        print(f"Error getting chat sessions: {e}")
        return []

async def get_session_by_id(session_id: str) -> dict[str, Any] | None:
    """Get a specific chat session by ID"""
    supabase = get_supabase()
    try:
        result = supabase.table('chat_sessions').select('*').eq('id', session_id).eq('is_active', True).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting session by ID: {e}")
        return None

async def get_or_create_active_session(user_id: str) -> dict[str, Any]:
    """Get user's most recent active session or create a new one (ChatGPT-like behavior)"""
    try:
        # Get user's sessions ordered by last activity
        sessions = await get_user_chat_sessions(user_id)

        # If user has an active session with recent activity (last 24 hours), use it
        # Otherwise create a new session
        active_session = None

        if sessions:
            # Get the most recent session
            latest_session = sessions[0]  # Already ordered by updated_at DESC
            # Check if it was active in the last 24 hours
            if latest_session.get('updated_at'):
                try:
                    # Handle different datetime formats from Supabase
                    last_update_str = latest_session['updated_at']
                    if 'T' in last_update_str:
                        # ISO format: 2023-10-27T14:30:00+00:00 or 2023-10-27T14:30:00Z
                        last_update_str = last_update_str.replace('Z', '+00:00')
                        last_update = datetime.fromisoformat(last_update_str)
                    else:
                        # Other format handling if needed
                        last_update = datetime.fromisoformat(last_update_str)
                    # Check if session was active in last 24 hours
                    now = datetime.now(last_update.tzinfo) if last_update.tzinfo else datetime.now()
                    if now - last_update < timedelta(hours=24):
                        active_session = latest_session
                        print(f"Using existing active session: {active_session['id']}")
                    else:
                        print(f"Last session too old ({now - last_update}), creating new session")
                except Exception as date_error:
                    print(f"Error parsing date: {date_error}, creating new session")
        # Create new session if no active session found
        if not active_session:
            session_name = f"Chat - {datetime.now().strftime('%m/%d %H:%M')}"
            active_session = await create_chat_session(
                user_id=user_id,
                session_name=session_name,
                session_type="conversation",
                document_ids=[]
            )
            print(f"Created new chat session {active_session['id']} for user {user_id}")
        return active_session
    except Exception as e:
        print(f"Error getting/creating active session: {e}")
        raise

async def get_or_create_default_session(user_id: str) -> dict[str, Any]:
    """Get user's default session or create one if it doesn't exist"""
    try:
        # Try to get user's existing default session
        sessions = await get_user_chat_sessions(user_id)
        # Look for a default session
        default_session = None
        for session in sessions:
            if (session.get('session_type') == 'default' or
                session.get('session_name') == 'Default Chat' or
                session.get('session_type') == 'general'):
                default_session = session
                break
        # If no default session exists, create one
        if not default_session:
            print(f"Creating default session for user {user_id}")
            default_session = await create_chat_session(
                user_id=user_id,
                session_name="Default Chat",
                session_type="default",
                document_ids=[]
            )
        return default_session
    except Exception as e:
        print(f"Error getting/creating default session: {e}")
        raise

async def add_chat_message(session_id: str, content: str,
                         tokens_used: int = None,
                         source_documents: list[dict] = None,
                         retrieval_query: str = None) -> dict[str, Any]:
    """Add a message to a chat session"""
    supabase = get_supabase()
    try:
        # Get current message count
        session_result = supabase.table('chat_sessions').select('message_count').eq('id', session_id).execute()
        current_count = session_result.data[0]['message_count'] if session_result.data else 0

        # Insert message
        message = supabase.table('chat_messages').insert({
            'session_id': session_id,
            'content': content,
            'tokens_used': tokens_used,
            'source_documents': source_documents,
            'retrieval_query': retrieval_query,
            'sequence_number': current_count + 1
        }).execute()

        # Update session
        supabase.table('chat_sessions').update({
            'message_count': current_count + 1,
            'updated_at': 'now()',
            'last_message_at': 'now()'
        }).eq('id', session_id).execute()

        return message.data[0]
    except Exception as e:
        print(f"Error adding chat message: {e}")
        raise

async def get_chat_messages(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Get messages for a chat session"""
    supabase = get_supabase()
    try:
        result = supabase.table('chat_messages').select('*').eq('session_id', session_id).order('sequence_number', desc=True).limit(limit).execute()
        return list(reversed(result.data))  # Return in chronological order
    except Exception as e:
        print(f"Error getting chat messages: {e}")
        return []

async def update_session_name(session_id: str, user_id: str, new_name: str) -> bool:
    """Update a chat session's name"""
    supabase = get_supabase()
    try:
        result = supabase.table('chat_sessions').update({
            'session_name': new_name,
            'updated_at': 'now()'
        }).eq('id', session_id).eq('user_id', user_id).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"Error updating session name: {e}")
        return False

async def delete_chat_session(session_id: str, user_id: str) -> bool:
    """Delete a chat session (soft delete by setting is_active=False)"""
    supabase = get_supabase()
    try:
        result = supabase.table('chat_sessions').update({'is_active': False}).eq('id', session_id).eq('user_id', user_id).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"Error deleting chat session: {e}")
        return False

async def get_session_summary(session_id: str) -> dict[str, Any]:
    """Get summary information about a chat session"""
    supabase = get_supabase()
    try:
        # Get session info
        session_result = supabase.table('chat_sessions').select('*').eq('id', session_id).execute()
        if not session_result.data:
            return None
        session = session_result.data[0]

        # Get message count and latest message
        messages_result = supabase.table('chat_messages').select('content, created_at').eq('session_id', session_id).order('sequence_number', desc=True).limit(1).execute()

        latest_message = messages_result.data[0] if messages_result.data else None

        return {
            'session_id': session['id'],
            'session_name': session['session_name'],
            'session_type': session['session_type'],
            'message_count': session['message_count'],
            'created_at': session['created_at'],
            'updated_at': session['updated_at'],
            'last_message_at': session['last_message_at'],
            'latest_message_preview': latest_message['content'][:100] + '...' if latest_message and len(latest_message['content']) > 100 else latest_message['content'] if latest_message else None,
            'is_active': session['is_active']
        }
    except Exception as e:
        print(f"Error getting session summary: {e}")
        return None

async def search_chat_sessions(user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search through user's chat sessions by session name or message content"""
    supabase = get_supabase()
    try:
        # Search in session names first
        sessions_result = supabase.table('chat_sessions').select('*').eq('user_id', user_id).eq('is_active', True).ilike('session_name', f'%{query}%').order('updated_at', desc=True).limit(limit).execute()

        # You could also search in message content if needed
        # This would be more complex and might require full-text search setup

        return sessions_result.data
    except Exception as e:
        print(f"Error searching chat sessions: {e}")
        return []
