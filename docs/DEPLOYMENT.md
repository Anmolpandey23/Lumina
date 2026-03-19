# Production Deployment Guide

This guide covers deploying Lumina to production environments.

## Pre-Production Checklist

### Code Quality
- [ ] All endpoints tested with unit tests
- [ ] Error handling covers edge cases
- [ ] Input validation is comprehensive
- [ ] Logging is structured
- [ ] No hardcoded secrets or sensitive data
- [ ] Code reviewed for security issues

### Infrastructure
- [ ] Database chosen and configured (PostgreSQL recommended)
- [ ] Vector database planned (Pinecone, Supabase, or Weaviate)
- [ ] Monitoring and alerting set up
- [ ] Backup strategy implemented
- [ ] SSL/TLS certificates ready

### Security
- [ ] API key management (use HashiCorp Vault or similar)
- [ ] CORS properly configured (don't use `*`)
- [ ] Rate limiting tuned for your scale
- [ ] Sensitive content filtering tested
- [ ] Security headers configured
- [ ] HTTPS enforced

### Documentation
- [ ] API documentation available
- [ ] Runbook for common issues
- [ ] Disaster recovery procedures
- [ ] Data retention policies documented

## Docker Deployment

### Build Docker Image

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/app ./app
COPY backend/main.py .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run application
CMD ["python", "main.py"]
```

### Build and Push

```bash
# Build image
docker build -t ai-copilot:latest .

# Tag for registry
docker tag ai-copilot:latest your-registry/ai-copilot:latest

# Push to Docker Hub or private registry
docker push your-registry/ai-copilot:latest

# Run locally to test
docker run -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=INFO \
  -e OPENAI_API_KEY=${OPENAI_API_KEY} \
  ai-copilot:latest
```

## Kubernetes Deployment

### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-copilot-backend
  labels:
    app: ai-copilot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-copilot
  template:
    metadata:
      labels:
        app: ai-copilot
    spec:
      containers:
      - name: backend
        image: your-registry/ai-copilot:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: ENVIRONMENT
          value: production
        - name: PORT
          value: "8000"
        - name: LOG_LEVEL
          value: INFO
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: openai-key
        - name: VALID_API_KEYS
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: valid-keys
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /api/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        volumeMounts:
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: logs
        emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - ai-copilot
              topologyKey: kubernetes.io/hostname
---
apiVersion: v1
kind: Service
metadata:
  name: ai-copilot-service
spec:
  selector:
    app: ai-copilot
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-copilot-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-copilot-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Deploy to Kubernetes

```bash
# Apply manifests
kubectl apply -f deployment.yaml

# Verify deployment
kubectl get pods -l app=ai-copilot
kubectl logs deployment/ai-copilot-backend

# Check service
kubectl get svc ai-copilot-service

# Port forward for testing
kubectl port-forward svc/ai-copilot-service 8000:80
curl http://localhost:8000/health
```

## Database Setup

### PostgreSQL + pgvector

```sql
-- Install pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    pages JSONB DEFAULT '[]',
    queries JSONB DEFAULT '[]',
    total_tokens_used INT DEFAULT 0,
    private_mode BOOLEAN DEFAULT FALSE
);

-- Create embeddings table
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    page_url TEXT NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Create indexes for performance
CREATE INDEX idx_session_id ON sessions(session_id);
CREATE INDEX idx_page_url ON embeddings(page_url);
CREATE INDEX idx_embedding_similarity ON embeddings USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_created_at ON embeddings(created_at);
```

### Connect in Backend

Update `backend/app/database/` with SQLAlchemy models:

```python
# app/database/models.py
from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, VECTOR
import uuid

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # ...

class Embedding(Base):
    __tablename__ = "embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), nullable=False)
    page_url = Column(String, nullable=False)
    text = Column(String, nullable=False)
    embedding = Column(VECTOR(384))
    # ...
```

## Monitoring & Observability

### Prometheus Metrics

```python
# app/utils/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
request_count = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
request_duration = Histogram('api_request_duration', 'Request duration in seconds', ['endpoint'])
active_sessions = Gauge('active_sessions', 'Number of active sessions')
retrieval_quality = Gauge('retrieval_quality', 'Mean retrieval score')

# Example usage in route
@app.post("/api/chat")
async def chat(request: ChatRequest):
    with request_duration.labels(endpoint='chat').time():
        # ... your code
        request_count.labels(method='POST', endpoint='chat').inc()
```

### ELK Stack Setup (Elasticsearch + Logstash + Kibana)

```yaml
# docker-compose.yml for ELK
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
    environment:
      discovery.type: single-node
      xpack.security.enabled: "false"
    ports:
      - "9200:9200"
    volumes:
      - es-data:/usr/share/elasticsearch/data

  kibana:
    image: docker.elastic.co/kibana/kibana:8.0.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

volumes:
  es-data:
```

### Grafana Dashboards

```json
// Example dashboard JSON for Grafana
{
  "dashboard": {
    "title": "Lumina Backend Metrics",
    "panels": [
      {
        "title": "API Response Time (p95)",
        "targets": [
          {"expr": "histogram_quantile(0.95, api_request_duration)"}
        ]
      },
      {
        "title": "Active Sessions",
        "targets": [
          {"expr": "active_sessions"}
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {"expr": "rate(api_requests_total{status=~'5..'}[5m])"}
        ]
      }
    ]
  }
}
```

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
name: Deploy Lumina

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        cd backend
        pytest --cov=app tests/
    
    - name: Check code quality
      run: |
        cd backend
        pip install flake8 black mypy
        flake8 app/
        black --check app/
        mypy app/

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: |
          your-registry/ai-copilot:latest
          your-registry/ai-copilot:${{ github.sha }}
    
    - name: Deploy to Kubernetes
      run: |
        kubectl set image deployment/ai-copilot-backend \
          backend=your-registry/ai-copilot:${{ github.sha }}
```

## Running Locally in Docker

```bash
# Build image
docker build -t ai-copilot-dev .

# Run with environment file
docker run -p 8000:8000 \
  --env-file config/.env.development \
  -v $(pwd)/backend/logs:/app/logs \
  ai-copilot-dev

# Or use docker-compose
cat > docker-compose.yml << EOF
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      ENVIRONMENT: development
      LOG_LEVEL: DEBUG
    volumes:
      - ./backend/logs:/app/logs
    networks:
      - ai-copilot
  
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: ai_copilot
    ports:
      - "5432:5432"
    networks:
      - ai-copilot

networks:
  ai-copilot:
    driver: bridge
EOF

docker-compose up
```

## Maintenance & Operations

### Backup Strategy

```bash
#!/bin/bash
# backup.sh - Daily backup script

BACKUP_DIR="/backups/ai-copilot"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup PostgreSQL
pg_dump $DATABASE_URL | gzip > $BACKUP_DIR/db-$DATE.sql.gz

# Backup embeddings (if using local storage)
tar -czf $BACKUP_DIR/embeddings-$DATE.tar.gz .embedding_cache/

# Upload to S3
aws s3 cp $BACKUP_DIR/ s3://ai-copilot-backups/$DATE/ --recursive

# Delete local backups older than 7 days
find $BACKUP_DIR -type f -mtime +7 -delete
```

### Monitoring Script

```bash
#!/bin/bash
# monitor.sh - Check all services

echo "=== API Health ==="
curl -s http://localhost:8000/health | jq .

echo "=== Database Connection ==="
psql -c "SELECT now();" 2>&1 | head -1

echo "=== Disk Usage ==="
du -sh /app /var/lib/postgresql/

echo "=== Memory Usage ==="
free -h

echo "=== CPU Usage ==="
top -bn1 | head -10
```

## Disaster Recovery

### Recovery Procedure

1. **Database Recovery**
   ```bash
   # Restore from backup
   psql $DATABASE_URL < backup.sql
   ```

2. **Reindex Embeddings**
   ```bash
   python -c "from app.rag import RAGPipeline; RAGPipeline().rebuild_indexes()"
   ```

3. **Clear Cache & Restart**
   ```bash
   rm -rf .embedding_cache/
   systemctl restart ai-copilot
   ```

### Testing Recovery

```bash
# Simulate backup/restore monthly
# Document time taken (RTO)
# Verify data integrity post-restore
```

---

**Refer to main README for additional information on features and architecture.**
