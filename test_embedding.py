import sys
import os
from pathlib import Path

# Add the parent directory to the path if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embeddings import get_embedding_sync  # Adjust import path as needed


def main():
    """Test the get_embedding_sync function"""
    
    # Test cases
    test_texts = [
        "Hello, world!",
      
    ]
    
    print("Testing get_embedding_sync function...\n")
    
    successful_tests = 0
    failed_tests = 0
    
    for i, text in enumerate(test_texts, 1):
        print(f"Test {i}: Testing with text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        
        try:
            # Call the embedding function
            embedding = get_embedding_sync(text)
            
            # Validate the result
            if isinstance(embedding, list) and len(embedding) > 0:
                print(f"✓ Success! Generated embedding of length: {len(embedding)}")
                print(f"  First 5 values: {embedding[:5]}")
                print(f"  All values are floats: {all(isinstance(x, (int, float)) for x in embedding)}")
                successful_tests += 1
            else:
                print(f"✗ Failed: Invalid embedding format or empty list")
                failed_tests += 1
                
        except Exception as e:
            print(f"✗ Error occurred: {type(e).__name__}: {str(e)}")
            failed_tests += 1
            
        print("-" * 50)
    
    # Summary
    print("\n" + "=" * 50)
    print(f"SUMMARY:")
    print(f"Total tests: {len(test_texts)}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {failed_tests}")
    print("=" * 50)
    
    # Additional consistency test
    print("\nConsistency Test:")
    test_text = "Consistency test string"
    try:
        embedding1 = get_embedding_sync(test_text)
        embedding2 = get_embedding_sync(test_text)
        
        if embedding1 == embedding2:
            print("✓ Embeddings are consistent for the same input")
        else:
            print("✗ Warning: Embeddings differ for the same input")
            # Calculate similarity
            import math
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            norm1 = math.sqrt(sum(a * a for a in embedding1))
            norm2 = math.sqrt(sum(b * b for b in embedding2))
            cosine_similarity = dot_product / (norm1 * norm2)
            print(f"  Cosine similarity: {cosine_similarity:.6f}")
            
    except Exception as e:
        print(f"✗ Consistency test failed: {e}")
    
    # Performance test
    print("\nPerformance Test:")
    import time
    test_text = "Performance test string"
    try:
        start_time = time.time()
        for _ in range(5):
            _ = get_embedding_sync(test_text)
        end_time = time.time()
        avg_time = (end_time - start_time) / 5
        print(f"✓ Average time per embedding: {avg_time:.3f} seconds")
    except Exception as e:
        print(f"✗ Performance test failed: {e}")


if __name__ == "__main__":
    main()