from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import logging

default_args = {
    'owner': 'shivp436',
    'start_date': datetime(2021, 1, 1, tzinfo=timezone.utc),
    'retries': 1,
    'retry_delay': timedelta(seconds=5)
}

def produce_web_logs():
    """
    Generate and send fake web logs to Kafka
    """
    # HEAVY IMPORTS INSIDE THE FUNCTION
    from KafkaModule.Producer import Producer
    from FakerModule.GenerateFake import GenerateFakeWebsiteLog
    from Helpers.utils import LogParser
    
    logger = logging.getLogger(__name__)
    
    fake_logger = GenerateFakeWebsiteLog()
    parser = LogParser()
    topic = "web-logs-topic"
    
    producer = None
    
    try:
        producer = Producer(topic)
        num_logs = 1000
        success_count = 0
        failed_count = 0
        
        logger.info(f"🚀 Starting to produce {num_logs} logs to topic '{topic}'")
        
        for i in range(num_logs):
            log_entry = fake_logger.get_log()
            parsed_log = parser.parse_log(log_entry)
            
            if parsed_log:
                future = producer.send(value=parsed_log)
                
                try:
                    record_metadata = future.get(timeout=10)
                    success_count += 1
                    if (i + 1) % 200 == 0:  # Log every 200 messages
                        logger.info(
                            f"📤 Progress: {i+1}/{num_logs} logs sent "
                            f"(partition={record_metadata.partition}, offset={record_metadata.offset})"
                        )
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Failed to send log {i+1}: {e}")
            else:
                failed_count += 1
                logger.warning(f"⚠️  Failed to parse log {i+1}")
        
        producer.flush()
        
        logger.info(f"📊 Summary: Successfully sent {success_count}/{num_logs} logs")
        if failed_count > 0:
            logger.warning(f"⚠️  Failed: {failed_count} logs")
        
        if success_count == num_logs:
            logger.info(f"🎉 All logs sent successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error in produce_web_logs: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if producer:
            producer.close()
            logger.info("✅ Producer closed")

with DAG(
    dag_id="log-producer",
    schedule="* * * * *",
    catchup=False,
    tags=["logs", "kafka", "production"],
    default_args=default_args,
    max_active_runs=1
) as dag:
    
    produce_web_logs_task = PythonOperator(
        task_id='produce_web_logs_task',
        python_callable=produce_web_logs,
        execution_timeout=timedelta(minutes=2)
    )
