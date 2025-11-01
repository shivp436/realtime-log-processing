# Real-Time Log Processing Pipeline Setup Guide

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Airflow DAG   │───▶│  Kafka Cluster  │───▶│ Elasticsearch   │───▶│     Kibana      │
│  (Producer)     │    │  (2 Brokers +   │    │   (Indexing)    │    │ (Visualization) │
│  Every 2 min    │    │   Controllers)  │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                │
                       ┌────────▼────────┐
                       │   Airflow DAG   │
                       │   (Consumer)    │
                       │  Every 1 min    │
                       └─────────────────┘
```

## Features

✅ **At-Most-Once Semantics**: Each log is processed exactly once using unique keys
✅ **Efficient Batch Processing**: Bulk indexing with configurable batch sizes
✅ **Manual Offset Management**: Commits only after successful Elasticsearch indexing
✅ **Modular Architecture**: Separate modules for Kafka, Elasticsearch, and business logic
✅ **Auto-scaling**: Multiple Kafka partitions for parallel processing
✅ **Monitoring**: Kibana dashboard for real-time log analytics

## Directory Structure

```
project/
├── dags/
│   ├── FakerModule/
│   │   ├── __init__.py
│   │   └── GenerateFake.py
│   ├── Helpers/
│   │   ├── __init__.py
│   │   └── utils.py
│   ├── KafkaModule/
│   │   ├── __init__.py
│   │   ├── Consumer.py
│   │   ├── Producer.py
│   │   └── TopicManager.py
│   ├── ElasticsearchModule/
│   │   ├── __init__.py
│   │   └── ElasticsearchClient.py
│   ├── log-producer.py
│   └── log-consumer.py
├── docker-compose-kafka.yml
├── docker-compose-airflow.yml
├── docker-compose-elasticsearch.yml
├── AirflowDockerfile
├── requirements.txt
└── .env
```

## Step-by-Step Setup

### 1. Prerequisites

- Docker and Docker Compose installed
- At least 8GB RAM available
- Ports available: 9200, 5601, 8081, 29092, 39092

### 2. Create Directory Structure

```bash
# Create module directories
mkdir -p dags/ElasticsearchModule
mkdir -p dags/KafkaModule
mkdir -p dags/FakerModule
mkdir -p dags/Helpers

# Create __init__.py files
touch dags/ElasticsearchModule/__init__.py
touch dags/KafkaModule/__init__.py
touch dags/FakerModule/__init__.py
touch dags/Helpers/__init__.py
```

### 3. Start Services in Order

```bash
# 1. Start Kafka cluster first
docker-compose -f docker-compose-kafka.yml up -d

# Wait for Kafka to be ready (check logs)
docker logs kafka-broker-1

# 2. Start Elasticsearch and Kibana
docker-compose -f docker-compose-elasticsearch.yml up -d

# Wait for Elasticsearch to be ready
curl http://localhost:9200/_cluster/health

# 3. Start Airflow
docker-compose -f docker-compose-airflow.yml up -d

# Check all services are running
docker ps
```

### 4. Verify Services

```bash
# Check Kafka
kafka-topics.sh --bootstrap-server localhost:29092 --list

# Check Elasticsearch
curl http://localhost:9200/_cat/indices

# Check Airflow Web UI
# Open browser: http://localhost:8081
# Login: airflow / airflow

# Check Kibana
# Open browser: http://localhost:5601
```

### 5. Enable Airflow DAGs

1. Go to Airflow UI: http://localhost:8081
2. Find `log-producer` DAG and toggle it ON
3. Find `log-consumer` DAG and toggle it ON
4. Watch them run!

### 6. View Logs in Kibana

1. Open Kibana: http://localhost:5601
2. Go to **Management** → **Stack Management** → **Data Views**
3. Click **Create data view**
4. Index pattern: `web-logs-topic*`
5. Timestamp field: `indexed_at`
6. Click **Create data view**
7. Go to **Analytics** → **Discover**
8. Select your data view and see the logs!

## Key Configuration

### Producer Settings (log-producer.py)
- Runs every 2 minutes
- Generates 100 logs per run
- Auto-generates unique keys for each log
- Partitioning across 6 Kafka partitions

### Consumer Settings (log-consumer.py)
- Runs every minute
- Processes up to 2500 messages per run (5 batches of 500)
- Manual offset commit after successful indexing
- At-most-once semantics using document IDs

### Elasticsearch Settings
- Index: `web-logs-topic`
- Shards: 2
- Replicas: 1
- Mappings optimized for log data

## Monitoring

### Check Producer Performance
```bash
# View producer logs
docker logs airflow-worker -f | grep "log-producer"

# Check Kafka topic
kafka-run-class.sh kafka.tools.GetOffsetShell \
  --broker-list localhost:29092 \
  --topic web-logs-topic
```

### Check Consumer Performance
```bash
# View consumer logs
docker logs airflow-worker -f | grep "log-consumer"

# Check consumer group lag
kafka-consumer-groups.sh --bootstrap-server localhost:29092 \
  --group elasticsearch-consumer-group \
  --describe
```

### Check Elasticsearch
```bash
# Index stats
curl http://localhost:9200/web-logs-topic/_stats?pretty

# Document count
curl http://localhost:9200/web-logs-topic/_count?pretty

# Sample documents
curl http://localhost:9200/web-logs-topic/_search?pretty&size=5
```

## Troubleshooting

### Kafka Connection Issues
```bash
# Check if Airflow can reach Kafka
docker exec -it airflow-worker ping kafka-broker-1
docker exec -it airflow-worker nc -zv kafka-broker-1 19092
```

### Elasticsearch Connection Issues
```bash
# Check if Airflow can reach Elasticsearch
docker exec -it airflow-worker curl http://elasticsearch:9200
```

### Consumer Lag Building Up
```bash
# Check consumer lag
kafka-consumer-groups.sh --bootstrap-server localhost:29092 \
  --group elasticsearch-consumer-group \
  --describe

# Solution: Increase batch size or reduce producer frequency
```

### Kibana Not Showing Data
1. Check if index exists: `curl http://localhost:9200/_cat/indices`
2. Verify data view pattern in Kibana matches index name
3. Check timestamp field is set to `indexed_at`

## Performance Tuning

### Increase Throughput
```python
# In log-producer.py
num_logs = 500  # Increase batch size

# In log-consumer.py
batch_size = 1000  # Increase batch size
max_batches = 10  # Process more batches per run
```

### Reduce Latency
```python
# In Consumer.py
max_poll_records=100  # Smaller batches

# In Producer.py
linger_ms=0  # Send immediately
```

### Scale Horizontally
```bash
# Add more Kafka partitions
kafka-topics.sh --bootstrap-server localhost:29092 \
  --alter --topic web-logs-topic --partitions 12

# Add more Airflow workers in docker-compose
```

## Stopping Services

```bash
# Stop in reverse order
docker-compose -f docker-compose-airflow.yml down
docker-compose -f docker-compose-elasticsearch.yml down
docker-compose -f docker-compose-kafka.yml down

# To remove volumes (delete all data)
docker-compose -f docker-compose-airflow.yml down -v
docker-compose -f docker-compose-elasticsearch.yml down -v
docker-compose -f docker-compose-kafka.yml down -v
```

## Next Steps

1. **Create Kibana Dashboards**:
   - Status code distribution
   - Top endpoints
   - Traffic by IP
   - Error rate over time

2. **Add Alerting**:
   - High error rates
   - Consumer lag thresholds
   - Index size limits

3. **Implement Data Retention**:
   - Index lifecycle management
   - Automatic cleanup of old logs

4. **Add Security**:
   - Enable Elasticsearch security
   - Add authentication to Kibana
   - Secure Kafka with SSL

## Support

For issues or questions:
1. Check Docker logs: `docker logs <container_name>`
2. Review Airflow task logs in the UI
3. Check Elasticsearch logs: `docker logs elasticsearch`
