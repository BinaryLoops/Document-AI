"""
Complete document ingestion pipeline.
P1 implementation: Multi-format support, OCR, status tracking, UUID generation.
"""

import os
import uuid
import logging
import tempfile
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from PIL import Image
import fitz  # PyMuPDF

from document.processor import DocumentProcessor
from document.ocr_processor import OCRProcessor, create_ocr_processor
from document.document_status import DocumentStatus, DocumentMetadata

logger = logging.getLogger(__name__)


class DocumentIngestion:
    """
    Complete document ingestion pipeline with multi-format support.
    Handles: PDF, JPG, JPEG, PNG, DOCX, TXT
    """
    
    # Supported file extensions
    SUPPORTED_FORMATS = {
        '.pdf': 'pdf',
        '.txt': 'text',
        '.docx': 'docx',
        '.doc': 'doc',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.png': 'image',
    }
    
    def __init__(
        self,
        ocr_engine: str = "tesseract",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize document ingestion pipeline.
        
        Args:
            ocr_engine: OCR engine to use ('tesseract' or 'easyocr')
            chunk_size: Chunk size for text processing
            chunk_overlap: Overlap between chunks
        """
        self.ocr_processor = create_ocr_processor(engine_type=ocr_engine)
        self.doc_processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    def ingest_document(
        self,
        file_path: str,
        filename: str,
        source: str = "upload"
    ) -> Tuple[DocumentMetadata, List[str], List[Dict[str, Any]]]:
        """
        Ingest a document through the complete pipeline.
        
        Args:
            file_path: Path to the document file
            filename: Original filename
            source: Source of the document
            
        Returns:
            Tuple of (document_metadata, chunks, chunk_metadata)
        """
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Determine file type
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported file format: {ext}")
        
        file_type = self.SUPPORTED_FORMATS[ext]
        
        # Initialize metadata
        doc_metadata = DocumentMetadata(
            document_id=document_id,
            filename=filename,
            source=source,
            status=DocumentStatus.UPLOADED
        )
        
        try:
            # Update status to processing
            doc_metadata.update_status(DocumentStatus.PROCESSING)
            
            # Extract text based on file type
            if file_type == 'image':
                chunks, chunk_metadata = self._process_image(
                    file_path, document_id, filename
                )
                doc_metadata.page_count = 1
                
            elif file_type == 'pdf':
                chunks, chunk_metadata = self._process_pdf(
                    file_path, document_id, filename
                )
                # Count pages
                doc_metadata.page_count = self._count_pdf_pages(file_path)
                
            else:  # text, docx, doc
                chunks, chunk_metadata = self._process_text_document(
                    file_path, document_id, filename
                )
                doc_metadata.page_count = 1  # Text files don't have clear pages
            
            # Update status to completed
            doc_metadata.update_status(DocumentStatus.COMPLETED)
            
            logger.info(
                f"Successfully ingested document {document_id}: "
                f"{len(chunks)} chunks from {doc_metadata.page_count} pages"
            )
            
            return doc_metadata, chunks, chunk_metadata
            
        except Exception as e:
            doc_metadata.update_status(
                DocumentStatus.FAILED, 
                error_message=str(e)
            )
            logger.error(f"Failed to ingest document {document_id}: {e}")
            raise
    
    def _process_image(
        self,
        file_path: str,
        document_id: str,
        filename: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Process a single image file using OCR.
        
        Args:
            file_path: Path to image file
            document_id: Document UUID
            filename: Original filename
            
        Returns:
            Tuple of (chunks, chunk_metadata)
        """
        logger.info(f"Processing image: {filename}")
        
        # Load image
        image = Image.open(file_path)
        
        # Extract text using OCR
        result = self.ocr_processor.extract_from_image(image, page_number=1)
        
        text = result["text"]
        confidence = result["confidence"]
        
        if not text.strip():
            logger.warning(f"No text extracted from image: {filename}")
            return [], []
        
        # Create chunks from extracted text
        chunks = [text]  # For single images, typically one chunk
        
        chunk_metadata = [{
            "document_id": document_id,
            "filename": filename,
            "page": 1,
            "ocr_confidence": confidence,
            "word_count": result["word_count"],
            "char_count": result["char_count"],
            "is_ocr": True
        }]
        
        return chunks, chunk_metadata
    
    def _process_pdf(
        self,
        file_path: str,
        document_id: str,
        filename: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Process a PDF file (text-native or scanned).
        
        Args:
            file_path: Path to PDF file
            document_id: Document UUID
            filename: Original filename
            
        Returns:
            Tuple of (chunks, chunk_metadata)
        """
        logger.info(f"Processing PDF: {filename}")
        
        # Try to extract text directly first (for text-native PDFs)
        try:
            chunks, chunk_metadata = self.doc_processor.process_file(
                file_path,
                metadata={"document_id": document_id, "filename": filename}
            )
            
            # If we got meaningful text, use it
            if chunks and any(len(chunk.strip()) > 100 for chunk in chunks):
                logger.info(f"Extracted text directly from PDF: {len(chunks)} chunks")
                
                # Add page numbers to metadata
                for i, meta in enumerate(chunk_metadata):
                    meta["page"] = i + 1
                    meta["document_id"] = document_id
                    meta["is_ocr"] = False
                
                return chunks, chunk_metadata
        except Exception as e:
            logger.warning(f"Direct text extraction failed: {e}, trying OCR")
        
        # If direct extraction failed or produced little text, use OCR
        return self._process_pdf_with_ocr(file_path, document_id, filename)
    
    def _process_pdf_with_ocr(
        self,
        file_path: str,
        document_id: str,
        filename: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Process a scanned PDF using OCR on each page.
        
        Args:
            file_path: Path to PDF file
            document_id: Document UUID
            filename: Original filename
            
        Returns:
            Tuple of (chunks, chunk_metadata)
        """
        logger.info(f"Processing PDF with OCR: {filename}")
        
        # Open PDF
        pdf_document = fitz.open(file_path)
        
        all_chunks = []
        all_metadata = []
        
        # Process each page
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Convert page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img_data = pix.tobytes("png")
            
            # Create PIL Image
            import io
            image = Image.open(io.BytesIO(img_data))
            
            # Extract text using OCR
            result = self.ocr_processor.extract_from_image(
                image, 
                page_number=page_num + 1
            )
            
            text = result["text"]
            
            if text.strip():
                all_chunks.append(text)
                all_metadata.append({
                    "document_id": document_id,
                    "filename": filename,
                    "page": page_num + 1,
                    "ocr_confidence": result["confidence"],
                    "word_count": result["word_count"],
                    "is_ocr": True
                })
        
        pdf_document.close()
        
        logger.info(f"Extracted text from {len(all_chunks)} pages via OCR")
        
        return all_chunks, all_metadata
    
    def _process_text_document(
        self,
        file_path: str,
        document_id: str,
        filename: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Process text-based documents (TXT, DOCX, DOC).
        
        Args:
            file_path: Path to document file
            document_id: Document UUID
            filename: Original filename
            
        Returns:
            Tuple of (chunks, chunk_metadata)
        """
        logger.info(f"Processing text document: {filename}")
        
        # Use existing processor
        chunks, chunk_metadata = self.doc_processor.process_file(
            file_path,
            metadata={"document_id": document_id, "filename": filename}
        )
        
        # Add document_id to all metadata
        for meta in chunk_metadata:
            meta["document_id"] = document_id
            meta["is_ocr"] = False
        
        return chunks, chunk_metadata
    
    @staticmethod
    def _count_pdf_pages(file_path: str) -> int:
        """Count pages in a PDF file."""
        try:
            pdf_document = fitz.open(file_path)
            page_count = len(pdf_document)
            pdf_document.close()
            return page_count
        except Exception as e:
            logger.error(f"Failed to count PDF pages: {e}")
            return 0
    
    @staticmethod
    def is_supported_format(filename: str) -> bool:
        """Check if a file format is supported."""
        ext = os.path.splitext(filename)[1].lower()
        return ext in DocumentIngestion.SUPPORTED_FORMATS
    
    @staticmethod
    def get_file_type(filename: str) -> Optional[str]:
        """Get the file type category for a filename."""
        ext = os.path.splitext(filename)[1].lower()
        return DocumentIngestion.SUPPORTED_FORMATS.get(ext)
