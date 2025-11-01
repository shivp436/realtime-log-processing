from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone

from KafkaModule.Producer import Producer
from FakerModule.GenerateFake import GenerateFakeWebsiteLog
from Helpers.utils import LogParser

default_args = {
    'owner': 'shivp436',
    'start_date': datetime(2021, 1, 1, tzinfo=timezone.utc),
    'retries': 1,
    'retry_delay': timedelta(seconds=5)
}

def produce_web_logs():
    """
    Generate and send fake web logs to Kafka
    Each log is sent with a unique key for at-most-once delivery
    """
    fake_logger = GenerateFakeWebsiteLog()
    parser = LogParser()
    topic = "web-logs-topic"
    
    with Producer(topic) as producer:
        try:
            num_logs = 1000  # Reduced for more frequent, smaller batches
            success_count = 0
            
            for i in range(num_logs):
                # Generate raw log entry
                log_entry = fake_logger.get_log()
                
                # Parse the log to get structured data
                parsed_log = parser.parse_log(log_entry)
                
                if parsed_log:
                    # Send parsed log (producer will auto-generate key)
                    # The key will be used for partitioning and as unique ID in Elasticsearch
                    future = producer.send(value=parsed_log)
                    
                    # Wait for confirmation (optional, for reliability)
                    try:
                        record_metadata = future.get(timeout=10)
                        success_count += 1
                        print(
                            f"✅ Log {i+1}/{num_logs}: "
                            f"partition={record_metadata.partition}, "
                            f"offset={record_metadata.offset}"
                        )
                    except Exception as e:
                        print(f"❌ Failed to send log {i+1}: {e}")
                else:
                    print(f"⚠️  Failed to parse log {i+1}")
            
            # Flush remaining messages
            producer.flush()
            print(f"🎉 Successfully sent {success_count}/{num_logs} logs!")
            
        except Exception as e:
            print(f"❌ Error in produce_web_logs: {e}")
            raise

with DAG(
    dag_id="log-producer",
    schedule="* * * * *",  # Every 2 minutes for more manageable batches
    catchup=False,
    tags=["logs", "kafka", "production"],
    default_args=default_args
) as dag:
    
    produce_web_logs_task = PythonOperator(
        task_id='produce_web_logs_task',
        python_callable=produce_web_logs
    )
