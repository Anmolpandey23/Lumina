"""
Text chunking strategies for RAG pipeline
Implements semantic chunking with overlap for better context preservation
"""

import re
from typing import List, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a text chunk with metadata"""
    text: str
    start_idx: int
    end_idx: int
    chunk_id: str
    source: str = "page_content"


class TextChunker:
    """
    Handles text chunking with multiple strategies
    Supports sentence-level, paragraph-level, and semantic chunking
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        strategy: str = "semantic"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy

    def chunk_text(self, text: str, page_url: str = "") -> List[Chunk]:
        """
        Chunk text using specified strategy
        
        Args:
            text: Text to chunk
            page_url: URL for metadata
            
        Returns:
            List of Chunk objects
        """
        if self.strategy == "semantic":
            return self._semantic_chunking(text, page_url)
        elif self.strategy == "paragraph":
            return self._paragraph_chunking(text, page_url)
        elif self.strategy == "sentence":
            return self._sentence_chunking(text, page_url)
        else:
            return self._simple_chunking(text, page_url)

    def _semantic_chunking(self, text: str, page_url: str) -> List[Chunk]:
        """
        Split text into semantic units (sections with headers)
        Preserves context by keeping related content together
        """
        chunks = []
        
        # Split by headers first
        sections = re.split(r'(?=^[A-Z][A-Z ]{5,}:|\n#{1,6}\s)', text, flags=re.MULTILINE)
        
        current_section = ""
        chunk_id = 0
        
        for section in sections:
            if not section.strip():
                continue
                
            # If section is small enough, keep as is
            if len(section) <= self.chunk_size:
                current_section += section
            else:
                # Further split large sections
                if current_section:
                    chunk = Chunk(
                        text=current_section.strip(),
                        start_idx=len(text) - len(current_section),
                        end_idx=len(text),
                        chunk_id=f"{page_url}#chunk_{chunk_id}",
                        source="page_content"
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                    current_section = ""
                
                # Split large section into smaller chunks
                subsections = self._split_by_sentences(section, self.chunk_size)
                for subsection in subsections:
                    if subsection.strip():
                        chunk = Chunk(
                            text=subsection.strip(),
                            start_idx=0,
                            end_idx=len(subsection),
                            chunk_id=f"{page_url}#chunk_{chunk_id}",
                            source="page_content"
                        )
                        chunks.append(chunk)
                        chunk_id += 1
        
        # Add any remaining content
        if current_section.strip():
            chunk = Chunk(
                text=current_section.strip(),
                start_idx=0,
                end_idx=len(current_section),
                chunk_id=f"{page_url}#chunk_{chunk_id}",
                source="page_content"
            )
            chunks.append(chunk)
        
        return chunks

    def _paragraph_chunking(self, text: str, page_url: str) -> List[Chunk]:
        """Split by paragraphs"""
        paragraphs = text.split('\n\n')
        chunks = []
        current_text = ""
        chunk_id = 0
        
        for para in paragraphs:
            if not para.strip():
                continue
                
            if len(current_text) + len(para) <= self.chunk_size:
                current_text += "\n\n" + para if current_text else para
            else:
                if current_text.strip():
                    chunk = Chunk(
                        text=current_text.strip(),
                        start_idx=0,
                        end_idx=len(current_text),
                        chunk_id=f"{page_url}#chunk_{chunk_id}",
                        source="page_content"
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                current_text = para
        
        if current_text.strip():
            chunk = Chunk(
                text=current_text.strip(),
                start_idx=0,
                end_idx=len(current_text),
                chunk_id=f"{page_url}#chunk_{chunk_id}",
                source="page_content"
            )
            chunks.append(chunk)
        
        return chunks

    def _sentence_chunking(self, text: str, page_url: str) -> List[Chunk]:
        """Split by sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_text = ""
        chunk_id = 0
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            if len(current_text) + len(sentence) <= self.chunk_size:
                current_text += " " + sentence if current_text else sentence
            else:
                if current_text.strip():
                    chunk = Chunk(
                        text=current_text.strip(),
                        start_idx=0,
                        end_idx=len(current_text),
                        chunk_id=f"{page_url}#chunk_{chunk_id}",
                        source="page_content"
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                current_text = sentence
        
        if current_text.strip():
            chunk = Chunk(
                text=current_text.strip(),
                start_idx=0,
                end_idx=len(current_text),
                chunk_id=f"{page_url}#chunk_{chunk_id}",
                source="page_content"
            )
            chunks.append(chunk)
        
        return chunks

    def _simple_chunking(self, text: str, page_url: str) -> List[Chunk]:
        """Simple fixed-size chunking with overlap"""
        chunks = []
        chunk_id = 0
        
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk_text = text[i:i + self.chunk_size]
            if chunk_text.strip():
                chunk = Chunk(
                    text=chunk_text.strip(),
                    start_idx=i,
                    end_idx=min(i + self.chunk_size, len(text)),
                    chunk_id=f"{page_url}#chunk_{chunk_id}",
                    source="page_content"
                )
                chunks.append(chunk)
                chunk_id += 1
        
        return chunks

    def _split_by_sentences(self, text: str, max_length: int) -> List[str]:
        """Helper to split text by sentences up to max_length"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        result = []
        current = ""
        
        for sentence in sentences:
            if len(current) + len(sentence) <= max_length:
                current += " " + sentence if current else sentence
            else:
                if current:
                    result.append(current)
                current = sentence
        
        if current:
            result.append(current)
        
        return result
