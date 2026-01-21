"""
Document Chunking for RAG Pipeline

Splits documents into chunks for embedding and retrieval.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkingStrategy(Enum):
    """Chunking strategies"""
    FIXED_SIZE = "fixed_size"  # Fixed character count
    SENTENCE = "sentence"  # Split by sentences
    PARAGRAPH = "paragraph"  # Split by paragraphs
    SEMANTIC = "semantic"  # Semantic chunking (requires ML model)
    RECURSIVE = "recursive"  # Recursive chunking with overlap


@dataclass
class DocumentChunk:
    """Document chunk for RAG"""
    text: str
    chunk_id: str
    document_id: str
    start_index: int
    end_index: int
    metadata: Dict[str, Any]
    overlap: int = 0  # Overlap with previous chunk


class DocumentChunker:
    """
    Document chunker for RAG pipeline.
    
    Splits documents into chunks suitable for embedding and retrieval.
    """
    
    def __init__(
        self,
        strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ):
        """
        Initialize document chunker.
        
        Args:
            strategy: Chunking strategy
            chunk_size: Target chunk size (characters or tokens)
            chunk_overlap: Overlap between chunks (characters)
            min_chunk_size: Minimum chunk size
        """
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        logger.info(f"✅ DocumentChunker initialized: {strategy.value}, size={chunk_size}, overlap={chunk_overlap}")
    
    def chunk(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Chunk document into smaller pieces.
        
        Args:
            text: Document text
            document_id: Document identifier
            metadata: Optional metadata
        
        Returns:
            List of DocumentChunk objects
        """
        metadata = metadata or {}
        
        if self.strategy == ChunkingStrategy.FIXED_SIZE:
            return self._chunk_fixed_size(text, document_id, metadata)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            return self._chunk_sentence(text, document_id, metadata)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._chunk_paragraph(text, document_id, metadata)
        elif self.strategy == ChunkingStrategy.RECURSIVE:
            return self._chunk_recursive(text, document_id, metadata)
        else:
            logger.warning(f"Unknown strategy: {self.strategy}, using fixed_size")
            return self._chunk_fixed_size(text, document_id, metadata)
    
    def _chunk_fixed_size(
        self,
        text: str,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Chunk by fixed size."""
        chunks = []
        start = 0
        chunk_idx = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end]
            
            if len(chunk_text) >= self.min_chunk_size:
                chunk = DocumentChunk(
                    text=chunk_text,
                    chunk_id=f"{document_id}_chunk_{chunk_idx}",
                    document_id=document_id,
                    start_index=start,
                    end_index=end,
                    metadata={**metadata, 'chunk_index': chunk_idx},
                    overlap=self.chunk_overlap if start > 0 else 0
                )
                chunks.append(chunk)
                chunk_idx += 1
            
            start = end - self.chunk_overlap
        
        return chunks
    
    def _chunk_sentence(
        self,
        text: str,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Chunk by sentences."""
        # Simple sentence splitting (can be improved with NLTK/spaCy)
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_idx = 0
        start_index = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            if current_size + sentence_size > self.chunk_size and current_chunk:
                # Create chunk
                chunk_text = ' '.join(current_chunk)
                end_index = start_index + len(chunk_text)
                
                chunk = DocumentChunk(
                    text=chunk_text,
                    chunk_id=f"{document_id}_chunk_{chunk_idx}",
                    document_id=document_id,
                    start_index=start_index,
                    end_index=end_index,
                    metadata={**metadata, 'chunk_index': chunk_idx},
                    overlap=0
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_text = ' '.join(current_chunk[-2:]) if len(current_chunk) >= 2 else current_chunk[-1]
                current_chunk = [overlap_text[:self.chunk_overlap]] if self.chunk_overlap > 0 else []
                current_size = len(current_chunk[0]) if current_chunk else 0
                start_index = end_index - len(overlap_text) if self.chunk_overlap > 0 else end_index
                chunk_idx += 1
            
            current_chunk.append(sentence)
            current_size += sentence_size + 1  # +1 for space
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            end_index = start_index + len(chunk_text)
            
            chunk = DocumentChunk(
                text=chunk_text,
                chunk_id=f"{document_id}_chunk_{chunk_idx}",
                document_id=document_id,
                start_index=start_index,
                end_index=end_index,
                metadata={**metadata, 'chunk_index': chunk_idx},
                overlap=0
            )
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_paragraph(
        self,
        text: str,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Chunk by paragraphs."""
        paragraphs = text.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_idx = 0
        start_index = 0
        
        for paragraph in paragraphs:
            para_size = len(paragraph)
            
            if para_size > self.chunk_size:
                # Paragraph is too large, split it
                if current_chunk:
                    # Save current chunk first
                    chunk_text = '\n\n'.join(current_chunk)
                    end_index = start_index + len(chunk_text)
                    
                    chunk = DocumentChunk(
                        text=chunk_text,
                        chunk_id=f"{document_id}_chunk_{chunk_idx}",
                        document_id=document_id,
                        start_index=start_index,
                        end_index=end_index,
                        metadata={**metadata, 'chunk_index': chunk_idx},
                        overlap=0
                    )
                    chunks.append(chunk)
                    chunk_idx += 1
                    start_index = end_index
                
                # Split large paragraph using fixed size
                para_chunks = self._chunk_fixed_size(paragraph, f"{document_id}_para", {})
                for para_chunk in para_chunks:
                    para_chunk.chunk_id = f"{document_id}_chunk_{chunk_idx}"
                    para_chunk.document_id = document_id
                    para_chunk.start_index = start_index
                    para_chunk.end_index = start_index + len(para_chunk.text)
                    chunks.append(para_chunk)
                    start_index = para_chunk.end_index
                    chunk_idx += 1
                
                current_chunk = []
                current_size = 0
            elif current_size + para_size > self.chunk_size:
                # Create chunk
                chunk_text = '\n\n'.join(current_chunk)
                end_index = start_index + len(chunk_text)
                
                chunk = DocumentChunk(
                    text=chunk_text,
                    chunk_id=f"{document_id}_chunk_{chunk_idx}",
                    document_id=document_id,
                    start_index=start_index,
                    end_index=end_index,
                    metadata={**metadata, 'chunk_index': chunk_idx},
                    overlap=0
                )
                chunks.append(chunk)
                chunk_idx += 1
                start_index = end_index
                current_chunk = [paragraph]
                current_size = para_size
            else:
                current_chunk.append(paragraph)
                current_size += para_size + 2  # +2 for \n\n
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            end_index = start_index + len(chunk_text)
            
            chunk = DocumentChunk(
                text=chunk_text,
                chunk_id=f"{document_id}_chunk_{chunk_idx}",
                document_id=document_id,
                start_index=start_index,
                end_index=end_index,
                metadata={**metadata, 'chunk_index': chunk_idx},
                overlap=0
            )
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_recursive(
        self,
        text: str,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Recursive chunking with overlap.
        
        Tries to split by paragraphs first, then sentences, then fixed size.
        """
        # Try paragraph first
        if '\n\n' in text:
            para_chunks = self._chunk_paragraph(text, document_id, metadata)
            # If chunks are reasonable size, return them
            if all(len(c.text) <= self.chunk_size * 1.5 for c in para_chunks):
                return para_chunks
        
        # Try sentence splitting
        if '.' in text or '!' in text or '?' in text:
            sent_chunks = self._chunk_sentence(text, document_id, metadata)
            # If chunks are reasonable size, return them
            if all(len(c.text) <= self.chunk_size * 1.5 for c in sent_chunks):
                return sent_chunks
        
        # Fallback to fixed size
        return self._chunk_fixed_size(text, document_id, metadata)

