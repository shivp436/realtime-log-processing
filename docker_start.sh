#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color 

echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}Starting Real-Time Log Processing Pipeline Containers${NC}"
echo -e "${GREEN}===================================================${NC}\n"

echo -e "${YELLOW}🚀 Starting Kafka cluster...${NC}"
docker compose -f kafka-compose.yml up -d

echo -e "${YELLOW}🚀 Starting Elasticsearch and Kibana...${NC}"
docker compose -f elasticsearch-compose.yml up -d

echo -e "${YELLOW}🚀 Starting Airflow...${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating default .env file...${NC}"
    cat > .env << EOF
# Airflow Configuration
AIRFLOW_UID=$(id -u)
AIRFLOW_PROJ_DIR=.
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow

# Kafka Configuration (for containers)
KAFKA_BOOTSTRAP_SERVERS=kafka-broker-1:19092,kafka-broker-2:19092

# Elasticsearch Configuration (for containers)
ELASTICSEARCH_HOSTS=http://elasticsearch:9200
EOF
    echo -e "${GREEN}✅ Created .env file${NC}\n"
fi

docker compose -f airflow-compose.yml up -d
