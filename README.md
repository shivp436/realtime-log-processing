## Realtime Log Processing using Apache Airflow, Kafka, Elastisearch
An intermediate level project on logging website events using Airflow, Kafka, Elasticsearch.
Docker is good to know, not must.

### Setup:
Everything runs on Docker, so no need to set anything up on your host machine.
But if you want intellisense while writing code, make sure to create a venv and *pip install -r airflow-requirements.txt*
I have uploaded the .env because it does not have anything sensitive.

There are 2 separate docker compose files for easy understanding, kafka & airflow.

1. uv venv
2. uv pip install -r airflow-requirements.txt
3. docker compose -f airflow-compose.yml up -d
4. docker compose -f kafka-compose.yml up -d
5. docker compose -f elastic-search.yml up -d

#### Scripts to it easier:
0. make help
1. docker_build.sh: build all images required to run the containers
2. docker_start.sh: start docker containers
3. docker_stop.sh: stop all running containers, persist the data
4. docker_remove.sh: stop all running containers, delete containers & data as well

That's all, you can access both conduktor-kafka and airflow-apiserver dashboard on your host machine.
- conduktor-kafka console: http://127.0.0.1:8082
- airflow-apiserver dashboard: http://127.0.0.1:8081
- kibana dashboard: http://127.0.0.1:5601
    - /app/dev_tools#/console => REST Endpoint
    - /app/management/data/index_management/indices => UI All indices

### AI Written Documentation:
- [SETUP_GUIDE](./__docs/SETUP.md)
- [QUICK_REFERENCE](./__docs/QUICK_REF.md)
