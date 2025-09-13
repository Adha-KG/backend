# test_chromadb_connection.py
import logging
import chromadb
from chromadb.config import Settings
import time

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_chromadb_basic():
    """Test basic ChromaDB operations"""
    logger.info("Starting ChromaDB test...")
    
    try:
        # Test 1: Create client
        start = time.time()
        client = chromadb.PersistentClient(path="./chroma_db")
        logger.info(f"✓ Client created in {time.time() - start:.2f}s")
        
        # Test 2: List collections
        collections = client.list_collections()
        logger.info(f"✓ Found {len(collections)} collections")
        
        # Test 3: Get or create collection
        start = time.time()
        collection = client.get_or_create_collection("pdf_embeddings")
        logger.info(f"✓ Collection accessed in {time.time() - start:.2f}s")
        
        # Test 4: Count documents
        count = collection.count()
        logger.info(f"✓ Collection has {count} documents")
        
        # Test 5: Add a test document
        collection.add(
            documents=["test"],
            embeddings=[[0.1] * 768],
            ids=["test_" + str(int(time.time()))]
        )
        logger.info("✓ Successfully added test document")
        
        # Test 6: Query
        results = collection.query(
            query_embeddings=[[0.1] * 768],
            n_results=1
        )
        logger.info(f"✓ Query successful: {len(results['documents'][0])} results")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ ChromaDB test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    test_chromadb_basic()