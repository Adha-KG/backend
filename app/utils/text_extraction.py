import fitz  # PyMuPDF
import pdfplumber
from typing import List, Dict, Any
import re


def extract_text_pymupdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract text from PDF using PyMuPDF.
    Returns list of dicts with page number and text.
    """
    doc = fitz.open(file_path)
    pages_data = []
    
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        pages_data.append({
            'page_number': page_num,
            'text': text,
            'char_count': len(text)
        })
    
    doc.close()
    return pages_data


def extract_text_pdfplumber(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract text from PDF using pdfplumber (better for tables).
    Returns list of dicts with page number and text.
    """
    pages_data = []
    
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages_data.append({
                'page_number': page_num,
                'text': text,
                'char_count': len(text)
            })
    
    return pages_data


def clean_text(text: str) -> str:
    """
    Clean extracted text by removing headers, footers, and extra whitespace.
    """
    # Remove multiple spaces
    text = re.sub(r' +', ' ', text)
    
    # Remove multiple newlines (keep max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove page numbers (simple pattern)
    text = re.sub(r'\n\d+\n', '\n', text)
    
    # Remove common header/footer patterns (customize as needed)
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def extract_text_from_pdf(file_path: str, method: str = "pymupdf") -> str:
    """
    Main function to extract text from PDF.
    
    Args:
        file_path: Path to PDF file
        method: 'pymupdf' or 'pdfplumber'
    
    Returns:
        Cleaned text string
    """
    if method == "pdfplumber":
        pages_data = extract_text_pdfplumber(file_path)
    else:
        pages_data = extract_text_pymupdf(file_path)
    
    # Combine all pages
    full_text = "\n\n".join(page['text'] for page in pages_data)
    
    # Clean the text
    cleaned_text = clean_text(full_text)
    
    return cleaned_text


def get_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from PDF.
    """
    doc = fitz.open(file_path)
    metadata = {
        'page_count': len(doc),
        'title': doc.metadata.get('title', ''),
        'author': doc.metadata.get('author', ''),
        'subject': doc.metadata.get('subject', ''),
        'creator': doc.metadata.get('creator', ''),
    }
    doc.close()
    return metadata
