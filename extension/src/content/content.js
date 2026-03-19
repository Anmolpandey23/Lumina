/**
 * Content Script for Lumina
 * Extracts meaningful content from DOM and sends to background/popup
 * Handles security and filtering of sensitive content
 */

class DOMExtractor {
  constructor() {
    this.sensitiveSelectors = [
      'script',
      'style',
      'noscript',
      'nav',
      'footer',
      '[role="banner"]',
      '[role="navigation"]',
      '.navbar',
      '.sidebar',
      '.ad',
      '.advertisement',
      '.cookie-banner',
      '.privacy-notice',
      'form input[type="password"]'
    ];

    this.sensitiveUrls = [
      'login',
      'signin',
      'signup',
      'password',
      'banking',
      'payment',
      'checkout',
      'cart'
    ];

    this.contentSelectors = [
      'article',
      'main',
      '[role="main"]',
      '.content',
      '.post',
      '.page-content',
      'h1, h2, h3, h4, h5, h6',
      'p',
      'li',
      'blockquote'
    ];

    this.highlightClass = 'ai-copilot-source-highlight';
    this.highlightStyleId = 'ai-copilot-highlight-style';
    this.ensureHighlightStyles();
  }

  ensureHighlightStyles() {
    if (document.getElementById(this.highlightStyleId)) return;

    const style = document.createElement('style');
    style.id = this.highlightStyleId;
    style.textContent = `
      .${this.highlightClass} {
        background: rgba(255, 230, 120, 0.45) !important;
        outline: 2px solid rgba(255, 190, 0, 0.9) !important;
        border-radius: 6px !important;
        transition: all 0.3s ease;
      }
    `;
    document.head.appendChild(style);
  }

  /**
   * Check if current page is sensitive (shouldn't extract from)
   */
  isPageSensitive() {
    const url = window.location.href.toLowerCase();
    return this.sensitiveUrls.some(keyword => url.includes(keyword));
  }

  /**
   * Clean node of sensitive elements
   */
  cleanElement(element) {
    const clone = element.cloneNode(true);
    
    // Remove sensitive selectors
    this.sensitiveSelectors.forEach(selector => {
      clone.querySelectorAll(selector).forEach(el => el.remove());
    });

    // Remove hidden elements
    clone.querySelectorAll('[style*="display: none"], [hidden], .hidden, .sr-only').forEach(el => el.remove());

    return clone;
  }

  normalizeText(text) {
    return (text || '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .replace(/[^a-z0-9\s]/g, '')
      .trim();
  }

  extractUiSignals() {
    const lines = [];

    const parseIntSafe = (value) => {
      const match = String(value || '').match(/\d{1,4}/);
      return match ? parseInt(match[0], 10) : null;
    };

    // Generic top-bar controls with semantic labels
    const labelledControls = Array.from(
      document.querySelectorAll('button[aria-label], a[aria-label], [role="button"][aria-label]')
    )
      .map((el) => (el.getAttribute('aria-label') || '').trim())
      .filter((label) => label.length > 0 && label.length < 140)
      .slice(0, 40);

    if (labelledControls.length) {
      lines.push('Controls:');
      labelledControls.forEach((label) => lines.push(`- ${label}`));
    }

    // YouTube-specific notification extraction (icon + badge)
    const ytNotifButton = document.querySelector(
      'ytd-notification-topbar-button-renderer button, button[aria-label*="notification" i]'
    );

    let strictNotificationCount = null;

    if (ytNotifButton) {
      const aria = (ytNotifButton.getAttribute('aria-label') || '').trim();
      const notifContainer = ytNotifButton.closest('ytd-notification-topbar-button-renderer, div, button') || ytNotifButton;
      const badge = notifContainer.querySelector('#notification-count, [id*="notification"][id*="count"], .notification-count');
      const badgeText = ((badge && badge.textContent) || '').trim();
      const ariaCountMatch = aria.match(/(\d+)/);
      const count = (badgeText.match(/\d+/) || ariaCountMatch || [])[0] || '';

      if (count) {
        const n = parseIntSafe(count);
        if (n !== null) strictNotificationCount = n;
      }

      // Fallback: parse short numeric tokens only from the notification container subtree.
      if (strictNotificationCount === null) {
        const scopedNumberCandidates = [];
        const scopedNodes = [notifContainer, ...Array.from(notifContainer.querySelectorAll('*'))];
        scopedNodes.forEach((node) => {
          const text = (node.textContent || '').trim();
          if (!text) return;
          // Keep only compact numeric/badge-like values to avoid unrelated page numbers.
          if (/^\d{1,3}\+?$/.test(text)) {
            const parsed = parseIntSafe(text);
            if (parsed !== null) scopedNumberCandidates.push(parsed);
          }
        });

        if (scopedNumberCandidates.length) {
          strictNotificationCount = Math.max(...scopedNumberCandidates);
        }
      }

      // Add raw scoped text for backend fallback parsing (still confined to notification container).
      const rawScopedText = (notifContainer.textContent || '').replace(/\s+/g, ' ').trim();
      if (rawScopedText) {
        lines.push(`Notification container text: ${rawScopedText.slice(0, 160)}`);
      }

      if (count) {
        lines.push(`Notification icon visible with count: ${count}`);
      } else if (aria) {
        lines.push(`Notification icon visible: ${aria}`);
      } else {
        lines.push('Notification icon appears visible.');
      }
    }

    // Fallback to strict global notification count element only if button path failed
    if (strictNotificationCount === null) {
      const globalNotifCountEl = document.querySelector('#notification-count, [id*="notification"][id*="count"]');
      const globalText = (globalNotifCountEl?.textContent || '').trim();
      const n = parseIntSafe(globalText);
      if (n !== null) {
        strictNotificationCount = n;
      }
    }

    // Generic notification cues in visible labels/titles
    const notificationHints = Array.from(document.querySelectorAll('[aria-label], [title]'))
      .map((el) => (el.getAttribute('aria-label') || el.getAttribute('title') || '').trim())
      .filter((text) => /notification|bell|alert/i.test(text))
      .slice(0, 12);

    // Emit one canonical line for backend parsing from strict sources only.
    if (strictNotificationCount !== null) {
      lines.push(`YouTube notification count detected: ${strictNotificationCount}`);
    }

    if (notificationHints.length) {
      lines.push('Notification hints:');
      notificationHints.forEach((hint) => lines.push(`- ${hint}`));
    }

    return lines.join('\n');
  }

  extractYouTubeSubscriptions() {
    if (!/youtube\.com/i.test(window.location.hostname)) {
      return '';
    }

    const section = document.querySelector('ytd-guide-section-renderer');
    const subItems = Array.from(
      document.querySelectorAll('ytd-guide-entry-renderer a[title], ytd-guide-entry-renderer yt-formatted-string')
    )
      .map((el) => (el.getAttribute('title') || el.textContent || '').replace(/\s+/g, ' ').trim())
      .filter((name) => name.length > 0)
      .filter((name) => !/home|shorts|history|playlist|watch later|liked videos|you|subscriptions/i.test(name))
      .slice(0, 30);

    if (!subItems.length) {
      return '';
    }

    const lines = [`count=${subItems.length}`];
    subItems.forEach((name, idx) => lines.push(`item${idx + 1}=${name}`));
    return lines.join('\n');
  }

  extractYouTubeVideoCards() {
    if (!/youtube\.com/i.test(window.location.hostname)) {
      return '';
    }

    const cards = Array.from(document.querySelectorAll('ytd-rich-item-renderer, ytd-video-renderer, ytd-grid-video-renderer'));
    if (!cards.length) {
      return '';
    }

    const lines = cards
      .map((card) => {
        const rect = card.getBoundingClientRect();
        const title = (card.querySelector('#video-title, a#video-title, h3 a')?.textContent || '').replace(/\s+/g, ' ').trim();
        const channel = (card.querySelector('#channel-name a, ytd-channel-name a, #text.ytd-channel-name')?.textContent || '').replace(/\s+/g, ' ').trim();
        const allText = (card.textContent || '').replace(/\s+/g, ' ').trim();
        const lessons = (allText.match(/(\d+)\s+lessons?/i) || [])[1] || '';
        let duration = (card.querySelector('ytd-thumbnail-overlay-time-status-renderer span')?.textContent || '').replace(/\s+/g, ' ').trim();

        // Fallback for layouts where duration is rendered differently.
        if (!duration) {
          const durationMatch = allText.match(/\b(\d{1,2}:\d{2}(?::\d{2})?)\b/);
          if (durationMatch) {
            duration = durationMatch[1];
          }
        }

        if (!title) return '';

        const parts = [
          `x=${Math.round(rect.left || 0)}`,
          `y=${Math.round(rect.top || 0)}`,
          `title=${title}`
        ];
        if (channel) parts.push(`channel=${channel}`);
        if (lessons) parts.push(`lessons=${lessons}`);
        if (duration) parts.push(`duration=${duration}`);
        return `CARD|${parts.join('|')}`;
      })
      .filter(Boolean)
      .slice(0, 40);

    return lines.join('\n');
  }

  extractDashboardSignals(rootElement) {
    const root = rootElement || document.body;
    const lines = [];
    const seen = new Set();

    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
    const scoreKeywords = /workers?|online|alerts?|critical|battery|status|monitoring|risk map|settings|control room|live monitoring|daily report|pre-entry gate|rakshak|inspect|focus on map/i;

    const pushUnique = (value) => {
      const text = normalize(value);
      if (!text) return;
      const key = text.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      lines.push(text);
    };

    // Capture readable navigation/action labels.
    const controlLabels = Array.from(root.querySelectorAll('a, button, [role="button"], [role="menuitem"], li'))
      .map((el) => normalize(el.textContent || ''))
      .filter((text) => text.length >= 3 && text.length <= 60)
      .filter((text) => /[a-z]/i.test(text))
      .filter((text) => scoreKeywords.test(text));

    controlLabels.slice(0, 80).forEach(pushUnique);

    // Capture compact metric cards such as "Workers Online 4".
    const metricBlocks = Array.from(root.querySelectorAll('div, section, article, li'))
      .map((el) => normalize(el.textContent || ''))
      .filter((text) => text.length >= 4 && text.length <= 120)
      .filter((text) => /[a-z]/i.test(text))
      .filter((text) => /\d/.test(text) || scoreKeywords.test(text));

    metricBlocks.slice(0, 120).forEach(pushUnique);

    return lines.slice(0, 120).join('\n');
  }

  getReadabilityRoot(cleanedBody) {
    const directMain =
      cleanedBody.querySelector('article') ||
      cleanedBody.querySelector('main') ||
      cleanedBody.querySelector('[role="main"]');

    if (directMain && directMain.textContent.trim().length > 400) {
      return directMain;
    }

    const candidates = Array.from(
      cleanedBody.querySelectorAll('article, main, [role="main"], section, div')
    );

    let bestNode = cleanedBody;
    let bestScore = -Infinity;

    candidates.forEach((node) => {
      const blocks = node.querySelectorAll('p, li, blockquote');
      const textParts = Array.from(blocks)
        .map((el) => el.textContent.trim())
        .filter((text) => text.length > 40);

      if (!textParts.length) return;

      const textLength = textParts.join(' ').length;
      if (textLength < 300) return;

      const allText = node.textContent || '';
      const linkTextLength = Array.from(node.querySelectorAll('a'))
        .map((a) => (a.textContent || '').length)
        .reduce((sum, len) => sum + len, 0);
      const linkDensity = allText.length ? linkTextLength / allText.length : 1;

      const score = textLength + textParts.length * 120 - linkDensity * 800;

      if (score > bestScore) {
        bestScore = score;
        bestNode = node;
      }
    });

    return bestNode;
  }

  clearHighlights() {
    document.querySelectorAll(`.${this.highlightClass}`).forEach((el) => {
      el.classList.remove(this.highlightClass);
    });
  }

  highlightSourceParagraph(sourceText) {
    if (!sourceText || sourceText.trim().length < 20) {
      return { success: false, error: 'No source text provided' };
    }

    this.clearHighlights();

    const sourceNorm = this.normalizeText(sourceText);
    const sourcePrefix = sourceNorm.slice(0, 180);
    const sourceWords = new Set(sourceNorm.split(' ').filter((w) => w.length > 4));

    const candidates = Array.from(document.querySelectorAll('p, li, blockquote'))
      .filter((el) => {
        const text = (el.textContent || '').trim();
        return text.length > 40;
      });

    let bestCandidate = null;
    let bestScore = 0;

    candidates.forEach((el) => {
      const text = (el.textContent || '').trim();
      const norm = this.normalizeText(text);
      if (!norm) return;

      let score = 0;

      if (norm.includes(sourcePrefix)) {
        score += 100;
      }

      const words = new Set(norm.split(' ').filter((w) => w.length > 4));
      let overlap = 0;
      sourceWords.forEach((word) => {
        if (words.has(word)) overlap += 1;
      });
      score += overlap;

      if (score > bestScore) {
        bestScore = score;
        bestCandidate = el;
      }
    });

    if (!bestCandidate || bestScore < 5) {
      return { success: false, error: 'Could not find matching paragraph to highlight' };
    }

    bestCandidate.classList.add(this.highlightClass);
    bestCandidate.scrollIntoView({ behavior: 'smooth', block: 'center' });

    return { success: true, highlightedText: bestCandidate.textContent.trim().slice(0, 200) };
  }

  /**
   * Extract main content from page
   */
  extractContent() {
    if (this.isPageSensitive()) {
      return {
        success: false,
        error: 'This page contains sensitive information. Content extraction is disabled.',
        content: ''
      };
    }

    try {
      let content = '';
      let cleanedBody = this.cleanElement(document.body);
      const uiSignals = this.extractUiSignals();
      const dashboardSignals = this.extractDashboardSignals(cleanedBody);
      const isYouTube = /(^|\.)youtube\.com$/i.test(window.location.hostname || '');
      const youtubeSubscriptions = isYouTube ? this.extractYouTubeSubscriptions() : '';
      const youtubeVideoCards = isYouTube ? this.extractYouTubeVideoCards() : '';

      // Extract pricing information FIRST from full body (before readability filtering)
      // Look for pricing containers/cards that group price + plan name + features
      const pricingContainers = Array.from(cleanedBody.querySelectorAll('div, section, article, li'))
        .filter(container => {
          const text = (container.textContent || '').trim();
          const hasPrice = /[\$€£¥₹]\s*\d+/i.test(text);
          const hasPricingKeyword = /\b(price|pricing|plan|subscription|per month|per year|\/month|\/year|subscribe)\b/i.test(text);
          // Look for containers that have price AND are reasonably sized (pricing cards)
          return (hasPrice || hasPricingKeyword) && text.length > 10 && text.length < 800;
        })
        .map(container => {
          const text = container.textContent.trim();
          // Try to find heading/title in this container
          const heading = container.querySelector('h1, h2, h3, h4, h5, h6, .title, [class*="title"], [class*="name"]');
          if (heading) {
            const headingText = heading.textContent.trim();
            // Return heading + full container text (this captures price + features together)
            return `=== ${headingText} ===\n${text}`;
          }
          return text;
        })
        .filter((text, index, arr) => {
          // Remove containers that are completely contained in larger containers
          return !arr.some((other, i) => i !== index && other.includes(text) && other.length > text.length + 50);
        })
        .slice(0, 20) // Limit to 20 pricing containers
        .join('\n\n---\n\n');

      // Readability-style main content extraction
      let mainContent = this.getReadabilityRoot(cleanedBody);

      // Extract headings
      const headings = Array.from(mainContent.querySelectorAll('h1, h2, h3, h4, h5, h6'))
        .map(h => `${h.tagName}: ${h.textContent.trim()}`)
        .filter(h => h.split(':')[1].trim().length > 0)
        .join('\n');

      // Extract readable text blocks
      const paragraphs = Array.from(mainContent.querySelectorAll('p, li, blockquote'))
        .map(p => p.textContent.trim())
        .filter(p => p.length > 40); // Keep meaningful readable blocks

      // Extract lists
      const lists = Array.from(mainContent.querySelectorAll('ul, ol'))
        .map(list => {
          const items = Array.from(list.querySelectorAll('li'))
            .map(li => `• ${li.textContent.trim()}`)
            .join('\n');
          return items;
        })
        .join('\n\n');

      // Extract tables
      const tables = Array.from(mainContent.querySelectorAll('table'))
        .map(table => {
          const rows = Array.from(table.querySelectorAll('tr'))
            .map(tr => {
              const cells = Array.from(tr.querySelectorAll('td, th'))
                .map(cell => cell.textContent.trim())
                .join(' | ');
              return cells;
            })
            .join('\n');
          return rows;
        })
        .join('\n\n');

      // Combine content while avoiding empty/irrelevant section headers.
      const sections = [
        `Page Title: ${document.title}`,
        `URL: ${window.location.href}`
      ];

      const pushSection = (title, body) => {
        if (!body || !String(body).trim()) return;
        sections.push('', `${title}:`, String(body).trim());
      };

      pushSection('UI ELEMENTS', uiSignals);
      pushSection('DASHBOARD SIGNALS', dashboardSignals);

      if (isYouTube) {
        pushSection('YOUTUBE SUBSCRIPTIONS', youtubeSubscriptions);
        pushSection('YOUTUBE VIDEO CARDS', youtubeVideoCards);
      }

      pushSection('HEADINGS', headings);
      pushSection('PRICING & COSTS', pricingContainers);
      pushSection('READABLE CONTENT', paragraphs.slice(0, 50).join('\n\n'));
      pushSection('LISTS', lists);
      pushSection('TABLES', tables);

      content = sections.join('\n');

      return {
        success: true,
        content: content.slice(0, 50000), // Limit to 50K chars
        pageTitle: document.title,
        pageUrl: window.location.href,
        extractedMode: 'readability-style',
        extractedAt: new Date().toISOString()
      };
    } catch (error) {
      console.error('Error extracting content:', error);
      return {
        success: false,
        error: error.message,
        content: ''
      };
    }
  }

  /**
   * Extract structured data from page
   */
  extractStructuredData() {
    try {
      const data = {
        title: document.title,
        url: window.location.href,
        description: '',
        language: document.documentElement.lang || 'en'
      };

      // Get meta description
      const metaDesc = document.querySelector('meta[name="description"]');
      if (metaDesc) {
        data.description = metaDesc.getAttribute('content');
      }

      return data;
    } catch (error) {
      console.error('Error extracting structured data:', error);
      return null;
    }
  }
}

// Initialize extractor
const extractor = new DOMExtractor();

// Listen for messages from popup/background
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  try {
    if (request.action === 'extractPageContent') {
      const result = extractor.extractContent();
      sendResponse(result);
    } else if (request.action === 'extractStructuredData') {
      const result = extractor.extractStructuredData();
      sendResponse({ success: true, data: result });
    } else if (request.action === 'highlightSource') {
      const result = extractor.highlightSourceParagraph(request.sourceText || '');
      sendResponse(result);
    } else if (request.action === 'clearHighlights') {
      extractor.clearHighlights();
      sendResponse({ success: true });
    } else {
      sendResponse({ success: false, error: 'Unknown action' });
    }
  } catch (error) {
    console.error('Message handler error:', error);
    sendResponse({ success: false, error: error.message });
  }
});

console.log('Lumina content script loaded');
