from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import logging
import os
import hashlib

from .TopicManager import TopicManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('kafka.producer').setLevel(logging.WARNING)
logging.getLogger('kafka.admin').setLevel(logging.WARNING)
logging.getLogger('kafka.coordinator').setLevel(logging.ERROR)

class Producer:
    def __init__(self, topic, bootstrap_servers=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        try:
            if bootstrap_servers is None:
                env_servers = os.getenv(
                    'KAFKA_BOOTSTRAP_SERVERS', 
                    'kafka-broker-1:19092,kafka-broker-2:19092'
                )
                self.bootstrap_servers = [s.strip() for s in env_servers.split(',')]
            else:
                self.bootstrap_servers = bootstrap_servers
            
            self.topic = topic
            self.topic_manager = TopicManager(self.bootstrap_servers)
            
            # Ensure topic exists before creating producer
            self._ensure_topic_exists()
            
            self.logger.info(f"🔌 Creating Kafka producer for topic: {self.topic}")
            
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,  # Add key serializer
                retries=3,
                linger_ms=10,
                batch_size=16384,
                request_timeout_ms=30000,
                acks='all',  # Ensure all replicas acknowledge
                compression_type='gzip'  # Compress for efficiency
            )
            self.logger.info(f"✅ Producer is Ready for topic: {self.topic}")
        except Exception as e:
            self.logger.error(f"❌ Error Initializing Producer: {e}")
            raise

    def _ensure_topic_exists(self, topic_name=None):
        """Ensure topic exists, create if it doesn't"""
        topic_to_check = topic_name or self.topic
        try:
            if not self.topic_manager.topic_exists(topic_to_check):
                self.logger.warning(f"⚠️  Topic '{topic_to_check}' doesn't exist. Creating...")
                success = self.topic_manager.create_topic(
                    topic_to_check,
                    num_partitions=6,  # Increase partitions for better parallelism
                    replication_factor=2
                )
                if not success:
                    raise Exception(f"Failed to create topic '{topic_to_check}'")
        except Exception as e:
            self.logger.error(f"❌ Error ensuring topic exists: {e}")
            raise

    def generate_key(self, value):
        """
        Generate a key for the message based on content
        Used for partitioning and as unique identifier for at-most-once semantics
        
        Args:
            value: Message value (should be a string or dict)
        
        Returns:
            str: Generated key
        """
        try:
            if isinstance(value, dict):
                # For structured data, use specific fields to create key
                # Example: use ip_address + timestamp for web logs
                key_parts = [
                    str(value.get('ip_address', '')),
                    str(value.get('timestamp', '')),
                    str(value.get('endpoint', ''))
                ]
                key_string = '_'.join(key_parts)
            else:
                # For unstructured data, hash the entire content
                key_string = str(value)
            
            # Create a short hash for the key
            key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]
            return key_hash
            
        except Exception as e:
            self.logger.error(f"❌ Error generating key: {e}")
            return None

    def send(self, value, topic=None, key=None, partition=None):
        """
        Send a message to Kafka
        
        Args:
            value: Message value (will be JSON serialized)
            topic: Optional topic name (uses default if not provided)
            key: Optional message key (auto-generated if not provided)
            partition: Optional partition number
        
        Returns:
            FutureRecordMetadata: Future for the send operation
        """
        topic_to_use = topic or self.topic
        
        try:
            # Ensure topic exists before sending
            if topic_to_use != self.topic:
                self._ensure_topic_exists(topic_to_use)
            
            # Generate key if not provided
            if key is None:
                key = self.generate_key(value)
            
            # Send message
            future = self.producer.send(
                topic=topic_to_use,
                key=key,
                value=value,
                partition=partition
            )
            
            self.logger.debug(f"📤 Sent message with key '{key}' to topic '{topic_to_use}'")
            return future
            
        except KafkaError as ke:
            self.logger.error(f"❌ Kafka error sending to '{topic_to_use}': {ke}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error sending to '{topic_to_use}': {e}")
            raise

    def send_batch(self, messages, topic=None):
        """
        Send multiple messages efficiently
        
        Args:
            messages: List of message values or (key, value) tuples
            topic: Optional topic name
        
        Returns:
            list: List of futures for each message
        """
        try:
            futures = []
            
            for msg in messages:
                if isinstance(msg, tuple) and len(msg) == 2:
                    # Message is (key, value) tuple
                    key, value = msg
                    future = self.send(value=value, topic=topic, key=key)
                else:
                    # Message is just value, key will be auto-generated
                    future = self.send(value=msg, topic=topic)
                
                futures.append(future)
            
            self.logger.info(f"📦 Sent batch of {len(messages)} messages")
            return futures
            
        except Exception as e:
            self.logger.error(f"❌ Error sending batch: {e}")
            raise

    def flush(self, timeout_ms=None):
        """Flush any pending messages"""
        try:
            self.producer.flush(timeout=timeout_ms)
            self.logger.info("✅ All messages flushed successfully")
        except Exception as e:
            self.logger.error(f"❌ Error during flush: {e}")
            raise

    def close(self, timeout_ms=30000):
        """Close producer and cleanup"""
        try:
            # Flush any pending messages
            self.flush(timeout_ms=5000)
            
            # Close producer
            if hasattr(self, 'producer') and self.producer:
                self.producer.close(timeout=timeout_ms)
                self.producer = None
            
            # Close topic manager
            if hasattr(self, 'topic_manager') and self.topic_manager:
                self.topic_manager.close()
                self.topic_manager = None
            
            self.logger.info("✅ Producer closed successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error closing Producer: {e}")
            raise

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False
