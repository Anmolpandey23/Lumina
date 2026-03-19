/**
 * Popup Script for AI Browsing Copilot
 * Handles UI interactions, message display, and API communication
 */

class ChatInterface {
  constructor() {
    this.apiUrl = 'http://localhost:8000';
    this.apiKey = null;
    this.currentSessionId = null;
    this.isWaitingForResponse = false;
    this.maxTokens = 500;
    this.privateMode = false;
    
    this.initializeDOM();
    this.attachEventListeners();
    this.loadSettings();
    this.initializeSession();
    this.displayWelcomeMessage();
  }

  initializeDOM() {
    this.chatMessages = document.getElementById('chatMessages');
    this.queryInput = document.getElementById('queryInput');
    this.sendBtn = document.getElementById('sendBtn');
    this.loading = document.getElementById('loading');
    this.errorMessage = document.getElementById('errorMessage');
    this.pageTitle = document.getElementById('pageTitle');
    this.tokenCount = document.getElementById('tokenCount');
    this.clearBtn = document.getElementById('clearBtn');
    this.settingsBtn = document.getElementById('settingsBtn');
    this.settingsModal = document.getElementById('settingsModal');
  }

  attachEventListeners() {
    this.sendBtn.addEventListener('click', () => this.handleSendMessage());
    this.queryInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleSendMessage();
      }
    });
    this.clearBtn.addEventListener('click', () => this.clearChat());
    this.settingsBtn.addEventListener('click', () => this.openSettings());

    // Settings modal events
    const closeBtn = this.settingsModal.querySelector('.close-btn');
    const saveBtn = document.getElementById('saveSettings');
    const cancelBtn = document.getElementById('cancelSettings');

    closeBtn.addEventListener('click', () => this.closeSettings());
    saveBtn.addEventListener('click', () => this.saveSettings());
    cancelBtn.addEventListener('click', () => this.closeSettings());
  }

  async loadSettings() {
    const settings = await chrome.storage.sync.get({
      apiUrl: 'http://localhost:8000',
      apiKey: null,
      maxTokens: 500,
      privateMode: false
    });

    this.apiUrl = settings.apiUrl;
    this.apiKey = settings.apiKey;
    this.maxTokens = settings.maxTokens;
    this.privateMode = settings.privateMode;
  }

  async initializeSession() {
    const sessionData = await chrome.storage.session.get('sessionId');
    
    if (!sessionData.sessionId) {
      this.currentSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      await chrome.storage.session.set({ sessionId: this.currentSessionId });
    } else {
      this.currentSessionId = sessionData.sessionId;
    }

    // Get current page info
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    this.currentPageUrl = tab.url;
    this.currentPageTitle = tab.title;
    
    this.pageTitle.textContent = this.currentPageTitle || 'Current Page';
    this.updateTokenCount(0);
  }

  displayWelcomeMessage() {
    const welcomeMsg = document.createElement('div');
    welcomeMsg.className = 'message system';
    welcomeMsg.innerHTML = `
      <div class="message-content">
        <strong>Welcome to AI Browsing Copilot!</strong>
        <br>
        I can answer questions about the current page using Retrieval-Augmented Generation (RAG).
        <br>
        Ask me anything about: "${this.currentPageTitle || 'this page'}"
      </div>
    `;
    this.chatMessages.appendChild(welcomeMsg);
    this.scrollToBottom();
  }

  async handleSendMessage() {
    const query = this.queryInput.value.trim();
    
    if (!query || this.isWaitingForResponse) return;

    // Display user message
    this.addMessage(query, 'user');
    this.queryInput.value = '';
    this.queryInput.disabled = true;
    this.sendBtn.disabled = true;
    this.isWaitingForResponse = true;
    this.showLoading(true);
    this.hideError();

    try {
      // Get page content from content script
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const pageContent = await this.getPageContent(tab.id);

      // Send query to backend
      const response = await this.sendQueryToBackend(query, pageContent);
      
      if (response.success) {
        this.addMessage(response.answer, 'assistant');
        this.updateTokenCount(response.tokens_used || 0);
      } else {
        this.showError(response.error || 'Failed to get response');
        this.addMessage('Sorry, I encountered an error. Please try again.', 'error');
      }
    } catch (error) {
      console.error('Error:', error);
      this.showError(error.message);
      this.addMessage(`Error: ${error.message}`, 'error');
    } finally {
      this.isWaitingForResponse = false;
      this.showLoading(false);
      this.queryInput.disabled = false;
      this.sendBtn.disabled = false;
      this.queryInput.focus();
    }
  }

  async getPageContent(tabId) {
    return new Promise((resolve, reject) => {
      chrome.tabs.sendMessage(
        tabId,
        { action: 'extractPageContent' },
        (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error('Could not extract page content'));
          } else if (response && response.success) {
            resolve(response.content);
          } else {
            reject(new Error(response?.error || 'Unknown error'));
          }
        }
      );
    });
  }

  async sendQueryToBackend(query, pageContent) {
    const payload = {
      query,
      page_content: pageContent,
      page_url: this.currentPageUrl,
      session_id: this.currentSessionId,
      max_tokens: this.maxTokens,
      private_mode: this.privateMode
    };

    const response = await fetch(`${this.apiUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(this.apiKey && { 'Authorization': `Bearer ${this.apiKey}` })
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  }

  addMessage(text, type = 'assistant') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;
    
    messageDiv.appendChild(contentDiv);
    this.chatMessages.appendChild(messageDiv);
    this.scrollToBottom();
  }

  scrollToBottom() {
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  showLoading(show) {
    if (show) {
      this.loading.classList.remove('hidden');
    } else {
      this.loading.classList.add('hidden');
    }
  }

  showError(message) {
    this.errorMessage.textContent = message;
    this.errorMessage.classList.remove('hidden');
  }

  hideError() {
    this.errorMessage.classList.add('hidden');
  }

  updateTokenCount(tokens) {
    this.tokenCount.textContent = `Tokens: ${tokens}`;
  }

  clearChat() {
    if (confirm('Are you sure you want to clear this chat?')) {
      this.chatMessages.innerHTML = '';
      this.displayWelcomeMessage();
    }
  }

  openSettings() {
    document.getElementById('apiUrl').value = this.apiUrl;
    document.getElementById('apiKey').value = this.apiKey || '';
    document.getElementById('maxTokens').value = this.maxTokens;
    document.getElementById('enablePrivateMode').checked = this.privateMode;
    this.settingsModal.classList.remove('hidden');
  }

  closeSettings() {
    this.settingsModal.classList.add('hidden');
  }

  async saveSettings() {
    this.apiUrl = document.getElementById('apiUrl').value || 'http://localhost:8000';
    this.apiKey = document.getElementById('apiKey').value || null;
    this.maxTokens = parseInt(document.getElementById('maxTokens').value) || 500;
    this.privateMode = document.getElementById('enablePrivateMode').checked;

    await chrome.storage.sync.set({
      apiUrl: this.apiUrl,
      apiKey: this.apiKey,
      maxTokens: this.maxTokens,
      privateMode: this.privateMode
    });

    this.closeSettings();
    this.addMessage('Settings saved successfully!', 'system');
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new ChatInterface();
});
