from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import os

from KafkaModule.Consumer import Consumer
from ElasticsearchModule.ElasticsearchClient import ElasticsearchClient

default_args = {
    'owner': 'shivp436',
    'start_date': datetime(2021, 1, 1, tzinfo=timezone.utc),
    'retries': 2,
    'retry_delay': timedelta(seconds=10)
}

def consume_and_index_logs():
    """
    Consume logs from Kafka and bulk index them into Elasticsearch
    Uses manual commit for at-least-once delivery guarantee
    Exits early if no messages are pending
    """
    topic = "web-logs-topic"
    group_id = "elasticsearch-consumer-group"
    index_name = "web-logs-topic"  # Same as topic name
    batch_size = 500  # Process 500 messages per batch
    max_empty_polls = 3  # Exit after 3 consecutive empty polls
    
    # Create consumer with auto_commit=False for manual control
    consumer = Consumer(
        topic=topic,
        group_id=group_id,
        enable_auto_commit=False,  # Manual commit after successful indexing
        max_poll_records=batch_size
    )
    
    # Create Elasticsearch client
    es_client = ElasticsearchClient(index_name=index_name)
    
    try:
        print(f"🚀 Starting to consume from topic '{topic}' and index to '{index_name}'")
        print(f"📡 Starting to poll for messages...")
        
        # Check lag after ensuring partitions are assigned
        lag_info = consumer.get_consumer_lag()
        total_lag = sum(info['lag'] for info in lag_info.values())
        print(f"📊 Initial consumer lag: {total_lag} messages")
        
        if total_lag == 0:
            print(f"ℹ️  No messages pending (lag=0). Exiting early.")
            return
        
        # Consume messages in batches
        total_indexed = 0
        batch_count = 0
        empty_poll_count = 0
        max_batches = 20  # Process max 20 batches per DAG run (10,000 messages)
        
        while batch_count < max_batches and empty_poll_count < max_empty_polls:
            # Consume a batch of messages
            messages = consumer.consume_batch(
                max_messages=batch_size,
                timeout_ms=5000  # 5 second timeout
            )
            
            if not messages:
                empty_poll_count += 1
                print(f"ℹ️  Empty poll #{empty_poll_count}/{max_empty_polls}")
                
                # Check lag to see if we're truly caught up
                lag_info = consumer.get_consumer_lag()
                current_lag = sum(info['lag'] for info in lag_info.values())
                
                if current_lag == 0:
                    print(f"✅ Caught up! No more messages to process (lag=0)")
                    break
                else:
                    print(f"⚠️  Still {current_lag} messages pending, continuing...")
                
                continue
            
            # Reset empty poll counter if we got messages
            empty_poll_count = 0
            batch_count += 1
            print(f"\n📦 Processing batch {batch_count} with {len(messages)} messages")
            
            # Extract message values AND keys for bulk indexing
            documents = []
            kafka_keys = []
            
            for msg in messages:
                if msg.value:  # Skip null values
                    doc = msg.value
                    # Add Kafka metadata to document
                    doc['kafka_partition'] = msg.partition
                    doc['kafka_offset'] = msg.offset
                    doc['kafka_timestamp'] = msg.timestamp
                    documents.append(doc)
                    # Store Kafka key for document ID
                    kafka_keys.append(msg.key if msg.key else None)
            
            if documents:
                # Bulk index to Elasticsearch with Kafka keys
                print(f"📥 Indexing {len(documents)} documents to Elasticsearch...")
                success_count, error_count = es_client.bulk_index(
                    documents=documents,
                    kafka_keys=kafka_keys,  # Pass Kafka keys for document IDs
                    chunk_size=500
                )
                
                if error_count > 0:
                    print(f"⚠️  Some documents failed to index: {error_count} errors")
                    # You might want to handle errors differently here
                    # For now, we'll still commit if majority succeeded
                    if error_count > success_count:
                        raise Exception(
                            f"Too many indexing errors: {error_count}/{len(documents)}"
                        )
                
                # Commit offsets only after successful indexing
                consumer.commit()
                print(f"✅ Committed offsets after indexing {success_count} documents")
                
                total_indexed += success_count
            else:
                print("⚠️  No valid documents in batch")
        
        # Get final statistics
        lag_info = consumer.get_consumer_lag()
        final_lag = sum(info['lag'] for info in lag_info.values())
        stats = es_client.get_index_stats()
        
        print(f"\n📊 Summary:")
        print(f"   - Processed {batch_count} batches")
        print(f"   - Indexed {total_indexed} documents in this run")
        print(f"   - Total documents in index: {stats.get('doc_count', 0)}")
        print(f"   - Index size: {stats.get('size_mb', 0):.2f} MB")
        print(f"   - Current consumer lag: {final_lag} messages")
        print(f"   - Status: {'✅ Caught up!' if final_lag == 0 else '⚠️  More messages pending'}")
        
        if total_indexed > 0:
            print(f"🎉 Log consumption and indexing completed successfully!")
        else:
            print(f"ℹ️  No new messages to process.")
        
    except Exception as e:
        print(f"❌ Error in consume_and_index_logs: {e}")
        import traceback
        traceback.print_exc()
        raise
        
    finally:
        # Clean up resources
        consumer.close()
        es_client.close()

with DAG(
    dag_id="log-consumer",
    schedule="*/2 * * * *",  # Run every minute
    catchup=False,
    tags=["logs", "kafka", "elasticsearch", "consumer"],
    default_args=default_args,
    max_active_runs=1  # Prevent overlapping runs
) as dag:
    
    consume_and_index_task = PythonOperator(
        task_id='consume_and_index_logs',
        python_callable=consume_and_index_logs,
        execution_timeout=timedelta(minutes=5)  # Kill if takes too long
    )
