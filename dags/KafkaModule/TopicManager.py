from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, UnknownTopicOrPartitionError
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('kafka.admin').setLevel(logging.WARNING)
logging.getLogger('kafka.coordinator').setLevel(logging.ERROR)  # Suppress group_id warnings

class TopicManager:
    def __init__(self, bootstrap_servers=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._topics_cache = None  # Cache for topics list
        self._cache_valid = False
        
        try:
            if bootstrap_servers is None:
                env_servers = os.getenv(
                    'KAFKA_BOOTSTRAP_SERVERS', 
                    'kafka-broker-1:19092,kafka-broker-2:19092'
                )
                self.bootstrap_servers = [s.strip() for s in env_servers.split(',')]
            else:
                self.bootstrap_servers = bootstrap_servers
            
            self.logger.info(f"🔌 Initializing TopicManager with brokers: {self.bootstrap_servers}")
            
            self.admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id='kafka_topic_manager',
                request_timeout_ms=10000
            )
            self.logger.info("✅ TopicManager initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ Error initializing TopicManager: {e}")
            raise

    def _refresh_topics_cache(self):
        """Refresh the cached list of topics from Kafka cluster"""
        try:
            self._topics_cache = self.admin_client.list_topics()
            self._cache_valid = True
            self.logger.debug(f"Refreshed topics cache: {len(self._topics_cache)} topics found")
        except Exception as e:
            self.logger.error(f"Error refreshing topics cache: {e}")
            self._cache_valid = False
            self._topics_cache = set()

    def _invalidate_cache(self):
        """Invalidate the topics cache (call after creating/deleting topics)"""
        self._cache_valid = False

    def topic_exists(self, topic_name, force_refresh=False):
        """
        Check if topic exists using admin client (efficient, no consumer needed)
        
        Args:
            topic_name: Name of the topic to check
            force_refresh: If True, bypass cache and query Kafka directly
        
        Returns:
            bool: True if topic exists, False otherwise
        """
        try:
            # Refresh cache if invalid or force refresh requested
            if not self._cache_valid or force_refresh:
                self._refresh_topics_cache()
            
            exists = topic_name in self._topics_cache
            
            if exists:
                self.logger.debug(f"✓ Topic '{topic_name}' exists")
            else:
                self.logger.debug(f"✗ Topic '{topic_name}' does not exist")
            
            return exists
            
        except Exception as e:
            self.logger.error(f"❌ Error checking if topic '{topic_name}' exists: {e}")
            # Fallback: try direct query without cache
            try:
                topics = self.admin_client.list_topics()
                return topic_name in topics
            except Exception as fallback_error:
                self.logger.error(f"❌ Fallback check also failed: {fallback_error}")
                return False

    def get_all_topics(self, force_refresh=False):
        """
        Get list of all topics
        
        Args:
            force_refresh: If True, bypass cache and query Kafka directly
        
        Returns:
            set: Set of topic names
        """
        try:
            if not self._cache_valid or force_refresh:
                self._refresh_topics_cache()
            return self._topics_cache.copy()
        except Exception as e:
            self.logger.error(f"❌ Error getting topics list: {e}")
            return set()

    def create_topic(self, topic_name, num_partitions=6, replication_factor=2):
        """
        Create topic if it doesn't exist
        
        Args:
            topic_name: Name of the topic to create
            num_partitions: Number of partitions (default: 3)
            replication_factor: Replication factor (default: 1)
        
        Returns:
            bool: True if topic was created or already exists, False on failure
        """
        try:
            # Check if topic already exists (using cache)
            if self.topic_exists(topic_name):
                self.logger.info(f"ℹ️  Topic '{topic_name}' already exists")
                return True

            # Create the topic
            topic_list = [NewTopic(
                name=topic_name,
                num_partitions=num_partitions,
                replication_factor=replication_factor
            )]

            self.admin_client.create_topics(new_topics=topic_list, validate_only=False)
            self.logger.info(
                f"✅ Topic '{topic_name}' created successfully "
                f"(partitions={num_partitions}, replication={replication_factor})"
            )
            
            # Invalidate cache since we created a new topic
            self._invalidate_cache()
            return True

        except TopicAlreadyExistsError:
            self.logger.info(f"ℹ️  Topic '{topic_name}' already exists")
            self._invalidate_cache()
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create topic '{topic_name}': {e}")
            return False

    def delete_topic(self, topic_name):
        """
        Delete a topic
        
        Args:
            topic_name: Name of the topic to delete
        
        Returns:
            bool: True if topic was deleted successfully, False otherwise
        """
        try:
            if not self.topic_exists(topic_name):
                self.logger.warning(f"⚠️  Topic '{topic_name}' does not exist, nothing to delete")
                return False

            self.admin_client.delete_topics([topic_name])
            self.logger.info(f"✅ Topic '{topic_name}' deleted successfully")
            
            # Invalidate cache since we deleted a topic
            self._invalidate_cache()
            return True
            
        except UnknownTopicOrPartitionError:
            self.logger.warning(f"⚠️  Topic '{topic_name}' does not exist")
            self._invalidate_cache()
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to delete topic '{topic_name}': {e}")
            return False

    def get_topic_config(self, topic_name):
        """
        Get configuration for a specific topic
        
        Args:
            topic_name: Name of the topic
        
        Returns:
            dict: Topic configuration or None on error
        """
        try:
            from kafka.admin import ConfigResource, ConfigResourceType
            
            resource = ConfigResource(ConfigResourceType.TOPIC, topic_name)
            configs = self.admin_client.describe_configs([resource])
            
            if configs:
                config_dict = {cfg.name: cfg.value for cfg in configs[resource].resources[0][4]}
                return config_dict
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error getting config for topic '{topic_name}': {e}")
            return None

    def close(self):
        """Close admin client and cleanup resources"""
        try:
            if hasattr(self, 'admin_client') and self.admin_client:
                self.admin_client.close()
                self._topics_cache = None
                self._cache_valid = False
                self.logger.info("✅ TopicManager closed successfully")
        except Exception as e:
            self.logger.error(f"❌ Error closing TopicManager: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False
