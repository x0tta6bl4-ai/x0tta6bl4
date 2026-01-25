"""
Storage module for x0tta6bl4
=============================

Provides:
- IPFS client for distributed storage
- Vector index for semantic search
- Knowledge Storage v2.0 (complete implementation)
"""
from src.storage.ipfs_client import IPFSClient, MockIPFSClient
from src.storage.vector_index import VectorIndex
from src.storage.knowledge_storage_v2 import KnowledgeStorageV2, IncidentEntry

__all__ = [
    'IPFSClient',
    'MockIPFSClient',
    'VectorIndex',
    'KnowledgeStorageV2',
    'IncidentEntry'
]
