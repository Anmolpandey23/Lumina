# Architecture & Design Decisions

## System Design Philosophy

Lumina is built following these principles:

1. **Modular Architecture**: Each component (extraction, chunking, embedding, retrieval, generation) is independent and testable
2. **Security-First**: Content extraction filters sensitive data by default
3. **Extensible Design**: Easy substitution of embedding models, LLMs, and databases
4. **Production-Ready Patterns**: Logging, error handling, rate limiting, caching
5. **Simplicity First**: Uses in-memory storage for MVP, upgradeable to distributed systems

## Component Deep-Dives

### 1. Chrome Extension (Frontend)

**Manifest V3 Benefits:**
- Service Workers instead of persistent background pages
- Better security model with restricted APIs
- Improved performance and memory footprint
- Future-proof (MV2 deprecated)

**Architecture:**
```
Popup UI ←→ Content Script ←→ Background Worker
   │              │                 │
   └──────────────┴─────────────────┘
        Message Passing (postMessage)
```

**Key Components:**

#### Content Script (`content.js`)
- Runs in page context with direct DOM access
- `DOMExtractor` class handles content extraction
- Security filters remove sensitive elements
- Sends structured data via `chrome.runtime.sendMessage`

**Extraction Pipeline:**
```
Raw DOM
  ↓
Clone & Remove Script/Style
  ↓
Filter Sensitive Selectors (nav, ads, footer)
  ↓
Remove Hidden Elements
  ↓
Extract Content (h1-h6, p, li, tables)
  ↓
Return Structured Text
```

**Sensitive Domain Detection:**
```javascript
const sensitiveUrls = [
  'login', 'signin', 'password', 
  'banking', 'payment', 'checkout'
];
// Skip extraction if URL contains these keywords
```

#### Popup UI (`popup.html` + `popup-interface.js`)
- Lightweight framework - no dependencies
- Vanilla JavaScript for minimal impact
- Message passing to content script
- Settings modal for configuration

**Key Classes:**
- `ChatInterface`: Main UI orchestration
- Event listeners for send, settings, clear
- Local storage for user preferences
- Error handling with user-friendly messages

#### Background Service Worker (`background.js`)
- Lightweight event handler
- Session ID management
- Request forwarding
- Logs setup and lifecycle events

### 2. Backend API (FastAPI)

**Why FastAPI?**
- Fast async framework (ASGI)
- Automatic OpenAPI documentation
- Built-in data validation (Pydantic)
- Easy to extend with middleware
- Perfect for ML pipelines

**Middleware Stack:**
```
Request
  ↓
CORS Middleware (allow cross-origin)
  ↓
GZIP Compression Middleware
  ↓
API Route Handler
  ↓
RAG Pipeline
  ↓
LLM Generation
  ↓
Response
  ↓
CORS Headers
  ↓
Client
```

**API Request Flow:**
```python
POST /api/chat
  ↓
validate_api_key()           # Optional auth
  ↓
validate_input()             # Pydantic + custom validation
  ↓
check_sensitive_content()    # Security check
  ↓
RAGPipeline.process_page()   # Chunk, embed, store
  ↓
RAGPipeline.retrieve_context() # Find relevant chunks
  ↓
LLMClient.generate_answer()  # LLM inference
  ↓
Build Response with Sources
  ↓
Return JSON
```

## Runtime Walkthrough (Current Implementation)

This section explains exactly how one user question is processed now.

### A) Extension Request Lifecycle
1. User asks question in popup (`popup.js`).
2. Popup asks content script for extracted page content (`extractPageContent`).
3. Content script (`content.js`) returns cleaned, structured text.
4. Popup posts to backend `/api/chat` with:
   - `query`
   - `page_content`
   - `page_url`
   - `session_id`
   - `max_tokens`
   - `private_mode`

### B) Backend Request Lifecycle
In `chat_routes.py`, request flow is:
1. Validate auth and sanitize input.
2. Block sensitive content if required.
3. Get/create session (`SessionManager`).
4. Save page metadata into session.
5. Apply typo correction for retrieval query matching.
6. Run `rag_pipeline.process_page()`:
   - chunk
   - embed
   - store vectors
7. Retrieve relevant chunks with `rag_pipeline.retrieve_context()`.
8. Build context prompt from retrieved chunks.
9. Append recent in-session chat turns as `RECENT CONVERSATION HISTORY`.
10. Generate answer via `LLMClient.generate_answer()`.
11. Return answer + sources + confidence + session id.

### C) Import Map (What Is Imported and Why)

`chat_routes.py` imports:
- `ChatRequest`: typed request schema.
- `validate_api_key`, `validate_input`, `check_sensitive_content`: security gates.
- `LLMClient`: provider abstraction for generation.
- `correct_query`: typo-tolerant retrieval.
- `RAGPipeline`: chunk/embed/retrieve orchestration.
- `SessionManager`: stores pages + prior turns for memory.

`app/rag/__init__.py` imports:
- `TextChunker`: converts page into semantically useful chunks.
- `EmbeddingPipeline`: converts text to vectors with optional cache.
- `VectorRetriever`, `RankedRetriever`: cosine search + post-processing.

### D) Retrieval, Context, and Confidence
- Query embedding is generated in same embedding space as page chunks.
- Retriever computes cosine similarity against stored chunk vectors.
- Top relevant chunks are deduplicated and ranked.
- Context is formatted like:
  - `[Source 1 - Confidence: 0.72] ...`
  - `[Source 2 - Confidence: 0.61] ...`
- Confidence in response is mean similarity score of retrieved chunks.

### E) Memory Model
- Session memory lives in `SessionManager.sessions` (Python dict in RAM).
- Stored per turn: `query`, `answer`, timestamp, `tokens_used`.
- Recent history is injected into context so follow-ups can reference earlier asks.
- Persistence hook exists (`save_session`) but database persistence is not yet implemented.

### F) Storage Model
- In-memory:
  - session objects
  - vector documents
- File-based local cache:
  - `.embedding_cache/*.npy` for embeddings
- Browser storage:
  - `chrome.storage.sync` for settings
  - `chrome.storage.session` for session id

### G) Typo Handling Behavior
- Fuzzy typo correction is used to improve retrieval hit-rate.
- Original user phrasing is still used for final generation output behavior.
- Correction notices are not shown in popup UI.

### 3. RAG Pipeline

The heart of the system - orchestrates Retrieval-Augmented Generation.

#### Stage 1: Text Chunking (`TextChunker`)

**Chunking Strategies:**

1. **Semantic Chunking** (Default & Recommended)
   - Respects document structure (headers)
   - Keeps related content together
   - Better for FAQ, articles, documentation
   - Smaller chunk boundaries = more precise retrieval

2. **Paragraph Chunking**
   - Splits by double newlines
   - Good for blog posts with clear paragraphs
   - Maintains natural breaks

3. **Sentence Chunking**
   - Maximum granularity
   - Higher retrieval precision
   - More chunks = slower search

4. **Fixed-Size Chunking**
   - Fallback strategy
   - Simple token-based boundaries
   - Consistent chunk sizes

**Parameters:**
- `chunk_size=512`: Max tokens per chunk
- `chunk_overlap=128`: Overlap for context preservation
- `strategy="semantic"`: Default strategy

**Why Overlap?**
```
Chunk 1: [0-512]
         "The machine learning model uses..."
           ↓ overlap
Chunk 2: [384-896]
         "...uses distributed training with..."
```
Ensures queries matching chunk boundaries aren't missed.

#### Stage 2: Embeddings (`EmbeddingPipeline`)

**Supported Models:**

1. **HuggingFace MiniLM-L6-v2** (Default)
   - 384-dimensional vectors
   - Fast inference (~80ms for 512-token text)
   - Good accuracy for generic content
   - Runs locally (no API calls)

2. **OpenAI Embeddings (ada-002)**
   - 1536-dimensional vectors
   - Higher quality but slower
   - $0.10 per 1M tokens
   - Requires API key

**Caching Strategy:**
```python
query = "What is ML?"
hash = md5(query)  # "a1b2c3d4e5..."

# Check cache first
cached = load(hash)
if cached:
    return cached  # Fast!

# Generate if not cached
embedding = model.embed(query)
save(hash, embedding)  # For next time
return embedding
```

**When to Cache Busting:**
- User preference changes
- Embedding model updates
- Manual cache clearing

#### Stage 3: Retrieval (`VectorRetriever`)

**Similarity Search Algorithm:**
```
Query Embedding (384-dims)
  ↓
For each stored chunk:
  similarity = cosine(query_vec, chunk_vec)
  if similarity > threshold:
    add to results
  ↓
Sort by similarity descending
  ↓
Return top-k results
```

**Cosine Similarity:**
- Range: 0 (orthogonal) to 1 (identical)
- Default threshold: 0.3
- Threshold too low = irrelevant results
- Threshold too high = no results

**Example:**
```
Query: "How does gradient descent work?"
Results:
1. "Gradient descent is an optimization algorithm..." (0.92)
2. "The backpropagation algorithm updates weights..." (0.78)
3. "Neural networks require optimization methods..." (0.65)
```

**Ranked Retriever Options:**
- `similarity`: Default, already sorted
- `keyword_boost`: Boost if query words appear
- `diversity`: Promote different perspectives

**Deduplication:**
- Removes near-duplicate chunks (>95% similar)
- Keeps diverse perspectives
- Improves answer quality

#### Stage 4: LLM Generation

**Provider Abstraction:**
```python
class LLMProvider(ABC):
    def generate(prompt, context, max_tokens):
        pass

# Implementations:
class OpenAIProvider(LLMProvider)
class OllamaProvider(LLMProvider)
class MockProvider(LLMProvider)
```

**Prompt Template:**
```
System: "You are a helpful assistant answering based on context..."
User: "Context:\n{context}\n\nQuestion: {query}"
```

**Confidence Scoring:**
```python
confidence = mean([chunk["score"] for chunk in retrieved])
# Weighted by relevance of sources used to generate answer
```

### 4. Session Management

**Session Lifecycle:**
```
1. Extension Popup Opens
   → Request session_id from storage
     → If exists, load session
     → If not, create new one
   
2. User Navigates to New Page
   → ContentScript sends page URL
   → Session.add_page(url, content)
   
3. User Asks Question
   → Backend receives query
   → Searches page content
   → Stores in session.queries
   
4. Session Closes or Expires
   → Save to DB (if not private_mode)
   → Notify user
```

**Multi-Page Queries:**
```python
session.pages = [
  {"url": "page1.com", ...},
  {"url": "page2.com", ...},
]

# Compare pages: "Which page has more info on ML?"
# → Build context from both pages
# → LLM generates comparison
```

### 5. Security & Privacy

**Defense Layers:**

1. **Content Extraction Level**
   ```python
   sensitiveSelectors = [
     'script', 'style',
     '[role="navigation"]',
     'form input[type="password"]'
   ]
   # Remove before text extraction
   ```

2. **Domain Level**
   ```python
   sensitiveUrls = ['login', 'banking', 'payment']
   if any(keyword in url for keyword in sensitiveUrls):
       refuse_extraction()
   ```

3. **Content Scanning**
   ```python
   patterns = [
     r'password\s*:\s*',
     r'credit\s*card',
     r'api[_-]?key\s*:\s*'
   ]
   # Reject if patterns match
   ```

4. **Input Validation**
   - Max lengths (query: 5KB, content: 100KB)
   - Sanitize whitespace and null bytes
   - Validate URLs with regex
   - Check for SQL injection patterns

5. **API Security**
   ```python
   # Optional API key validation
   if REQUIRE_API_KEY:
       validate_bearer_token(request)
   ```

6. **Rate Limiting**
   ```python
   # Per session:
   60 requests/minute
   1000 requests/hour
   
   # Prevents misuse and abusive queries
   ```

**Privacy By Design:**
- Private mode: no data persistence
- Session-based (not user-based)
- No user identification
- No external tracking
- Local embeddings (no external calls by default)

## Data Models

### ChatRequest (Input)
```python
{
  "query": str,              # 1-5000 chars
  "page_content": str,       # 1-100k chars
  "page_url": str,           # URL
  "session_id": str,         # UUID
  "max_tokens": int = 500,   # 100-2000
  "private_mode": bool = False
}
```

### ChatResponse (Output)
```python
{
  "success": bool,
  "answer": str,             # Generated answer
  "confidence": float,       # 0-1 relevance score
  "tokens_used": int,        # Approx token count
  "sources": [               # Retrieved chunks used
    {"id": str, "score": float, "page_url": str}
  ],
  "session_id": str
}
```

### Chunk (Internal)
```python
{
  "chunk_id": str,           # "url#chunk_0"
  "text": str,               # Content
  "embedding": List[float],  # 384-dims
  "metadata": {
    "page_url": str,
    "created_at": datetime
  }
}
```

## Performance Considerations

### Latency Budget (2-second response target)

```
Request Received: 0ms
  ↓
Input Validation: 5-10ms
  ↓
Chunking: 50-100ms (depends on content size)
  ↓
Embedding Generation: 80-150ms (120ms for 512 tokens)
  ↓
Vector Search: 10-20ms (cosine similarity)
  ↓
LLM Generation: 1000-1200ms (network + inference)
  ↓
Response Serialization: 5-10ms
  ↓
Total: ~1200-1600ms ✓
```

### Optimization Strategies

1. **Caching**
   - Embedding cache (file-based)
   - Session cache (in-memory)
   - Query cache (Redis in production)

2. **Batching**
   - Embed multiple chunks together
   - Parallel I/O for multiple requests

3. **Indexing**
   - FAISS for fast similarity search
   - Pinecone for distributed search

4. **Circuit Breaking**
   - Fallback to summary if retrieval fails
   - Timeout handling for LLM calls

## Scalability Architecture

### Current (MVP)
```
┌────────────────┐
│  Chrome Ext    │
└────────┬───────┘
         │
         ├──────────┐
         │          │
    ┌────▼────┐  ┌──▼─────────┐
    │ In-Memory│  │  LLM Mock  │
    │ Chunks   │  │  Provider  │
    └──────────┘  └────────────┘
```

### Phase 2 (Single Instance with Persistence)
```
┌─────────────────┐
│   Chrome Ext    │
│   (Multiple)    │
└────────┬────────┘
         │
    ┌────▼──────────────┐
    │  FastAPI Backend  │
    │  (Single Instance) │
    ├──────────┬────────┤
    │ Cache    │ Logger │
    ├──────────┼────────┤
    │  Redis   │PostgreSQL
    │  (Cache) │(pgvector)
    └──────────┴────────┘
```

### Phase 3 (Distributed)
```
┌───────────────────────────────────┐
│    Load Balancer (Nginx)          │
└────────────┬────────────┬─────────┘
             │            │
    ┌────────▼───┐  ┌─────▼────────┐
    │ Backend #1 │  │  Backend #2  │ ...
    ├────────────┤  ├──────────────┤
    │ Cache      │  │ Cache        │
    └────────┬───┘  └─────┬────────┘
             │            │
     ┌───────┴────────────┴────────┐
     │  Pinecone (Vector DB)       │
     │  PostgreSQL (Persistence)   │
     │  Redis (Session Cache)      │
     └─────────────────────────────┘
```

## Failure Modes & Resilience

### Graceful Degradation

1. **Embedding Cache Miss**
   - → Generate on the fly
   - → Store for next time

2. **No Similar Chunks Retrieved
   - → Use page summary (first 1000 chars)
   - → Notify user limited context

3. **LLM Timeout
   - → Return "Please try again"
   - → Log error for debugging

4. **Sensitive Content Detected
   - → Reject extraction
   - → Return helpful error message

5. **Rate Limit Exceeded
   - → Queue request
   - → Return 429 with retry-after

## Production Checklist

### Before Deploying to Prod

- [ ] Unit tests (90%+ coverage)
- [ ] Integration tests (happy path + errors)
- [ ] Load testing (1000+ concurrent users)
- [ ] Security audit (code review)
- [ ] Secrets management (use HashiCorp Vault)
- [ ] Monitoring setup (Prometheus + Grafana)
- [ ] Logging centralization (ELK stack)
- [ ] Backup & disaster recovery
- [ ] Database migrations strategy
- [ ] Deployment automation (Terraform + GitHub Actions)

### Monitoring & Observability

**Key Metrics:**
- Response latency (P50, P95, P99)
- Error rate (5xx, 4xx)
- Cache hit rate
- Embedding quality (NDCG@5)
- Token usage per request
- Active sessions
- Queue depth (if async)

**Alerting:**
- Latency > 3s
- Error rate > 1%
- Cache miss rate > 20%
- Memory usage > 80%
- CPU usage > 90%

---

**This architecture balances simplicity for development with extensibility for production.**
