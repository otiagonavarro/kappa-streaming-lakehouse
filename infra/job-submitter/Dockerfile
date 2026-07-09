FROM apache/flink:1.18.1-scala_2.12-java11

USER root

RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-dev curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
    "requests>=2.31" \
    "psycopg2-binary>=2.9" \
    "click>=8.1"

# Drop connector JARs into Flink's lib dir (this is what FLINK_HOME/lib resolves to at runtime)
RUN curl -fsSL \
    "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.2-1.18/flink-sql-connector-kafka-3.0.2-1.18.jar" \
    -o "/opt/flink/lib/flink-sql-connector-kafka-3.0.2-1.18.jar" \
 && curl -fsSL \
    "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-flink-runtime-1.18/1.6.1/iceberg-flink-runtime-1.18-1.6.1.jar" \
    -o "/opt/flink/lib/iceberg-flink-runtime-1.18-1.6.1.jar" \
 && curl -fsSL \
    "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-aws-bundle/1.6.1/iceberg-aws-bundle-1.6.1.jar" \
    -o "/opt/flink/lib/iceberg-aws-bundle-1.6.1.jar" \
 && curl -fsSL \
    "https://repo1.maven.org/maven2/org/apache/flink/flink-connector-jdbc/3.1.2-1.18/flink-connector-jdbc-3.1.2-1.18.jar" \
    -o "/opt/flink/lib/flink-connector-jdbc-3.1.2-1.18.jar" \
 && curl -fsSL \
    "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar" \
    -o "/opt/flink/lib/postgresql-42.7.3.jar" \
 && cp /opt/flink/opt/flink-s3-fs-hadoop-1.18.1.jar /opt/flink/lib/ \
 && curl -fsSL \
    "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-common/3.3.6/hadoop-common-3.3.6.jar" \
    -o "/opt/flink/lib/hadoop-common-3.3.6.jar" \
 && curl -fsSL \
    "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-hdfs-client/3.3.6/hadoop-hdfs-client-3.3.6.jar" \
    -o "/opt/flink/lib/hadoop-hdfs-client-3.3.6.jar"

WORKDIR /app

COPY infra/job-submitter/submit_jobs.py .
COPY flink-jobs/src/ ./jobs/

# Use system Flink's PyFlink (avoids bundled-JAR bloat from the pip package)
ENV PYTHONPATH=/opt/flink/opt/python/pyflink.zip:/opt/flink/opt/python/py4j-0.10.9.7-src.zip:/app

CMD ["python3", "submit_jobs.py"]
