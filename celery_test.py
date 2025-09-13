# test_celery_basic.py
from app.celery_app import celery
import logging

from app.services.embeddings import get_embedding
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@celery.task(bind=True)
def test_basic_task(self):
    """Basic test task"""
    logger.info("Test task started")
    
    # Update state
    self.update_state(state="PROGRESS", meta={"status": "working"})
    
    # Test ChromaDB in Celery context
    try:
        from app.services.vectorstore import get_collection
        collection = get_collection()
        count = collection.count()
        logger.info(f"ChromaDB accessed from Celery: {count} documents")

        # Test embedding function
        test_text = "Hello, world!"
        embedding = get_embedding(test_text)
        logger.info(f"Generated embedding from Celery: {embedding}")
        embedding_String = "Hello, world!"
        embedding = get_embedding(embedding_String)
        logger.info(f"Generated embedding from Celery: {embedding_String}")
    except Exception as e:
        logger.error(f"Failed to access ChromaDB from Celery: {e}")
        raise
    
    return {"status": "success", "message": "Test completed"}

# Run this task
if __name__ == "__main__":
    result = test_basic_task.delay()
    print(f"Task ID: {result.id}")