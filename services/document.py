import os
import sys
import uuid
import logging
from io import BytesIO
from pathlib import Path
from typing import Dict

# Add parent directory to path to allow importing config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config

from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
)
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

# ---------------------------------------------------------------------------
# Docling converter (cached)
# ---------------------------------------------------------------------------

_converters: Dict[bool, DocumentConverter] = {}

def get_converter(use_ocr: bool = True) -> DocumentConverter:
    """Get or create a cached DocumentConverter instance based on OCR preference."""
    if use_ocr not in _converters:
        pipeline_options = PdfPipelineOptions(
            do_ocr=use_ocr,
            do_table_structure=False,
        )
        if use_ocr:
            # Enable extra options for OCR mode if needed, matching original logic?
            # Original logic just did do_ocr=use_ocr, do_table_structure=False
            # Wait, my previous plan had: 
            # pipeline_options.do_ocr = True
            # pipeline_options.do_table_structure = True
            # pipeline_options.table_structure_options.do_cell_matching = True
            # But the original flask_app.py code inside get_converter was:
            # pipeline_options = PdfPipelineOptions(do_ocr=use_ocr, do_table_structure=False)
            pass

        _converters[use_ocr] = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.ASCIIDOC,
                InputFormat.MD,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    backend=PyPdfiumDocumentBackend,
                    pipeline_options=pipeline_options,
                ),
                InputFormat.DOCX: WordFormatOption(pipeline_cls=SimplePipeline),
                InputFormat.HTML: WordFormatOption(),
                InputFormat.PPTX: WordFormatOption(),
            },
        )
    return _converters[use_ocr]

def convert_document(file_bytes, filename, use_ocr=True):
    """
    Converts a document (PDF, DOCX, HTML, etc.) to Docling structure.
    Returns: ConversionResult or None on failure
    """
    file_ext = os.path.splitext(filename)[1].lower()
    temp_path = os.path.join(config.UPLOAD_FOLDER, f"{uuid.uuid4()}{file_ext}")

    try:
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        converter = get_converter(use_ocr=use_ocr)
        
        # docling can parse from path
        result = converter.convert(
            Path(temp_path),
            max_num_pages=config.MAX_PAGES,
            max_file_size=config.MAX_FILE_SIZE,
        )
        
        return result

    except Exception as e:
        print(f"Error converting document: {e}")
        # Try to cleanup if failed
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        raise e
