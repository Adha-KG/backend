"""Celery tasks for unified backend - RAG and Notes"""

# Import RAG tasks
from app.tasks.rag_tasks import process_pdf

# Notes tasks are in notes_tasks.py and auto-discovered by Celery
# They don't need to be imported here as Celery discovers them via celery_app.py include

__all__ = ["process_pdf"]
