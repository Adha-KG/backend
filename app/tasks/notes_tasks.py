"""Notes processing tasks for unified backend"""
from celery import Task
from typing import List, Dict, Any
import os
import time
from datetime import datetime

from app.celery_app import celery
from app.services.notes_db import notes_db as db
from app.services.notes_llm import llm_service
from app.services.vectorstore import get_collection
from app.config import settings
from app.utils.file_utils import save_note_as_markdown, get_note_filename


class CallbackTask(Task):
    """Base task with error handling"""
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        note_id = args[0] if args else kwargs.get('note_id')
        if note_id:
            db.update_note_status(
                note_id,
                status='failed',
                error=str(exc)
            )


@celery.task(bind=True, base=CallbackTask, acks_late=True, max_retries=3)
def generate_notes_task(
    self,
    note_id: str,
    document_ids: List[str],
    note_style: str = "moderate",
    user_prompt: str = None,
    collection_name: str = None,
    user_id: str = None
):
    """
    Main task to generate notes from documents.

    This task retrieves chunks from the unified ChromaDB collection (same as RAG/Chat),
    summarizes each chunk, and synthesizes them into comprehensive notes.

    Args:
        note_id: Unique note identifier
        document_ids: List of document IDs to generate notes from
        note_style: Style of notes ('short', 'moderate', or 'descriptive')
        user_prompt: Optional custom instructions
        collection_name: ChromaDB collection name (e.g., 'user_{user_id}_docs')
        user_id: User ID for ownership context
    """
    try:
        # Update status to retrieving
        db.update_note_status(note_id, 'retrieving')
        self.update_state(state='PROGRESS', meta={'step': 'retrieving_chunks'})

        # Step 1: Retrieve chunks from ChromaDB for all document_ids
        collection = get_collection(collection_name)
        all_chunks = []

        for doc_id in document_ids:
            try:
                # Query ChromaDB for chunks with this document_id
                # Using the underlying ChromaDB collection's get method
                results = collection._collection.get(
                    where={"document_id": doc_id},
                    include=["documents", "metadatas"]
                )

                if results and results.get("documents"):
                    for i, doc_text in enumerate(results["documents"]):
                        chunk_index = i
                        if results.get("metadatas") and i < len(results["metadatas"]):
                            chunk_index = results["metadatas"][i].get("chunk_index", i)

                        all_chunks.append({
                            "text": doc_text,
                            "document_id": doc_id,
                            "chunk_index": chunk_index,
                            "chroma_id": results["ids"][i] if results.get("ids") and i < len(results["ids"]) else None
                        })
            except Exception as e:
                print(f"Warning: Error retrieving chunks for document {doc_id}: {e}")
                continue

        if not all_chunks:
            raise ValueError(
                f"No chunks found for the specified documents. "
                f"Make sure the documents have been processed and are available in the collection '{collection_name}'."
            )

        # Sort chunks by document_id and chunk_index to maintain order
        all_chunks.sort(key=lambda x: (x["document_id"], x["chunk_index"]))

        print(f"Retrieved {len(all_chunks)} raw chunks from {len(document_ids)} documents")

        # Merge small chunks into larger ones for more efficient note generation
        # Target ~4000 chars per merged chunk (reduces API calls significantly)
        TARGET_CHUNK_SIZE = 10000
        merged_chunks = []
        current_text = ""
        current_doc_id = None
        current_start_idx = 0

        for chunk in all_chunks:
            # If switching documents or chunk would be too large, save current and start new
            if current_doc_id != chunk["document_id"] or len(current_text) + len(chunk["text"]) > TARGET_CHUNK_SIZE:
                if current_text:
                    merged_chunks.append({
                        "text": current_text.strip(),
                        "document_id": current_doc_id,
                        "chunk_index": current_start_idx,
                        "chroma_id": None  # Merged chunks don't have a single chroma_id
                    })
                current_text = chunk["text"]
                current_doc_id = chunk["document_id"]
                current_start_idx = chunk["chunk_index"]
            else:
                current_text += "\n\n" + chunk["text"]

        # Don't forget the last chunk
        if current_text:
            merged_chunks.append({
                "text": current_text.strip(),
                "document_id": current_doc_id,
                "chunk_index": current_start_idx,
                "chroma_id": None
            })

        # Use merged chunks for processing
        all_chunks = merged_chunks
        print(f"Merged into {len(all_chunks)} chunks for note generation (target: {TARGET_CHUNK_SIZE} chars each)")

        # Step 2: Summarize chunks
        db.update_note_status(note_id, 'summarizing')
        summaries = []
        total_tokens = 0
        successful_summaries = 0
        failed_summaries = 0

        for i, chunk in enumerate(all_chunks):
            self.update_state(
                state='PROGRESS',
                meta={
                    'step': 'summarizing_chunks',
                    'current': i + 1,
                    'total': len(all_chunks)
                }
            )

            # Generate summary for chunk with specified style
            try:
                result = llm_service.generate_summary(
                    chunk["text"],
                    note_style=note_style,
                    user_prompt=user_prompt
                )

                # Validate that result contains required fields
                if not result or not result.get('text'):
                    raise ValueError(f"LLM service returned empty result for chunk {i}")

                # Store summary in database
                summary_data = {
                    'note_id': note_id,
                    'document_id': chunk["document_id"],
                    'chroma_chunk_id': chunk["chroma_id"],
                    'chunk_index': chunk["chunk_index"],
                    'summary_text': result['text'],
                    'llm_provider': result.get('provider', 'unknown'),
                    'llm_model': result.get('model', 'unknown'),
                    'tokens_used': result.get('tokens_used', 0)
                }
                db.create_summary(summary_data)

                summaries.append(result['text'])
                total_tokens += result.get('tokens_used', 0)
                successful_summaries += 1

                # Rate limiting: Gemini free tier allows 10 requests/minute for Flash, 2 for Pro
                if llm_service.provider == "gemini" and i < len(all_chunks) - 1:
                    model_name = settings.gemini_model.lower()
                    if "flash" in model_name:
                        delay = 7
                    else:
                        delay = 45
                    print(f"Rate limiting: waiting {delay} seconds before processing next chunk...")
                    time.sleep(delay)

            except Exception as e:
                failed_summaries += 1
                error_msg = f"Error summarizing chunk {i}: {str(e)}"
                print(error_msg)

                # Fallback for safety blocks: extract key sentences from the chunk
                if "SAFETY" in str(e) or "blocked" in str(e).lower():
                    try:
                        sentences = chunk["text"].split('.')
                        key_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:3]
                        if key_sentences:
                            fallback_summary = ". ".join(key_sentences) + "."
                            print(f"Using fallback summary for chunk {i} due to safety block")

                            summary_data = {
                                'note_id': note_id,
                                'document_id': chunk["document_id"],
                                'chroma_chunk_id': chunk["chroma_id"],
                                'chunk_index': chunk["chunk_index"],
                                'summary_text': f"[Fallback] {fallback_summary}",
                                'llm_provider': 'fallback',
                                'llm_model': 'extractive',
                                'tokens_used': 0
                            }
                            db.create_summary(summary_data)
                            summaries.append(fallback_summary)
                            successful_summaries += 1
                            continue
                    except Exception as fallback_error:
                        print(f"Fallback extraction also failed: {fallback_error}")

                # Handle rate limit errors
                error_str = str(e).lower()
                if llm_service.provider == "gemini" and ("429" in error_str or "quota" in error_str or "rate limit" in error_str):
                    if i < len(all_chunks) - 1:
                        import re
                        model_name = settings.gemini_model.lower()
                        delay = 60 if "flash" in model_name else 90

                        delay_patterns = [
                            r'retry\s+in\s+(\d+(?:\.\d+)?)\s*s\.?',
                            r'retry\s+in\s+(\d+(?:\.\d+)?)',
                            r'(\d+(?:\.\d+)?)\s*seconds',
                        ]
                        for pattern in delay_patterns:
                            delay_match = re.search(pattern, str(e), re.IGNORECASE)
                            if delay_match:
                                extracted_delay = float(delay_match.group(1))
                                delay = max(extracted_delay + 10, 40)
                                break

                        print(f"Rate limit error, waiting {delay:.1f} seconds...")
                        time.sleep(delay)

        # Only proceed to synthesis if we have summaries
        if successful_summaries == 0:
            raise ValueError(
                f"Failed to create any summaries. "
                f"All {failed_summaries} chunks failed to summarize. "
                f"Check LLM service configuration and API keys."
            )

        # Step 3: Synthesize final notes
        db.update_note_status(note_id, 'synthesizing')
        self.update_state(state='PROGRESS', meta={'step': 'synthesizing'})

        # For hierarchical synthesis with many summaries, do it in stages
        if len(summaries) > 20:
            intermediate_summaries = []
            for i in range(0, len(summaries), 10):
                group = summaries[i:i+10]
                result = llm_service.synthesize_notes(group, note_style, user_prompt)
                intermediate_summaries.append(result['text'])

            final_result = llm_service.synthesize_notes(intermediate_summaries, note_style, user_prompt)
        else:
            final_result = llm_service.synthesize_notes(summaries, note_style, user_prompt)

        # Update note with final content
        metadata = {
            'total_chunks': len(all_chunks),
            'total_documents': len(document_ids),
            'summaries_created': successful_summaries,
            'synthesis_method': 'hierarchical' if len(summaries) > 20 else 'direct',
            'note_style': note_style,
            'llm_provider': final_result.get('provider'),
            'llm_model': final_result.get('model'),
            'tokens_used': total_tokens + final_result.get('tokens_used', 0)
        }

        db.update_note_content(note_id, final_result['text'], metadata)

        # Save note as markdown file locally if enabled
        if settings.save_notes_locally:
            try:
                # Get note record to include in filename
                note_record = db.get_note(note_id)
                title = note_record.get('title', '') if note_record else ''

                # Generate markdown filename
                md_filename = f"note_{note_id[:8]}_{title or 'untitled'}.md".replace(' ', '_')
                md_file_path = os.path.join(settings.notes_dir, md_filename)

                # Ensure notes directory exists
                os.makedirs(settings.notes_dir, exist_ok=True)

                # Prepare metadata for frontmatter
                frontmatter_metadata = {
                    'note_id': note_id,
                    'title': title,
                    'document_ids': document_ids,
                    'note_style': note_style,
                    'llm_provider': final_result.get('provider'),
                    'llm_model': final_result.get('model'),
                    'tokens_used': metadata['tokens_used'],
                }

                save_note_as_markdown(
                    note_text=final_result['text'],
                    output_path=md_file_path,
                    metadata=frontmatter_metadata
                )
                print(f"Note saved locally as markdown: {md_file_path}")
            except Exception as e:
                print(f"Warning: Failed to save note locally as markdown: {str(e)}")

        return {
            'status': 'completed',
            'note_id': note_id,
            'chunks_processed': len(all_chunks),
            'summaries_created': successful_summaries,
            'tokens_used': metadata['tokens_used']
        }

    except Exception as e:
        db.update_note_status(note_id, 'failed', error=str(e))
        raise


@celery.task(bind=True, acks_late=True)
def cleanup_old_notes_task(self, days_old: int = 30):
    """
    Cleanup task to remove old notes.

    Args:
        days_old: Remove notes older than this many days
    """
    # This would be run periodically via Celery Beat
    # Implementation depends on your cleanup policy
    pass
