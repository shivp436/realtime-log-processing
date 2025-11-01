#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color 

# Function to build and verify
build_service() {
    local service_name=$1
    local compose_file=$2
    echo -e "${YELLOW}🚀 Building $service_name...${NC}"
    
    if docker compose -f "$compose_file" build --no-cache --no-parallel; then
        echo -e "${GREEN}✅ $service_name built successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name build failed${NC}"
        return 1
    fi
}

echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}Building Real-Time Log Processing Pipeline Containers${NC}"
echo -e "${GREEN}===================================================${NC}\n"

# Build services sequentially
build_service "Kafka cluster" "kafka-compose.yml" || exit 1
build_service "Elasticsearch and Kibana" "elasticsearch-compose.yml" || exit 1

echo -e "${YELLOW}🚀 Setting up Airflow...${NC}"

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

build_service "Airflow" "airflow-compose.yml" || exit 1

echo -e "${GREEN}🎉 All builds completed successfully!${NC}"
