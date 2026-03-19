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
    this.llmProvider = '';
    this.llmModel = '';
    this.llmApiKey = '';
    this.sessionStorageKey = null;

    this.initializeDOM();
    this.attachEventListeners();
    this.bootstrapPromise = this.bootstrap();
  }

  async bootstrap() {
    this.queryInput.disabled = true;
    this.sendBtn.disabled = true;

    await this.loadSettings();
    await this.initializeSession();

    const restored = await this.restoreSessionHistory();
    if (!restored) {
      this.displayWelcomeMessage();
    }

    this.queryInput.disabled = false;
    this.sendBtn.disabled = false;
    this.queryInput.focus();
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
      privateMode: false,
      llmProvider: '',
      llmModel: '',
      llmApiKey: ''
    });

    this.apiUrl = settings.apiUrl;
    this.apiKey = settings.apiKey;
    this.maxTokens = settings.maxTokens;
    this.privateMode = settings.privateMode;
    this.llmProvider = settings.llmProvider;
    this.llmModel = settings.llmModel;
    this.llmApiKey = settings.llmApiKey;
  }

  async initializeSession() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    this.currentTabId = tab.id;
    this.currentPageUrl = tab.url;
    this.currentPageTitle = tab.title;
    this.sessionStorageKey = `sessionId_tab_${this.currentTabId}`;

    if (this.privateMode) {
      this.currentSessionId = `private_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    } else {
      const sessionData = await chrome.storage.local.get(this.sessionStorageKey);
      if (!sessionData[this.sessionStorageKey]) {
        this.currentSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        await chrome.storage.local.set({ [this.sessionStorageKey]: this.currentSessionId });
      } else {
        this.currentSessionId = sessionData[this.sessionStorageKey];
      }
    }

    this.pageTitle.textContent = this.currentPageTitle || 'Current Page';
    this.updateTokenCount(0);
  }

  async restoreSessionHistory() {
    if (this.privateMode) return false;
    if (!this.currentSessionId) return false;

    try {
      const response = await fetch(`${this.apiUrl}/api/session/${this.currentSessionId}`);
      if (!response.ok) {
        return false;
      }

      const data = await response.json();
      const queries = Array.isArray(data.queries) ? data.queries : [];
      if (!queries.length) {
        return false;
      }

      this.chatMessages.innerHTML = '';
      const recent = queries.slice(-10);
      recent.forEach((entry) => {
        if (entry.query) this.addMessage(entry.query, 'user');
        if (entry.answer) this.addMessage(entry.answer, 'assistant');
      });
      return true;
    } catch (error) {
      console.warn('Could not restore session history:', error);
      return false;
    }
  }

  displayWelcomeMessage() {
    const welcomeMsg = document.createElement('div');
    welcomeMsg.className = 'message system';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const strong = document.createElement('strong');
    strong.textContent = 'Welcome to Lumina!';
    contentDiv.appendChild(strong);
    contentDiv.appendChild(document.createElement('br'));
    contentDiv.appendChild(document.createTextNode(
      'I can answer questions about the current page using Retrieval-Augmented Generation (RAG).'
    ));
    contentDiv.appendChild(document.createElement('br'));
    contentDiv.appendChild(document.createTextNode('Ask me anything about: '));
    const titleNode = document.createElement('em');
    // Use textContent (not innerHTML) to prevent XSS from a malicious page title
    titleNode.textContent = this.currentPageTitle || 'this page';
    contentDiv.appendChild(titleNode);

    welcomeMsg.appendChild(contentDiv);
    this.chatMessages.appendChild(welcomeMsg);
    this.scrollToBottom();
  }

  async handleSendMessage() {
    await this.bootstrapPromise;

    const query = this.queryInput.value.trim();

    if (!query || this.isWaitingForResponse) return;

    this.addMessage(query, 'user');
    this.queryInput.value = '';
    this.queryInput.disabled = true;
    this.sendBtn.disabled = true;
    this.isWaitingForResponse = true;
    this.showLoading(true);
    this.hideError();

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const pageContent = await this.getPageContent(tab.id);

      const response = await this.sendQueryToBackend(query, pageContent);

      if (response.success) {
        this.addMessage(response.answer, 'assistant');
        this.updateTokenCount(response.tokens_used || 0);
        const primarySource = response.sources && response.sources.length ? response.sources[0] : null;
        if (primarySource && primarySource.text_snippet) {
          this.highlightSourceOnPage(tab.id, primarySource.text_snippet);
        }
      } else {
        const backendMessage = response.answer || response.error || 'Failed to get response';
        this.showError(backendMessage);
        this.addMessage(backendMessage, 'error');
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
    const sendExtractMessage = () => new Promise((resolve, reject) => {
      chrome.tabs.sendMessage(
        tabId,
        { action: 'extractPageContent' },
        (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message || 'Could not extract page content'));
            return;
          }

          if (response && response.success) {
            resolve(response.content);
            return;
          }

          reject(new Error(response?.error || 'Could not extract page content'));
        }
      );
    });

    try {
      return await sendExtractMessage();
    } catch (error) {
      const errorMessage = (error?.message || '').toLowerCase();
      const canRetryByInjecting =
        errorMessage.includes('receiving end does not exist') ||
        errorMessage.includes('could not establish connection') ||
        errorMessage.includes('message port closed');

      if (!canRetryByInjecting) {
        throw error;
      }

      // Recover automatically when content script is missing (e.g., after extension reload).
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['src/content/content.js']
      });

      return await sendExtractMessage();
    }
  }

  async sendQueryToBackend(query, pageContent) {
    const payload = {
      query,
      page_content: pageContent,
      page_url: this.currentPageUrl,
      session_id: this.currentSessionId,
      max_tokens: this.maxTokens,
      private_mode: this.privateMode,
      llm_provider: this.llmProvider || undefined,
      llm_model: this.llmModel || undefined,
      llm_api_key: this.llmApiKey || undefined
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

  async highlightSourceOnPage(tabId, sourceText) {
    try {
      await new Promise((resolve) => {
        chrome.tabs.sendMessage(
          tabId,
          { action: 'highlightSource', sourceText },
          () => resolve()
        );
      });
    } catch (error) {
      console.warn('Highlighting failed:', error);
    }
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

  async clearChat() {
    if (confirm('Are you sure you want to clear this chat?')) {
      // Only DELETE stored sessions; private sessions are never persisted on the backend
      if (this.currentSessionId && !this.privateMode) {
        try {
          await fetch(`${this.apiUrl}/api/session/${this.currentSessionId}`, { method: 'DELETE' });
        } catch (error) {
          console.warn('Could not clear backend session:', error);
        }
      }

      // Regenerate session ID matching current mode
      this.currentSessionId = this.privateMode
        ? `private_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        : `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      if (!this.privateMode && this.sessionStorageKey) {
        await chrome.storage.local.set({ [this.sessionStorageKey]: this.currentSessionId });
      }

      this.chatMessages.innerHTML = '';
      this.displayWelcomeMessage();
    }
  }

  openSettings() {
    document.getElementById('apiUrl').value = this.apiUrl;
    document.getElementById('apiKey').value = this.apiKey || '';
    document.getElementById('llmProvider').value = this.llmProvider || '';
    document.getElementById('llmModel').value = this.llmModel || '';
    document.getElementById('llmApiKey').value = this.llmApiKey || '';
    document.getElementById('maxTokens').value = this.maxTokens;
    document.getElementById('enablePrivateMode').checked = this.privateMode;
    this.settingsModal.classList.remove('hidden');
  }

  closeSettings() {
    this.settingsModal.classList.add('hidden');
  }

  async saveSettings() {
    // Validate apiUrl to prevent SSRF via a malicious sync-profile injection
    const rawUrl = (document.getElementById('apiUrl').value || '').trim();
    this.apiUrl = (rawUrl.startsWith('http://') || rawUrl.startsWith('https://'))
      ? rawUrl
      : 'http://localhost:8000';
    this.apiKey = document.getElementById('apiKey').value || null;
    this.llmProvider = (document.getElementById('llmProvider').value || '').trim();
    this.llmModel = (document.getElementById('llmModel').value || '').trim();
    this.llmApiKey = (document.getElementById('llmApiKey').value || '').trim();
    this.maxTokens = parseInt(document.getElementById('maxTokens').value) || 500;
    const previousPrivateMode = this.privateMode;
    this.privateMode = document.getElementById('enablePrivateMode').checked;

    await chrome.storage.sync.set({
      apiUrl: this.apiUrl,
      apiKey: this.apiKey,
      llmProvider: this.llmProvider,
      llmModel: this.llmModel,
      llmApiKey: this.llmApiKey,
      maxTokens: this.maxTokens,
      privateMode: this.privateMode
    });

    if (this.privateMode) {
      if (this.sessionStorageKey) {
        await chrome.storage.local.remove(this.sessionStorageKey);
      }
      this.currentSessionId = `private_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      this.chatMessages.innerHTML = '';
      this.displayWelcomeMessage();
    } else if (previousPrivateMode && this.sessionStorageKey) {
      this.currentSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      await chrome.storage.local.set({ [this.sessionStorageKey]: this.currentSessionId });
    }

    this.closeSettings();
    this.addMessage('Settings saved successfully!', 'system');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new ChatInterface();
});
