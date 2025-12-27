"""Shared pytest fixtures and configuration."""
import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def uploads_dir():
    """Get the uploads directory path."""
    return Path("./uploads")


@pytest.fixture
def test_pdf_path(uploads_dir):
    """Get a test PDF path if available."""
    test_pdf = uploads_dir / "5ded9e59-a0dc-4a3c-a49b-158ff98dd0cd_L_18_C_23.pdf"
    if test_pdf.exists():
        return str(test_pdf)

    # Try to find any PDF in uploads
    if uploads_dir.exists():
        pdfs = list(uploads_dir.glob("*.pdf"))
        if pdfs:
            return str(pdfs[0])

    return None

