from sentence_transformers import SentenceTransformer

sentences = ["Cat", "Dog" , "Lion"]

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
embeddings = model.encode(sentences)
print(embeddings)

print("pairwise similarity: ", model.similarity(embeddings[0], embeddings[1]))
print("pairwise similarity: ", model.similarity(embeddings[0], embeddings[2]))
print("pairwise similarity: ", model.similarity(embeddings[1], embeddings[2]))
