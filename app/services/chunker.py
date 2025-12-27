from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", ".", " ", ""],  # Tries to split on natural boundaries
    )
    return text_splitter.split_text(text)

# def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100):
#     chunks = []
#     start = 0
#     while start < len(text):
#         end = min(start + chunk_size, len(text))
#         # print(f"Chunk from {start} to {end}")
#         chunks.append(text[start:end])
#         start += chunk_size - overlap
#     return chunks
