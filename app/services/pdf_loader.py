from langchain.schema import Document
from PyPDF2 import PdfReader


def extract_text_from_pdf(file_path: str) -> list[Document]:
    reader = PdfReader(file_path)
    documents = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            documents.append(Document(
                page_content=text,
                metadata={"source": file_path, "page": i + 1}
            ))
    return documents




# def extract_text_from_pdf(file_path: str) -> str:
#     reader = PdfReader(file_path)
#     text = ""
#     for page in reader.pages:
#         text += page.extract_text() or ""
#     return text
