# Setup & Installation Guide

Complete step-by-step guide to get Lumina running locally for development and testing.

## System Requirements

- **OS**: macOS, Linux, or Windows (with WSL2)
- **Python**: 3.9 or higher
- **Node.js**: 14+ (optional, if using frontend build tools)
- **Chrome**: Version 90 or later
- **RAM**: 4GB minimum (8GB+ recommended)
- **Disk**: 1GB for dependencies

## Installation Steps

### Step 1: Clone the Repository

```bash
# Navigate to where you want the project
cd ~/Projects

# Clone (replace with your repo URL)
git clone https://github.com/yourusername/ai-browsing-copilot.git
cd ai-browsing-copilot

# Verify structure
ls -la
# You should see: backend/, extension/, config/, docs/, README.md
```

### Step 2: Set Up Python Environment

```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows (PowerShell):
# venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
# venv\Scripts\activate.bat

# Verify activation (should see (venv) in prompt)
which python  # Should show path inside venv
```

### Step 3: Install Python Dependencies

```bash
# Make sure you're in backend/ with venv activated
pip install --upgrade pip setuptools wheel

# Install required packages
pip install -r requirements.txt

# Verify installation
pip list | grep -E "fastapi|sentence-transformers|scikit-learn"
```

**Expected packages:**
- fastapi==0.104.1
- uvicorn==0.24.0
- pydantic==2.5.0
- sentence-transformers==2.2.2
- scikit-learn==1.3.2
- numpy==1.24.3

### Step 4: Configure Environment

```bash
# Go to config directory
cd ../config

# Copy example env file
cp .env.example .env

# Edit .env with your settings (defaults work for local dev)
# nano .env  # or use your editor
```

**Recommended development settings:**
```bash
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
LOG_LEVEL=DEBUG
LLM_PROVIDER_TYPE=mock  # Use mock for testing without API key
REQUIRE_API_KEY=false
```

### Step 5: Start Backend Server

```bash
# Go back to backend directory
cd ../backend

# Make sure venv is activated
source venv/bin/activate  # if not already

# Start the server
python main.py

# Expected output:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete

# Test in another terminal:
curl http://localhost:8000/health
# Should return: {"status":"healthy","service":"ai-browsing-copilot","version":"1.0.0"}
```

**Keep this terminal running** for the rest of setup.

### Step 6: Load Extension in Chrome

Open a new terminal/window (keep backend running in first terminal):

```bash
# Navigate to extension folder
cd ../extension

# Note: You should see manifest.json here
ls -la
# Should show: manifest.json, src/, assets/
```

**Load in Chrome:**

1. Open Chrome browser
2. Navigate to `chrome://extensions/`
3. **Enable Developer mode** (toggle in top-right corner)
4. Click **Load unpacked**
5. Select the `extension` folder you just navigated to
6. ✅ Extension should appear with icon in toolbar

**Verify Extension Loaded:**
- Look for "Lumina" icon in toolbar
- Right-click → "Manage extension" to view details
- Should show "Lumina v1.0.0"

### Step 7: Verify Setup is Working

1. **Test Backend API:**
   ```bash
   # In a new terminal
   curl http://localhost:8000/api/health
   curl http://localhost:8000/api/stats
   ```

2. **Test Extension Content Script:**
   - Navigate to any website (e.g., https://www.wikipedia.org)
   - Open DevTools (F12)
   - Go to **Console** tab
   - Should see: "Lumina content script loaded"

3. **Test Chat Interface:**
   - Click extension icon in toolbar
   - Chat popup should open
   - You should see:
     - "Welcome to Lumina!"
     - Current page title
     - Input field to "Ask something about this page..."

4. **Send a Test Query:**
   - Type: "What is this page about?"
   - Click send button (📤)
   - Wait for response...
   - Should see mock response appear

## Troubleshooting

### Backend Won't Start

**Error: `Address already in use`**
```bash
# Port 8000 is occupied
# Solution 1: Kill existing process
lsof -ti:8000 | xargs kill -9

# Solution 2: Use different port
PORT=8001 python main.py
# Then update extension settings to http://localhost:8001
```

**Error: `ModuleNotFoundError: No module named 'sentence_transformers'`**
```bash
# Dependencies not installed
# Solution: Make sure venv is active and reinstall
source venv/bin/activate
pip install -r requirements.txt
```

**Error: `OSError: Cannot find model`**
```bash
# HuggingFace model not downloaded
# Solution: Let it download automatically (first run takes 2-3 min)
# Or pre-download:
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Extension Won't Load

**Error: `Extension ID not found`**
- Make sure you're selecting the `extension/` folder (with manifest.json inside)
- Not the parent folder

**Error: `Parse error in manifest`**
- Check `extension/manifest.json` for syntax errors
- Make sure it's valid JSON (no trailing commas)

**Content script not running**
1. Close the extension
2. Reload the webpage
3. Open DevTools (F12)
4. Check Console for errors

### Chat Doesn't Work

**Error: `Could not extract page content`**
```bash
# Backend and extension not communicating
# Solutions:
# 1. Verify backend is running: curl http://localhost:8000/health
# 2. Check extension settings: Click ⚙️ in popup
# 3. Verify API URL is correct (default: http://localhost:8000)
# 4. Check browser console (F12) for errors
```

**Error: `Failed to get response`**
```bash
# Backend error, check logs:
# Look at backend terminal for error messages
# Common issues:
# - Backend crashed (restart it)
# - Rate limit exceeded (wait 1 minute)
# - Input too large (query or page content overflow)
```

**No response after clicking send**
```bash
# Check if backend is still running
# If not, restart:
cd backend
source venv/bin/activate
python main.py
```

## Development Workflow

### Making Changes to Backend

```bash
# Edit any Python file
nano backend/app/utils/llm_client.py

# Backend automatically reloads (uvicorn reload mode)
# See: "Application startup complete" in terminal

# Test with curl:
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is AI?",
    "page_content": "Artificial intelligence is...",
    "page_url": "http://example.com",
    "session_id": "test_session"
  }'
```

### Making Changes to Extension

```bash
# Edit any extension file
nano extension/src/popup/popup-interface.js

# Reload extension:
# 1. Go to chrome://extensions/
# 2. Find "Lumina"
# 3. Click refresh icon ↻

# Or keyboard shortcut: Cmd+R (Mac) / Ctrl+R (Windows/Linux)

# Test in popup again
```

### Making Changes to RAG Pipeline

```bash
# Edit RAG logic
nano backend/app/rag/__init__.py

# Server reloads automatically
# Test with new queries
```

## Upgrading & Maintenance

### Update Dependencies

```bash
cd backend

# Check for updates
pip list --outdated

# Update specific package
pip install --upgrade sentence-transformers

# Or update all (be careful!)
pip install --upgrade -r requirements.txt
```

### Clear Cache

```bash
# Extension cache
# In Chrome DevTools (Extension tab), or:
# chrome://extensions/ → Clear data for extension

# Backend embedding cache
cd backend
rm -rf .embedding_cache/

# Session data
# In-memory, automatically cleared on restart
```

## Performance Tips

### Speed Up First Run

First run downloads embedding model (2-3 min). To skip wait:

```bash
# Pre-download model
cd backend
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Then start server
python main.py
```

### Reduce CPU Usage

Edit `config/.env`:
```bash
# Use smaller embedding model (faster, less accurate)
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2  # Current (fast)
# or
EMBEDDING_MODEL_NAME=all-mpnet-base-v2  # More accurate, slower

# Reduce chunk size (fewer chunks = faster)
CHUNK_SIZE=256  # Was 512
```

### Monitor Resource Usage

```bash
# Watch Python process resources
top -p $(pgrep -f "python main.py")

# macOS:
ps aux | grep python
```

## Testing

### Manual Testing Checklist

- [ ] Start backend server
- [ ] Load extension in Chrome
- [ ] Navigate to https://en.wikipedia.org/wiki/Machine_learning
- [ ] Ask: "What is machine learning?"
- [ ] Should get relevant answer
- [ ] Try on different websites (news, blogs, docs)
- [ ] Check error handling (very long text, special websites)
- [ ] Test settings dialog (change API URL, max tokens)
- [ ] Test clear chat button
- [ ] Test multiple queries in same session

### Example Websites to Test

1. **Wikipedia Articles**
   - Long-form, well-structured
   - Good for testing chunking

2. **News Articles**
   - Headline + body structure
   - Different DOM layout

3. **Technical Documentation**
   - Code examples, lists
   - Dense information

4. **Blog Posts**
   - Natural paragraph breaks
   - Images and media

## Next Steps

Once everything is working:

1. **Read Documentation**
   - Check `docs/ARCHITECTURE.md` for detailed design
   - Review inline code comments

2. **Explore the Code**
   - Start with `backend/main.py`
   - Follow RAG pipeline: `backend/app/rag/__init__.py`
   - Check extension logic: `extension/src/popup/popup-interface.js`

3. **Customize & Extend**
   - Change embedding model
   - Add your own LLM provider
   - Modify chunking strategy
   - Add database persistence

4. **Deploy**
   - See "Production Deployment" in main README
   - Set up Docker container
   - Deploy to cloud (Heroku, AWS, GCP)

## Getting Help

### Check Logs

**Backend logs:**
```bash
# In running terminal, or
tail -f backend/app.log

# Look for ERROR or WARNING messages
```

**Extension logs:**
```bash
# Chrome DevTools
F12 → Console tab
# Look for red errors or yellow warnings
```

### Debug Extension

```bash
# In DevTools Console, try:
chrome.runtime.sendMessage(
  {action: 'extractPageContent'},
  response => console.log(response)
)
```

### Test Backend API Directly

```bash
# Use curl to test endpoints
curl http://localhost:8000/health

curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "page_content": "test content here",
    "page_url": "http://test.com",
    "session_id": "test123"
  }'
```

---

**Congratulations! Your Lumina extension is ready to use! 🚀**

For questions or issues, refer to:
- README.md - Overview and features
- docs/ARCHITECTURE.md - Technical deep dive
- Code comments - Implementation details
