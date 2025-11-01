from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ConnectionError, RequestError
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class ElasticsearchClient:
    """
    Elasticsearch client for indexing and managing documents
    Implements at-most-once semantics using document IDs
    """
    
    def __init__(self, hosts=None, index_name=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        try:
            # Get Elasticsearch hosts from environment or use default
            if hosts is None:
                env_hosts = os.getenv('ELASTICSEARCH_HOSTS', 'http://elasticsearch:9200')
                self.hosts = [h.strip() for h in env_hosts.split(',')]
            else:
                self.hosts = hosts if isinstance(hosts, list) else [hosts]
            
            self.index_name = index_name
            
            self.logger.info(f"🔌 Connecting to Elasticsearch: {self.hosts}")
            
            # Create Elasticsearch client
            self.es = Elasticsearch(
                hosts=self.hosts,
                retry_on_timeout=True,
                max_retries=3,
                request_timeout=30
            )
            
            # Verify connection
            if not self.es.ping():
                raise ConnectionError("Failed to connect to Elasticsearch")
            
            info = self.es.info()
            self.logger.info(f"✅ Connected to Elasticsearch cluster: {info['cluster_name']}")
            
            # Create index if specified and doesn't exist
            if self.index_name:
                self._ensure_index_exists()
                
        except Exception as e:
            self.logger.error(f"❌ Error initializing Elasticsearch client: {e}")
            raise

    def _ensure_index_exists(self):
        """Create index with appropriate mappings if it doesn't exist"""
        try:
            if not self.es.indices.exists(index=self.index_name):
                self.logger.info(f"📝 Creating index: {self.index_name}")
                
                # Define index mappings for web logs
                mappings = {
                    "mappings": {
                        "properties": {
                            "ip_address": {"type": "ip"},
                            "identd": {"type": "keyword"},
                            "auth_user": {"type": "keyword"},
                            "timestamp": {"type": "date", "format": "dd/MMM/yyyy:HH:mm:ss Z"},
                            "method": {"type": "keyword"},
                            "endpoint": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                            "http_version": {"type": "keyword"},
                            "status_code": {"type": "short"},
                            "response_size": {"type": "integer"},
                            "referrer": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                            "user_agent": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                            "indexed_at": {"type": "date"}
                        }
                    },
                    "settings": {
                        "number_of_shards": 2,
                        "number_of_replicas": 1,
                        "refresh_interval": "5s"
                    }
                }
                
                self.es.indices.create(index=self.index_name, body=mappings)
                self.logger.info(f"✅ Index '{self.index_name}' created successfully")
            else:
                self.logger.debug(f"Index '{self.index_name}' already exists")
                
        except Exception as e:
            self.logger.error(f"❌ Error ensuring index exists: {e}")
            raise

    def generate_document_id(self, doc: Dict[str, Any], kafka_key: Optional[str] = None) -> str:
        """
        Generate a unique document ID for at-most-once semantics
        Prefers Kafka key if available (most efficient), otherwise generates from doc fields
        
        Args:
            doc: Document data
            kafka_key: Optional Kafka message key (if available, use this directly)
        
        Returns:
            str: Document ID
        """
        try:
            # Use Kafka key if available (most efficient - no need to regenerate)
            if kafka_key:
                self.logger.debug(f"Using Kafka key as document ID: {kafka_key}")
                return kafka_key
            
            # Fallback: Generate from document fields
            unique_string = f"{doc.get('ip_address', '')}_{doc.get('timestamp', '')}_{doc.get('endpoint', '')}_{doc.get('method', '')}"
            return unique_string
        except Exception as e:
            self.logger.error(f"❌ Error generating document ID: {e}")
            # Last resort: timestamp-based ID
            return f"{datetime.utcnow().isoformat()}_{hash(str(doc))}"

    def index_document(self, doc: Dict[str, Any], doc_id: Optional[str] = None, kafka_key: Optional[str] = None, index_name: Optional[str] = None) -> bool:
        """
        Index a single document with at-most-once semantics
        
        Args:
            doc: Document to index
            doc_id: Optional document ID (generated if not provided)
            kafka_key: Optional Kafka message key (preferred over doc_id)
            index_name: Optional index name (uses default if not provided)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            target_index = index_name or self.index_name
            if not target_index:
                raise ValueError("Index name must be specified")
            
            # Generate ID: prefer kafka_key > doc_id > auto-generate
            if doc_id is None:
                doc_id = self.generate_document_id(doc, kafka_key)
            
            # Add indexing timestamp
            doc['indexed_at'] = datetime.utcnow().isoformat()
            
            # Index with explicit ID for at-most-once semantics
            # If document with same ID exists, it will be updated (idempotent)
            response = self.es.index(
                index=target_index,
                id=doc_id,
                document=doc,
                op_type='index'  # Use 'create' for strict at-most-once (fails if exists)
            )
            
            self.logger.debug(f"✅ Indexed document {doc_id} with result: {response['result']}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error indexing document: {e}")
            return False

    def bulk_index(self, documents: List[Dict[str, Any]], kafka_keys: Optional[List[str]] = None, index_name: Optional[str] = None, chunk_size: int = 500) -> tuple:
        """
        Bulk index multiple documents efficiently with at-most-once semantics
        
        Args:
            documents: List of documents to index
            kafka_keys: Optional list of Kafka message keys (must match documents length)
            index_name: Optional index name (uses default if not provided)
            chunk_size: Number of documents per bulk request
        
        Returns:
            tuple: (success_count, error_count)
        """
        try:
            target_index = index_name or self.index_name
            if not target_index:
                raise ValueError("Index name must be specified")
            
            if not documents:
                self.logger.warning("No documents to index")
                return (0, 0)
            
            # Validate kafka_keys length if provided
            if kafka_keys and len(kafka_keys) != len(documents):
                raise ValueError(
                    f"kafka_keys length ({len(kafka_keys)}) must match documents length ({len(documents)})"
                )
            
            # Prepare bulk actions with IDs for at-most-once semantics
            actions = []
            for i, doc in enumerate(documents):
                # Use Kafka key if available, otherwise generate
                kafka_key = kafka_keys[i] if kafka_keys else None
                doc_id = self.generate_document_id(doc, kafka_key)
                doc['indexed_at'] = datetime.utcnow().isoformat()
                
                action = {
                    '_index': target_index,
                    '_id': doc_id,
                    '_source': doc
                }
                actions.append(action)
            
            # Perform bulk indexing
            success_count = 0
            error_count = 0
            
            for success, info in helpers.streaming_bulk(
                self.es,
                actions,
                chunk_size=chunk_size,
                raise_on_error=False,
                raise_on_exception=False
            ):
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    self.logger.error(f"❌ Failed to index document: {info}")
            
            self.logger.info(
                f"✅ Bulk indexing complete: {success_count} succeeded, {error_count} failed"
            )
            
            return (success_count, error_count)
            
        except Exception as e:
            self.logger.error(f"❌ Error in bulk indexing: {e}")
            return (0, len(documents))

    def search(self, query: Dict[str, Any], index_name: Optional[str] = None, size: int = 10) -> List[Dict[str, Any]]:
        """
        Search for documents
        
        Args:
            query: Elasticsearch query DSL
            index_name: Optional index name (uses default if not provided)
            size: Number of results to return
        
        Returns:
            List of matching documents
        """
        try:
            target_index = index_name or self.index_name
            
            response = self.es.search(
                index=target_index,
                body=query,
                size=size
            )
            
            hits = response['hits']['hits']
            documents = [hit['_source'] for hit in hits]
            
            self.logger.info(f"🔍 Found {len(documents)} documents")
            return documents
            
        except Exception as e:
            self.logger.error(f"❌ Error searching: {e}")
            return []

    def delete_index(self, index_name: Optional[str] = None) -> bool:
        """Delete an index"""
        try:
            target_index = index_name or self.index_name
            
            if self.es.indices.exists(index=target_index):
                self.es.indices.delete(index=target_index)
                self.logger.info(f"✅ Index '{target_index}' deleted successfully")
                return True
            else:
                self.logger.warning(f"⚠️  Index '{target_index}' does not exist")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error deleting index: {e}")
            return False

    def get_index_stats(self, index_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for an index"""
        try:
            target_index = index_name or self.index_name
            
            stats = self.es.indices.stats(index=target_index)
            
            doc_count = stats['indices'][target_index]['total']['docs']['count']
            size_in_bytes = stats['indices'][target_index]['total']['store']['size_in_bytes']
            
            self.logger.info(
                f"📊 Index '{target_index}': {doc_count} documents, "
                f"{size_in_bytes / (1024*1024):.2f} MB"
            )
            
            return {
                'doc_count': doc_count,
                'size_bytes': size_in_bytes,
                'size_mb': size_in_bytes / (1024*1024)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error getting index stats: {e}")
            return {}

    def close(self):
        """Close Elasticsearch connection"""
        try:
            if hasattr(self, 'es') and self.es:
                self.es.close()
                self.logger.info("✅ Elasticsearch client closed successfully")
        except Exception as e:
            self.logger.error(f"❌ Error closing Elasticsearch client: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False
