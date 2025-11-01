# Quick Reference Guide

## 🚀 Quick Start

```bash
# 1. Make scripts executable
chmod +x start.sh stop.sh

# 2. Start everything
./start.sh

# 3. Enable DAGs in Airflow UI (http://localhost:8081)
#    - log-producer
#    - log-consumer

# 4. View logs in Kibana (http://localhost:5601)
```

## 📦 Architecture Components

| Component | Purpose | Port |
|-----------|---------|------|
| **Kafka** | Message broker | 29092, 39092 |
| **Airflow** | Workflow orchestration | 8081 |
| **Elasticsearch** | Log storage & indexing | 9200 |
| **Kibana** | Log visualization | 5601 |

## 🔄 Data Flow

```
Producer DAG (every 2min)
    ↓ generates 100 logs
Kafka Topic (web-logs-topic)
    ↓ stores in 6 partitions
Consumer DAG (every 1min)
    ↓ consumes 2500 logs/run
Elasticsearch (web-logs-topic index)
    ↓ indexed with unique IDs
Kibana Dashboard
    ↓ visualize & analyze
```

## 🔑 Key Features

### At-Most-Once Delivery
- **Unique Keys**: Each log has a unique key (ip + timestamp + endpoint)
- **Document IDs**: Same key used as Elasticsearch document ID
- **Idempotent**: Duplicate messages don't create duplicate documents

### Manual Commit Pattern
```python
# 1. Consume batch from Kafka
messages = consumer.consume_batch(500)

# 2. Index to Elasticsearch
success, errors = es_client.bulk_index(documents)

# 3. Commit only if successful
if errors == 0:
    consumer.commit()  # ✅ Safe to commit
```

## 📊 Monitoring Commands

### Check Pipeline Health
```bash
# All services status
docker ps

# Producer status
docker logs airflow-worker | grep "log-producer"

# Consumer status  
docker logs airflow-worker | grep "log-consumer"

# Consumer lag
kafka-consumer-groups.sh --bootstrap-server localhost:29092 \
  --group elasticsearch-consumer-group --describe
```

### Elasticsearch Queries
```bash
# Document count
curl http://localhost:9200/web-logs-topic/_count

# Index stats
curl http://localhost:9200/web-logs-topic/_stats

# Sample documents
curl http://localhost:9200/web-logs-topic/_search?size=5&pretty

# Search by status code
curl -X GET "http://localhost:9200/web-logs-topic/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"term": {"status_code": 404}}}'
```

### Kafka Operations
```bash
# List topics
kafka-topics.sh --bootstrap-server localhost:29092 --list

# Topic details
kafka-topics.sh --bootstrap-server localhost:29092 \
  --describe --topic web-logs-topic

# Consumer groups
kafka-consumer-groups.sh --bootstrap-server localhost:29092 --list
```

## 🐛 Troubleshooting

### Producer Not Sending
```bash
# Check Airflow worker logs
docker logs airflow-worker -f

# Check if Kafka is reachable
docker exec airflow-worker ping kafka-broker-1
docker exec airflow-worker nc -zv kafka-broker-1 19092

# Manually trigger DAG in Airflow UI
```

### Consumer Not Consuming
```bash
# Check consumer group exists
kafka-consumer-groups.sh --bootstrap-server localhost:29092 --list

# Check offsets
kafka-consumer-groups.sh --bootstrap-server localhost:29092 \
  --group elasticsearch-consumer-group --describe

# Reset offsets (if needed)
kafka-consumer-groups.sh --bootstrap-server localhost:29092 \
  --group elasticsearch-consumer-group --reset-offsets \
  --to-earliest --topic web-logs-topic --execute
```

### Elasticsearch Issues
```bash
# Check cluster health
curl http://localhost:9200/_cluster/health?pretty

# Check if index exists
curl http://localhost:9200/_cat/indices?v

# Delete and recreate index
curl -X DELETE http://localhost:9200/web-logs-topic
# Consumer will recreate it automatically
```

### Kibana Not Showing Data
1. **Check index exists**: `curl http://localhost:9200/_cat/indices`
2. **Check document count**: `curl http://localhost:9200/web-logs-topic/_count`
3. **Recreate data view** in Kibana with pattern `web-logs-topic*`
4. **Set timestamp field** to `indexed_at`
5. **Adjust time range** in Discover (top right)

## ⚙️ Configuration Tuning

### Increase Throughput

**Producer** (`dags/log-producer.py`):
```python
num_logs = 500  # More logs per run
schedule="* * * * *"  # Run every minute
```

**Consumer** (`dags/log-consumer.py`):
```python
batch_size = 1000  # Larger batches
max_batches = 10  # Process more per run
```

**Kafka Topic**:
```bash
# Add more partitions for parallelism
kafka-topics.sh --bootstrap-server localhost:29092 \
  --alter --topic web-logs-topic --partitions 12
```

### Reduce Latency

**Producer**:
```python
producer = KafkaProducer(
    linger_ms=0,  # Send immediately
    batch_size=0  # No batching
)
```

**Consumer**:
```python
consumer = Consumer(
    max_poll_records=100,  # Smaller batches
)
```

## 📈 Kibana Visualizations

### Create Index Pattern
1. **Management** → **Data Views**
2. **Create data view**
3. Index pattern: `web-logs-topic*`
4. Timestamp: `indexed_at`

### Useful Visualizations

**1. Status Code Distribution**
- Visualization: Pie Chart
- Bucket: Terms aggregation on `status_code`

**2. Requests Over Time**
- Visualization: Line Chart
- X-axis: Date Histogram on `indexed_at`
- Y-axis: Count

**3. Top Endpoints**
- Visualization: Bar Chart
- Bucket: Terms aggregation on `endpoint.keyword`

**4. Error Rate**
- Visualization: Metric
- Filter: `status_code >= 400`
- Aggregation: Count

**5. Geographic Traffic** (if IP geolocation enabled)
- Visualization: Map
- Layer: Clusters based on `ip_address`

## 🔐 Production Considerations

### Security
```yaml
# Enable Elasticsearch security
xpack.security.enabled=true

# Add SSL/TLS
xpack.security.http.ssl.enabled=true

# Kafka authentication
KAFKA_SASL_MECHANISM=PLAIN
```

### Monitoring
- Add Prometheus exporters
- Set up Grafana dashboards
- Configure alerting rules

### Data Retention
```bash
# Set up Index Lifecycle Management
curl -X PUT "http://localhost:9200/_ilm/policy/logs-policy" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy": {
      "phases": {
        "hot": {"actions": {}},
        "delete": {"min_age": "7d", "actions": {"delete": {}}}
      }
    }
  }'
```

## 🛠️ Useful Scripts

### Bulk Delete Logs
```bash
# Delete all documents
curl -X POST "http://localhost:9200/web-logs-topic/_delete_by_query" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match_all": {}}}'
```

### Reset Everything
```bash
# Stop services
./stop.sh

# Remove all volumes
docker volume prune -f

# Restart
./start.sh
```

### Check Resource Usage
```bash
# Docker stats
docker stats

# Elasticsearch heap
curl http://localhost:9200/_nodes/stats/jvm?pretty

# Kafka disk usage
docker exec kafka-broker-1 du -sh /var/lib/kafka/data
```

## 📞 Support

- **Logs**: `docker logs <container_name>`
- **Airflow Task Logs**: Available in Airflow UI
- **Health Checks**: All services have health endpoints
