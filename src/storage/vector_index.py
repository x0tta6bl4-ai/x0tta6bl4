"""
Vector Index for RAG Pipeline
=============================

HNSW-based vector index for semantic search in knowledge base.
"""
import logging
import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Try to import HNSW
try:
    import hnswlib
    HNSW_AVAILABLE = True
except ImportError:
    HNSW_AVAILABLE = False
    logger.warning("⚠️ hnswlib not available. Install with: pip install hnswlib")

# Try to import sentence transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("⚠️ sentence-transformers not available. Install with: pip install sentence-transformers")


class VectorIndex:
    """
    HNSW-based vector index for semantic search.
    
    Features:
    - HNSW index (M=32, ef=256)
    - 384-dimensional embeddings (all-MiniLM-L6-v2)
    - Similarity search with threshold
    - Persistent storage
    """
    
    def __init__(
        self,
        dimension: int = 384,
        max_elements: int = 10000,
        M: int = 32,
        ef_construction: int = 200,
        ef_search: int = 256,
        index_path: Optional[Path] = None
    ):
        """
        Initialize vector index.
        
        Args:
            dimension: Embedding dimension (384 for MiniLM-L6)
            max_elements: Maximum number of elements
            M: Number of bi-directional links (default: 32)
            ef_construction: Size of dynamic candidate list (default: 200)
            ef_search: Size of dynamic candidate list during search (default: 256)
            index_path: Path to persistent index
        """
        self.dimension = dimension
        self.max_elements = max_elements
        self.M = M
        self.ef_construction = ef_construction
        self.ef_search = ef_search
        self.index_path = index_path or Path("/var/lib/x0tta6bl4/hnsw_index")
        
        self.index = None
        self.metadata: Dict[int, Dict[str, Any]] = {}  # id -> metadata
        self.next_id = 0
        
        # Initialize embedding model
        self.embedding_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("✅ Loaded embedding model: all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load embedding model: {e}")
        
        # Initialize HNSW index
        if HNSW_AVAILABLE:
            self._init_index()
        else:
            logger.warning("⚠️ HNSW not available. Using mock index.")
    
    def _init_index(self):
        """Initialize HNSW index."""
        if not HNSW_AVAILABLE:
            return
        
        try:
            self.index = hnswlib.Index(space='cosine', dim=self.dimension)
            self.index.init_index(
                max_elements=self.max_elements,
                ef_construction=self.ef_construction,
                M=self.M
            )
            self.index.set_ef(self.ef_search)
            logger.info(f"✅ HNSW index initialized (M={self.M}, ef={self.ef_search})")
        except Exception as e:
            logger.error(f"❌ Failed to initialize HNSW index: {e}")
            self.index = None
    
    def embed(self, text: str) -> np.ndarray:
        """
        Generate embedding for text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector (384-dim)
        """
        if self.embedding_model:
            try:
                embedding = self.embedding_model.encode(text, convert_to_numpy=True)
                return embedding
            except Exception as e:
                logger.error(f"❌ Failed to generate embedding: {e}")
        
        # Fallback: random embedding (for testing)
        logger.warning("⚠️ Using random embedding (fallback)")
        return np.random.rand(self.dimension).astype(np.float32)
    
    def add(
        self,
        text: str,
        metadata: Dict[str, Any],
        embedding: Optional[np.ndarray] = None
    ) -> int:
        """
        Add document to index.
        
        Args:
            text: Document text
            metadata: Document metadata (incident_id, type, etc.)
            embedding: Pre-computed embedding (optional)
            
        Returns:
            Document ID
        """
        doc_id = self.next_id
        self.next_id += 1
        
        # Generate embedding if not provided
        if embedding is None:
            embedding = self.embed(self._prepare_text(text, metadata))
        
        # Normalize embedding
        embedding = embedding / np.linalg.norm(embedding)
        
        # Add to index
        if self.index and HNSW_AVAILABLE:
            try:
                self.index.add_items(embedding.reshape(1, -1), [doc_id])
            except Exception as e:
                logger.error(f"❌ Failed to add to index: {e}")
        
        # Store metadata
        self.metadata[doc_id] = {
            **metadata,
            'text': text,
            'embedding': embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
        }
        
        logger.debug(f"📝 Added document {doc_id} to index")
        return doc_id
    
    def search(
        self,
        query: str,
        k: int = 10,
        threshold: float = 0.7
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            k: Number of results
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            List of (doc_id, similarity_score, metadata) tuples
        """
        # Generate query embedding
        query_embedding = self.embed(query)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Search in index
        if self.index and HNSW_AVAILABLE:
            try:
                labels, distances = self.index.knn_query(query_embedding.reshape(1, -1), k=k)
                results = []
                for label, distance in zip(labels[0], distances[0]):
                    similarity = 1.0 - distance  # Convert distance to similarity
                    if similarity >= threshold and label in self.metadata:
                        results.append((int(label), similarity, self.metadata[label]))
                return results
            except Exception as e:
                logger.error(f"❌ Search failed: {e}")
        
        # Fallback: return empty results
        logger.warning("⚠️ Search not available (HNSW not initialized)")
        return []
    
    def _prepare_text(self, text: str, metadata: Dict[str, Any]) -> str:
        """Prepare text for embedding (combine text + metadata)."""
        parts = [text]
        
        # Add metadata fields to text
        if 'anomaly_type' in metadata:
            parts.append(f"Type: {metadata['anomaly_type']}")
        if 'root_cause' in metadata:
            parts.append(f"Root cause: {metadata['root_cause']}")
        if 'action_taken' in metadata:
            parts.append(f"Action: {metadata['action_taken']}")
        
        return " ".join(parts)
    
    def save(self, path: Optional[Path] = None):
        """Save index to disk."""
        path = path or self.index_path
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Save HNSW index
            if self.index and HNSW_AVAILABLE:
                index_file = path / "hnsw_index.bin"
                self.index.save_index(str(index_file))
                logger.info(f"💾 Saved HNSW index to {index_file}")
            
            # Save metadata
            metadata_file = path / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump({
                    'metadata': self.metadata,
                    'next_id': self.next_id,
                    'dimension': self.dimension
                }, f)
            logger.info(f"💾 Saved metadata to {metadata_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save index: {e}")
    
    def load(self, path: Optional[Path] = None):
        """Load index from disk."""
        path = path or self.index_path
        
        try:
            # Load metadata
            metadata_file = path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                    self.metadata = data.get('metadata', {})
                    self.next_id = data.get('next_id', 0)
                    self.dimension = data.get('dimension', 384)
                logger.info(f"📂 Loaded metadata from {metadata_file}")
            
            # Load HNSW index
            if HNSW_AVAILABLE:
                index_file = path / "hnsw_index.bin"
                if index_file.exists():
                    self._init_index()
                    self.index.load_index(str(index_file))
                    self.index.set_ef(self.ef_search)
                    logger.info(f"📂 Loaded HNSW index from {index_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load index: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            'total_documents': len(self.metadata),
            'dimension': self.dimension,
            'max_elements': self.max_elements,
            'M': self.M,
            'ef_search': self.ef_search,
            'hnsw_available': HNSW_AVAILABLE,
            'embedding_model_available': SENTENCE_TRANSFORMERS_AVAILABLE
        }

