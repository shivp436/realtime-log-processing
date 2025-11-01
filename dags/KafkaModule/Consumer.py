from kafka import KafkaConsumer
from kafka.errors import KafkaError
import json
import logging
import os

from .TopicManager import TopicManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('kafka.consumer').setLevel(logging.WARNING)
logging.getLogger('kafka.admin').setLevel(logging.WARNING)
logging.getLogger('kafka.coordinator').setLevel(logging.ERROR)

class Consumer:
    def __init__(
        self, 
        topic, 
        group_id=None, 
        bootstrap_servers=None,
        auto_offset_reset="earliest",
        enable_auto_commit=False,  # Changed default to False for manual commit control
        value_deserializer=lambda v: json.loads(v.decode('utf-8')) if v else None,
        key_deserializer=lambda k: k.decode('utf-8') if k else None,
        max_poll_records=500  # Batch size for efficient processing
    ):
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

            # Check if topic exists
            self.topic_manager = TopicManager(self.bootstrap_servers)
            if not self.topic_manager.topic_exists(topic):
                self.logger.error(f"Topic {topic} does not exist")
                self.topic_manager.close()
                raise Exception(f"Topic '{topic}' does not exist")
            
            self.topic = topic
            self.group_id = group_id
            self.enable_auto_commit = enable_auto_commit
            self._partitions_assigned = False
            
            self.logger.info(
                f"🔌 Creating consumer for topic '{self.topic}' "
                f"with group_id '{self.group_id}' "
                f"(auto_commit={self.enable_auto_commit})"
            )
            
            self.consumer = KafkaConsumer(
                self.topic,
                group_id=self.group_id,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=value_deserializer,
                key_deserializer=key_deserializer,
                auto_offset_reset=auto_offset_reset,
                enable_auto_commit=enable_auto_commit,
                max_poll_records=max_poll_records,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
                consumer_timeout_ms=1000  # Prevent indefinite blocking
            )
            self.logger.info(f"✅ Consumer is Ready for topic: {self.topic}")
            
        except Exception as e:
            self.logger.error(f"❌ Error Initializing Consumer: {e}")
            if hasattr(self, 'topic_manager') and self.topic_manager:
                self.topic_manager.close()
            raise

    def _ensure_partitions_assigned(self, timeout_ms=10000):
        """
        Ensure partitions are assigned by polling once if needed
        This triggers the consumer group rebalance
        """
        if not self._partitions_assigned:
            self.logger.debug("🔄 Triggering partition assignment...")
            # Poll once to trigger partition assignment
            self.consumer.poll(timeout_ms=timeout_ms, max_records=1)
            
            # Check if partitions are now assigned
            assignment = self.consumer.assignment()
            if assignment:
                self._partitions_assigned = True
                self.logger.info(f"✅ Partitions assigned: {[p.partition for p in assignment]}")
            else:
                self.logger.warning("⚠️  No partitions assigned after poll")

    def consume_batch(self, max_messages=500, timeout_ms=5000):
        """
        Consume a batch of messages efficiently
        Returns list of messages for batch processing
        
        Args:
            max_messages: Maximum number of messages to consume in one batch
            timeout_ms: Timeout for poll operation
        
        Returns:
            list: List of ConsumerRecord objects
        """
        try:
            # Ensure partitions are assigned before consuming
            if not self._partitions_assigned:
                self._ensure_partitions_assigned(timeout_ms=timeout_ms)
            
            messages = []
            records = self.consumer.poll(timeout_ms=timeout_ms, max_records=max_messages)
            
            for topic_partition, msgs in records.items():
                messages.extend(msgs)
                self.logger.debug(
                    f"Polled {len(msgs)} messages from partition {topic_partition.partition}"
                )
            
            if messages:
                self.logger.info(f"📦 Consumed batch of {len(messages)} messages")
            
            return messages
            
        except Exception as e:
            self.logger.error(f"❌ Error consuming batch: {e}")
            return []

    def commit(self):
        """
        Manually commit offsets (use when auto_commit is False)
        Call this after successfully processing a batch
        """
        try:
            if self.enable_auto_commit:
                self.logger.warning("⚠️  Auto-commit is enabled, manual commit not needed")
                return
            
            self.consumer.commit()
            self.logger.debug("✅ Offsets committed successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error committing offsets: {e}")
            raise

    def commit_async(self, callback=None):
        """
        Asynchronously commit offsets
        More efficient for high-throughput scenarios
        """
        try:
            if self.enable_auto_commit:
                self.logger.warning("⚠️  Auto-commit is enabled, manual commit not needed")
                return
            
            self.consumer.commit_async(callback=callback)
            self.logger.debug("🔄 Async offset commit initiated")
            
        except Exception as e:
            self.logger.error(f"❌ Error in async commit: {e}")
            raise

    def __call__(self, limit=-1):
        """
        Make the class callable - returns a generator of messages
        Usage: for msg in consumer(limit=5):
        
        Note: This is for simple iteration. For batch processing with manual commits,
        use consume_batch() method instead.
        """
        return self.consume_messages(limit)

    def __iter__(self):
        """
        Make the class iterable - allows: for msg in consumer:
        
        Note: This is for simple iteration. For batch processing with manual commits,
        use consume_batch() method instead.
        """
        return self.consume_messages()

    def consume_messages(self, limit=-1):
        """
        Generator that yields messages one by one
        
        Note: For efficient batch processing with Elasticsearch,
        use consume_batch() method instead
        """
        try:
            # Ensure partitions are assigned
            if not self._partitions_assigned:
                self._ensure_partitions_assigned()
            
            cnt = 0
            for msg in self.consumer:
                yield msg
                cnt += 1
                if limit > 0 and cnt >= limit:
                    break
                    
        except KeyboardInterrupt:
            self.logger.info("🛑 Consumption interrupted by user")
            self.close()
        except Exception as e:
            self.logger.error(f"❌ Error consuming messages: {e}")
            self.close()
            raise

    def print_messages(self, limit=-1):
        """Print messages (for debugging)"""
        for msg in self.consume_messages(limit):
            print(f"Partition {msg.partition}, Offset {msg.offset}: {msg.value}")

    def get_consumer_lag(self):
        """
        Get consumer lag information
        Ensures partitions are assigned before checking lag
        """
        try:
            # Ensure partitions are assigned first
            if not self._partitions_assigned:
                self._ensure_partitions_assigned()
            
            lag_info = {}
            assignment = self.consumer.assignment()
            
            if not assignment:
                self.logger.warning("⚠️  No partitions assigned to consumer")
                return lag_info
            
            # Get current offsets
            for partition in assignment:
                try:
                    current_offset = self.consumer.position(partition)
                    end_offset = self.consumer.end_offsets([partition])[partition]
                    lag = end_offset - current_offset
                    
                    lag_info[partition.partition] = {
                        'current_offset': current_offset,
                        'end_offset': end_offset,
                        'lag': lag
                    }
                except Exception as e:
                    self.logger.warning(f"⚠️  Could not get lag for partition {partition.partition}: {e}")
            
            total_lag = sum(info['lag'] for info in lag_info.values())
            self.logger.info(f"📊 Total consumer lag: {total_lag} messages")
            
            return lag_info
            
        except Exception as e:
            self.logger.error(f"❌ Error getting consumer lag: {e}")
            return {}

    def close(self):
        """Close consumer and cleanup"""
        try:
            if hasattr(self, 'consumer') and self.consumer:
                # Commit any pending offsets before closing
                if not self.enable_auto_commit:
                    try:
                        self.consumer.commit()
                        self.logger.info("✅ Final offset commit before closing")
                    except Exception as e:
                        self.logger.warning(f"⚠️  Could not commit offsets on close: {e}")
                
                self.consumer.close()
                
            if hasattr(self, 'topic_manager') and self.topic_manager:
                self.topic_manager.close()
                
            self.logger.info("✅ Consumer closed successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error in closing Consumer: {e}")
            raise

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False
