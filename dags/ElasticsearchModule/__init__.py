"""
Elasticsearch Module for indexing and managing documents
Provides at-most-once semantics using document IDs
"""

from .ElasticsearchClient import ElasticsearchClient

__all__ = ['ElasticsearchClient']
