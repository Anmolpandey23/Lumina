/**
 * Background Service Worker for AI Browsing Copilot
 * Manages extension lifecycle, event handling, and inter-script communication
 */

// Initialize extension
chrome.runtime.onInstalled.addListener((details) => {
  console.log('AI Browsing Copilot installed/updated');
  
  if (details.reason === 'install') {
    // Open welcome page on first install
    chrome.tabs.create({
      url: 'https://github.com/yourusername/ai-browsing-copilot#readme'
    });
  }

  // Set up storage defaults
  chrome.storage.sync.get({
    apiUrl: 'http://localhost:8000',
    apiKey: null,
    maxTokens: 500,
    privateMode: false
  }, (items) => {
    // Storage initialized
  });
});

// Handle tab changes
chrome.tabs.onActivated.addListener((activeInfo) => {
  chrome.tabs.get(activeInfo.tabId, (tab) => {
    // Could trigger page analysis here if needed
    console.log('Tab activated:', tab.title);
  });
});

// Handle messages from popup and content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getSessionData') {
    chrome.storage.session.get('sessionId', (data) => {
      sendResponse(data);
    });
    return true; // Will respond asynchronously
  }
});

// Listen for errors and log them
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'logError') {
    console.error('Extension error:', request.error, request.context);
  }
});

// Set up rate limiting and cache
const sessionCache = new Map();
const REQUEST_TIMEOUT = 30000; // 30 seconds

/**
 * Clear old cache entries periodically
 */
setInterval(() => {
  const now = Date.now();
  for (const [key, value] of sessionCache.entries()) {
    if (now - value.timestamp > 3600000) { // 1 hour
      sessionCache.delete(key);
    }
  }
}, 600000); // Clean every 10 minutes

console.log('AI Browsing Copilot background service worker loaded');
