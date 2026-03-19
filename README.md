# Lumina - Production-Grade Chrome Extension with RAG

**AI that illuminates every webpage** - A sophisticated Chrome extension that allows users to chat with any webpage using Retrieval-Augmented Generation (RAG). This project demonstrates real-world ML engineering, system design, scalability, and security practices suitable for a senior AI/ML engineer portfolio.

## 🎯 Features

- **Interactive Chat Interface**: Clean, modern popup UI for asking questions about the current webpage
- **Smart Content Extraction**: DOM-aware extraction that ignores ads, navigation, and clutter
- **RAG Pipeline**: Semantic chunking → Embeddings → Vector similarity search → LLM generation
- **Multi-Page Memory**: Track pages visited in a session and enable cross-page queries
- **User-Supplied LLM Keys**: Users can bring their own API key, provider, and model via extension settings — no backend key required to run Lumina
- **Private Mode**: When enabled, no session data is persisted anywhere (backend or extension storage)
- **Multiple LLM Providers**: HuggingFace, OpenAI, Google Gemini, and Ollama (local) out of the box
- **Deterministic Shortcuts**: YouTube-specific fast-path answers (notification count, subscription list, channel attribution, video lessons) skip LLM entirely
- **Conversation Follow-up Memory**: Session context injected into LLM prompt for coherent multi-turn conversations
- **Fuzzy Typo Correction**: Query spelling mistakes corrected before retrieval (original wording preserved for answer generation)
- **Security First**: Sensitive content detection, secure API validation, input sanitization
- **Production Ready**: Comprehensive logging, error handling, rate limiting, caching
- **Extensible Architecture**: Easy to swap LLM providers, embedding models, and vector databases

## 📁 Project Structure

```
Web-chat-extension/
├── extension/                      # Chrome Extension (Manifest V3)
│   ├── manifest.json
│   └── src/
│       ├── popup/                 # Popup UI & logic
│       │   ├── popup.html
│       │   ├── popup.css
│       │   └── popup.js
│       ├── content/               # DOM extraction & messaging
│       │   └── content.js
│       └── background/            # Service worker
│           └── background.js
│
├── backend/                        # FastAPI Backend
│   ├── main.py                    # FastAPI app entry point
│   ├── requirements.txt           # Python dependencies
│   └── app/
│       ├── models/               # Request/response models
│       │   ├── __init__.py
│       │   └── request_models.py
│       ├── routes/                # API endpoints
│       │   ├── chat_routes.py     # Main chat endpoint
│       │   └── health_routes.py   # Health checks
│       ├── rag/                  # RAG Pipeline
│       │   ├── __init__.py       # RAGPipeline orchestration
│       │   ├── chunking/         # Text chunking strategies
│       │   ├── embeddings/       # Embedding generation & caching
│       │   └── retrieval/        # Vector similarity search
│       ├── utils/                # Utility modules
│       │   ├── llm_client.py     # LLM providers (HuggingFace, OpenAI, Gemini, Ollama)
│       │   ├── text_correction.py # Fuzzy typo correction for retrieval
│       │   └── rate_limiter.py   # Request rate limiting
│       ├── session/              # Session management
│       │   └── session_manager.py
│       ├── security/             # Security & validation
│       │   ├── auth.py           # API key validation
│       │   └── input_validation.py # Input sanitization
│       ├── database/             # DB layer (extensible)
│       ├── logging_config/       # Structured logging
│       └── __init__.py
│
├── config/                        # Configuration
│   ├── .env.example
│   └── .env.development
│
└── docs/                         # Documentation
    └── ARCHITECTURE.md
```

## 🚀 Quick Start

### Prerequisites
- Chrome 90+
- Python 3.9+
- Node.js 14+ (if using bundler)
- pip package manager

### Step 1: Clone and Navigate
```bash
cd Web-chat-extension
```

### Step 2: Install Backend Dependencies
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Configure Environment
```bash
cd ../config
cp .env.example .env
# Edit .env with your settings (defaults work for local dev)
```

### Step 4: Start Backend Server
```bash
cd ../backend
python main.py
# Server runs on http://localhost:8000
# Check health: curl http://localhost:8000/health
```

### Step 5: Load Extension in Chrome
1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. The extension appears in your toolbar

### Step 6: Test the Extension
1. Navigate to any website (e.g., Wikipedia, news site)
2. Click the **Lumina** icon in the toolbar
3. Ask a question about the page
4. Get answers grounded in page content!

## 🏗️ Architecture Overview

### Extension Layer (Manifest V3)
- **Popup**: Chat interface with settings
- **Content Script**: DOM extraction with security filters
- **Background Service Worker**: Message routing and session management
- **Message Passing**: Secure communication between scripts

### Backend - FastAPI Server
- RESTful API for chat queries and session management
- Rate limiting and request validation
- API authentication (optional)
- CORS and security headers

### RAG Pipeline (3 Stages)

#### Stage 1: Text Processing & Chunking
```
Raw Page Content
    ↓
Clean & Extract Relevant Text (remove noise)
    ↓
Semantic Chunking (512 tokens with 128 overlap)
    ↓
Chunks with Metadata
```

#### Stage 2: Embedding & Storage
```
Chunks
    ↓
HuggingFace MiniLM-L6-v2 (384-dim vectors)
    ↓
Caching Layer (avoid recomputation)
    ↓
In-Memory Vector Store
```

#### Stage 3: Retrieval & Generation
```
User Query
    ↓
Embed Query
    ↓
Cosine Similarity Search (top-5)
    ↓
De-duplication & Ranking
    ↓
Build Context Prompt
    ↓
LLM Generation
    ↓
Answer with Confidence Score
```

### Data Flow Diagram
```
Chrome Extension                Backend
┌─────────────────┐          ┌──────────────────┐
│  Chat Popup     │          │  FastAPI Server  │
└────────┬────────┘          └────────┬─────────┘
         │                            │
         ├─ Extract Page Content      │
         ├─ Get User Query            │
         └─────────────────────────→  POST /api/chat
                                      │
                    ┌─────────────────┴────────────────┐
                    │    RAG Pipeline Processing       │
                    └────────────────────────────────┐
                                      │              │
                         ┌────────────┴──────┐       │
                         │ TextChunking      │       │
                         │ Embeddings        │       │
                         │ VectorRetrieval   │       │
                         │ LLMGeneration    │       │
                         └────────────────┬──┘       │
                                          │         │
         ┌─────────────────────────────────────────┘
         │
         └─ ← Response: Answer + Sources + Confidence
```

  ## 🔎 End-to-End Process (What We Built)

  ### 1) Browser Side (Extension)
  - `extension/src/popup/popup.js` handles UI, settings, session id creation, and sends requests to backend.
  - `extension/src/content/content.js` extracts page text from DOM with:
    - Sensitive URL checks (`login`, `payment`, `checkout`, etc.)
    - Element filtering (`script`, `style`, nav/footer/ads, hidden nodes)
    - Readability-style main-content scoring
    - Structured sections: `HEADINGS`, `PRICING & COSTS`, `READABLE CONTENT`, `LISTS`, `TABLES`
    - Source highlighting from backend snippets (`text_snippet`) using fuzzy overlap matching.

  ### 2) Backend Entry (FastAPI)
  `backend/app/routes/chat_routes.py` imports and orchestrates:
  - `ChatRequest` (request schema)
  - `validate_api_key`, `validate_input`, `check_sensitive_content` (security/validation)
  - `RAGPipeline` (chunking + embeddings + retrieval)
  - `SessionManager` (session memory in RAM)
  - `LLMClient` (provider abstraction)
  - `correct_query` (typo correction for retrieval)

  ### 3) Processing Pipeline (RAG)
  1. `process_page(page_content, page_url)`
    - Chunk text (`TextChunker`)
    - Generate chunk embeddings (`EmbeddingPipeline`)
    - Store vectors (`VectorRetriever` in-memory index)
  2. `retrieve_context(query, page_url, top_k=5)`
    - Embed query
    - Cosine similarity retrieval
    - Deduplicate and rank
  3. `build_context_prompt(retrieved_chunks)`
    - Builds `[Source i - Confidence x.xx]` blocks passed to LLM.

  ### 4) How Context Is Found
  - Query is embedded into the same vector space as chunks.
  - Retriever compares query embedding vs each chunk embedding via cosine similarity.
  - Top relevant chunks become context.
  - Returned sources include `id`, `score`, `page_url`, and `text_snippet` for explainability and highlighting.

  ### 5) How Memory Works
  - Session id is created in extension (`chrome.storage.session`) and sent with each request.
  - Backend stores session in `SessionManager.sessions` (Python dict, in RAM).
  - Each turn saves `query`, `answer`, timestamp, and tokens.
  - Recent turns are appended to LLM context as `RECENT CONVERSATION HISTORY` for follow-up questions.

  ### 6) How Spelling Mistakes Are Handled
  - `backend/app/utils/text_correction.py` does fuzzy correction.
  - Important behavior:
    - Correction is used for **retrieval query matching**.
    - Original user wording is preserved for final answer generation.
    - UI no longer displays the corrected-word notice.

  ### 7) Where Data Is Stored Right Now
  - Session memory: backend RAM (`SessionManager.sessions`)
  - Vector store: backend RAM (`VectorRetriever.documents`)
  - Embedding cache: local files in `.embedding_cache/*.npy`
  - Extension settings: `chrome.storage.sync`
  - Extension session id: `chrome.storage.session`

  Note: backend RAM data resets when server restarts; DB persistence is planned (placeholder exists in `save_session()`).

## 🔐 Security & Privacy

### Content Extraction Safety
- Filters out sensitive domains (banking, payment, auth pages)
- Removes password fields, form inputs, sensitive patterns
- Cleans navigation, ads, trackers from extraction

### API Security
- Optional API key validation with Bearer tokens
- Input validation and sanitization
- Rate limiting per session (60 req/min, 1000 req/hour)
- CORS configuration
- Error messages don't leak internal details

### Data Privacy
- Private mode option (no data persistence)
- Session-based memory (not user-based)
- No user identification or tracking
- Configurable data retention

### Frontend Security
- No credentials stored in extension storage
- HTTPS-only communication (in production)
- Content Security Policy compatible

##  Key ML/Engineering Concepts Demonstrated

### 1. **Semantic Chunking**
- Respects document structure (headers, paragraphs)
- Maintains context with overlap
- Handles variable-length content

### 2. **Embeddings & Similarity Search**
- Uses MiniLM for efficiency (384-dim vectors)
- Cosine similarity for retrieval
- Caching to avoid recomputation
- Easy swap to OpenAI embeddings

### 3. **Prompt Engineering**
- Context-aware LLM prompts
- Source citation in responses
- Temperature tuning for consistency

### 4. **Session Management**
- Multi-page context tracking
- Conversation memory within session
- Token usage monitoring

### 5. **Production Patterns**
- Structured logging with rotation
- Error handling and recovery
- Rate limiting and backpressure
- Health checks and monitoring
- Modular, testable architecture

##  Extensibility & Scaling

### Swappable Components

#### LLM Providers
```python
# Currently: Mock provider
llm_client = LLMClient(provider_type="mock")

# Switch to OpenAI:
llm_client = LLMClient(provider_type="openai", model="gpt-3.5-turbo")

# or Ollama (local):
llm_client = LLMClient(provider_type="ollama", model="mistral")
```

#### Embedding Models
```python
# Currently: HuggingFace MiniLM
rag = RAGPipeline(embedding_model_type="huggingface")

# Switch to OpenAI embeddings:
rag = RAGPipeline(embedding_model_type="openai")
```

#### Vector Databases
Currently uses in-memory storage. For production:

```python
# Replace VectorRetriever with one of:
# - Pinecone Cloud Vector DB
# - Supabase pgvector
# - Weaviate
# - FAISS (local)
```

### Scalability Path

**Phase 1: Current (Development)**
- In-memory vector storage
- Mock LLM or local Ollama
- File-based logging

**Phase 2: Production (Single Instance)**
- PostgreSQL + pgvector for vector DB
- OpenAI/Claude for LLM
- Redis for session caching
- Structured JSON logging

**Phase 3: Multi-Instance (Horizontal Scaling)**
- Distributed vector DB (Pinecone)
- Load balancer + multiple backend instances
- Celery/RabbitMQ for async tasks
- Kubernetes deployment

**Phase 4: Enterprise (High-Scale)**
- Multi-region deployment
- Fine-tuned domain-specific models
- Advanced caching strategies
- Analytics and monitoring

##  Configuration & Customization

### Environment Variables
All options in `config/.env.example`:

```bash
# LLM Provider (backend default — overridable per-request from extension settings)
LLM_PROVIDER=huggingface           # huggingface | openai | gemini | ollama | mock
LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct

# Provider API Keys (backend defaults; users can supply their own via extension)
HUGGINGFACE_API_KEY=hf_...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...

# Embedding Model
EMBEDDING_MODEL_TYPE=huggingface
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2

# RAG Pipeline
CHUNK_SIZE=512
CHUNK_OVERLAP=128
RETRIEVAL_TOP_K=5

# Rate Limiting
RATE_LIMIT_RPM=60
RATE_LIMIT_RPH=1000

# Security
REQUIRE_API_KEY=false      # Set true to enforce Backend API Key on all requests
VALID_API_KEYS=key1,key2   # Comma-separated valid bearer tokens
```

### Two API Keys Explained

| Key | Field | Purpose | Where Sent |
|-----|-------|---------|------------|
| **Backend API Key** | `Authorization: Bearer <key>` header | Guards access to *your* backend server | HTTP header on every request |
| **LLM API Key** | `llm_api_key` in request body | Authenticates to LLM provider (HF/OpenAI/Gemini) | Forwarded to provider API |

Both are optional: Backend API Key enforcement requires `REQUIRE_API_KEY=true`; LLM API Key falls back to `.env` when not supplied.

## 🧪 Testing & Monitoring

### Health Checks
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/ready
```

### View Statistics
```bash
curl http://localhost:8000/api/stats
```

### Logs
```bash
tail -f app.log
```

### Extension Debugging
1. Right-click extension icon → **Manage extension**
2. Click **Errors** to view console errors
3. Check Chrome DevTools: F12 → **Service Workers** tab

##  API Reference

### POST `/api/chat`
Main endpoint for chat queries.

**Request:**
```json
{
  "query": "What is the main topic of this article?",
  "page_content": "Full page text extracted...",
  "page_url": "https://example.com/article",
  "session_id": "session_123456",
  "max_tokens": 500,
  "private_mode": false,
  "llm_provider": "huggingface",
  "llm_model": "meta-llama/Llama-3.1-8B-Instruct",
  "llm_api_key": "hf_your_key_here"
}
```

> `llm_provider`, `llm_model`, and `llm_api_key` are all **optional**. When omitted, the backend falls back to environment variable defaults (`LLM_PROVIDER`, `LLM_MODEL`, provider API keys in `.env`).

**Response:**
```json
{
  "success": true,
  "answer": "The main topic is...",
  "confidence": 0.87,
  "tokens_used": 124,
  "sources": [
    {
      "id": "chunk_1",
      "score": 0.92,
      "page_url": "https://example.com/article",
      "text_snippet": "...relevant excerpt..."
    }
  ],
  "session_id": "session_123456"
}
```

### GET `/api/session/{session_id}`
Retrieve session history and metadata.

### DELETE `/api/session/{session_id}`
Clear session data.

### GET `/api/stats`
Get system statistics (active sessions, queries, RAG stats).

##  Production Deployment Guide

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-copilot-backend
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
        image: ai-copilot:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: production
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

##  Production Enhancements

### Implemented
- [x] User-supplied LLM provider / model / API key per request
- [x] True private mode (no backend or extension storage)
- [x] HuggingFace, OpenAI, Gemini, Ollama provider support
- [x] Deterministic YouTube shortcuts (notifications, subscriptions, channels, lessons)
- [x] Fuzzy typo correction for retrieval
- [x] Session-based conversation follow-up memory
- [x] Source highlighting in-page from returned `text_snippet`

### Not Yet Implemented
- [ ] Database persistence (PostgreSQL + SQLAlchemy)
- [ ] Redis caching layer
- [ ] Vector database integration (Pinecone/Weaviate)
- [ ] User authentication and accounts
- [ ] Fine-grained access control
- [ ] Comprehensive unit and integration tests
- [ ] Performance benchmarking
- [ ] Frontend analytics and monitoring
- [ ] Multi-language support

### Quick Wins to Production
1. **Add Tests**: Unit tests for RAG pipeline, API endpoints
2. **Database**: Add PostgreSQL for session persistence
3. **Vector DB**: Integrate Pinecone or Supabase pgvector
4. **Monitoring**: Add Prometheus metrics and Grafana
5. **CI/CD**: GitHub Actions for testing and deployment
6. **Documentation**: API docs (auto-generated via FastAPI)

## 📈 Performance Metrics to Track

- **Latency**: Query → Response time (target: <2s)
- **Retrieval Quality**: Relevance of retrieved chunks (NDCG@5)
- **Answer Quality**: Human evaluation of answer relevance
- **Cache Hit Rate**: Embedding cache effectiveness
- **Token Usage**: Average tokens per request
- **Error Rate**: Failed requests / total requests
- **Concurrent Users**: Max simultaneous sessions

## 🤝 Contributing & Customization

### Adding a New LLM Provider
1. Create class inheriting from `LLMProvider` in `app/utils/llm_client.py`
2. Implement `generate()` method
3. Add to `LLMClient.__init__()`:
   ```python
   elif provider_type == "my_provider":
       self.provider = MyProvider(model)
   ```
4. Test and deploy

### Custom Chunking Strategy
Extend `TextChunker` in `app/rag/chunking/text_chunker.py`:
```python
def _my_chunking_strategy(self, text, page_url):
    # Your logic here
    pass
```

## 📝 License

MIT License - Free for personal and commercial use.

## 🙏 Acknowledgments

- Inspired by real-world RAG systems (LangChain, LlamaIndex)
- Chrome Extension best practices from Google
- FastAPI for excellent async framework
- Sentence-Transformers for efficient embeddings

## 📞 Support

For issues, improvements, or questions:
1. Check documentation in `docs/`
2. Review inline code comments
3. Check backend logs: `tail -f app.log`
4. Debug extension: See "Testing & Monitoring" section

---

**Build with ❤️ to showcase ML engineering excellence**
