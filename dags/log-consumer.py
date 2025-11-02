from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import logging

# LIGHTWEIGHT IMPORTS ONLY - no heavy initialization
default_args = {
    'owner': 'shivp436',
    'start_date': datetime(2021, 1, 1, tzinfo=timezone.utc),
    'retries': 2,
    'retry_delay': timedelta(seconds=10)
}

def consume_and_index_logs():
    """
    Consume logs from Kafka and bulk index them into Elasticsearch
    """
    # HEAVY IMPORTS INSIDE THE FUNCTION - only when task executes
    from KafkaModule.Consumer import Consumer
    from ElasticsearchModule.ElasticsearchClient import ElasticsearchClient
    
    logger = logging.getLogger(__name__)
    
    topic = "web-logs-topic"
    group_id = "elasticsearch-consumer-group"
    index_name = "web-logs-topic"
    batch_size = 1000  # Increased batch size
    max_empty_polls = 5  # Increased tolerance
    
    consumer = None
    es_client = None
    
    try:
        # Create consumer with auto_commit=False for manual control
        consumer = Consumer(
            topic=topic,
            group_id=group_id,
            enable_auto_commit=False,
            max_poll_records=batch_size
        )
        
        # Create Elasticsearch client
        es_client = ElasticsearchClient(index_name=index_name)
        
        logger.info(f"🚀 Starting to consume from topic '{topic}' and index to '{index_name}'")
        
        # Check lag after ensuring partitions are assigned
        lag_info = consumer.get_consumer_lag()
        total_lag = sum(info['lag'] for info in lag_info.values())
        logger.info(f"📊 Initial consumer lag: {total_lag} messages")
        
        if total_lag == 0:
            logger.info(f"ℹ️  No messages pending (lag=0). Exiting early.")
            return
        
        # Consume messages in batches - NO BATCH LIMIT
        total_indexed = 0
        batch_count = 0
        empty_poll_count = 0
        
        # Continue until we catch up (lag=0) or hit max empty polls
        while empty_poll_count < max_empty_polls:
            messages = consumer.consume_batch(
                max_messages=batch_size,
                timeout_ms=10000  # Increased timeout to 10 seconds
            )
            
            if not messages:
                # Check actual lag before counting as empty poll
                lag_info = consumer.get_consumer_lag()
                current_lag = sum(info['lag'] for info in lag_info.values())
                
                if current_lag == 0:
                    logger.info(f"✅ Caught up! No more messages to process (lag=0)")
                    break
                
                empty_poll_count += 1
                logger.info(f"ℹ️  Empty poll #{empty_poll_count}/{max_empty_polls} - Still {current_lag} messages pending")
                continue
            
            # Reset empty poll count on successful poll
            empty_poll_count = 0
            batch_count += 1
            logger.info(f"📦 Processing batch {batch_count} with {len(messages)} messages")
            
            documents = []
            kafka_keys = []
            
            for msg in messages:
                if msg.value:
                    doc = msg.value
                    doc['kafka_partition'] = msg.partition
                    doc['kafka_offset'] = msg.offset
                    doc['kafka_timestamp'] = msg.timestamp
                    documents.append(doc)
                    kafka_keys.append(msg.key if msg.key else None)
            
            if documents:
                logger.info(f"🔥 Indexing {len(documents)} documents to Elasticsearch...")
                success_count, error_count = es_client.bulk_index(
                    documents=documents,
                    kafka_keys=kafka_keys,
                    chunk_size=500
                )
                
                if error_count > 0:
                    logger.warning(f"⚠️  Some documents failed to index: {error_count} errors")
                    if error_count > success_count:
                        raise Exception(
                            f"Too many indexing errors: {error_count}/{len(documents)}"
                        )
                
                consumer.commit()
                logger.info(f"✅ Committed offsets after indexing {success_count} documents")
                total_indexed += success_count
                
                # Log progress every 5 batches
                if batch_count % 5 == 0:
                    lag_info = consumer.get_consumer_lag()
                    current_lag = sum(info['lag'] for info in lag_info.values())
                    logger.info(f"📊 Progress: {batch_count} batches, {total_indexed} indexed, {current_lag} lag remaining")
            else:
                logger.info("⚠️  No valid documents in batch")
        
        # Get final statistics
        lag_info = consumer.get_consumer_lag()
        final_lag = sum(info['lag'] for info in lag_info.values())
        stats = es_client.get_index_stats()
        
        logger.info(f"📊 Summary: Processed {batch_count} batches, Indexed {total_indexed} documents")
        logger.info(f"📊 Total in index: {stats.get('doc_count', 0)}, Size: {stats.get('size_mb', 0):.2f} MB")
        logger.info(f"📊 Final lag: {final_lag} messages")
        
        if final_lag == 0:
            logger.info(f"🎉 Successfully caught up! Lag is now 0.")
        elif total_indexed > 0:
            logger.info(f"✅ Processed {total_indexed} documents. Remaining lag: {final_lag}")
        else:
            logger.info(f"ℹ️  No new messages to process.")
        
    except Exception as e:
        logger.error(f"❌ Error in consume_and_index_logs: {e}")
        import traceback
        traceback.print_exc()
        raise
        
    finally:
        if consumer:
            consumer.close()
        if es_client:
            es_client.close()

with DAG(
    dag_id="log-consumer",
    schedule="*/5 * * * *",
    catchup=False,
    tags=["logs", "kafka", "elasticsearch", "consumer"],
    default_args=default_args,
    max_active_runs=1
) as dag:
    
    consume_and_index_task = PythonOperator(
        task_id='consume_and_index_logs',
        python_callable=consume_and_index_logs,
        execution_timeout=timedelta(minutes=5)
    )
