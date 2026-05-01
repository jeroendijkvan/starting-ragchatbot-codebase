// API base URL - use relative path to work from any host
const API_URL = '/api';

// Global state
let currentSessionId = null;

// DOM elements
let chatMessages, chatInput, sendButton, newChatButton, themeToggleButton, totalCourses, courseTitles;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  // Get DOM elements after page loads
  chatMessages = document.getElementById('chatMessages');
  chatInput = document.getElementById('chatInput');
  sendButton = document.getElementById('sendButton');
  newChatButton = document.getElementById('newChatButton');
  themeToggleButton = document.getElementById('themeToggleButton');
  totalCourses = document.getElementById('totalCourses');
  courseTitles = document.getElementById('courseTitles');

  initTheme();
  setupEventListeners();
  createNewSession();
  loadCourseStats();
});

// Theme Management
function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    }
}

function toggleTheme() {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    if (isLight) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('theme', 'dark');
    } else {
        document.documentElement.setAttribute('data-theme', 'light');
        localStorage.setItem('theme', 'light');
    }
}

// Event Listeners
function setupEventListeners() {
  // Theme toggle
  themeToggleButton.addEventListener('click', toggleTheme);

  // Chat functionality
  sendButton.addEventListener('click', sendMessage);
  chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });
  newChatButton.addEventListener('click', createNewSession);

  // Suggested questions
  document.querySelectorAll('.suggested-item').forEach((button) => {
    button.addEventListener('click', (e) => {
      const question = e.target.getAttribute('data-question');
      chatInput.value = question;
      sendMessage();
    });
  });
}

// Chat Functions
async function sendMessage() {
  const query = chatInput.value.trim();
  if (!query) return;

  // Disable input
  chatInput.value = '';
  chatInput.disabled = true;
  sendButton.disabled = true;

  // Add user message
  addMessage(query, 'user');

  // Add loading message - create a unique container for it
  const loadingMessage = createLoadingMessage();
  chatMessages.appendChild(loadingMessage);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const response = await fetch(`${API_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: query,
        session_id: currentSessionId,
      }),
    });

    if (!response.ok) throw new Error('Query failed');

    const data = await response.json();

    // Update session ID if new
    if (!currentSessionId) {
      currentSessionId = data.session_id;
    }

    // Replace loading message with response
    loadingMessage.remove();
    addMessage(data.answer, 'assistant', data.sources);
  } catch (error) {
    // Replace loading message with error
    loadingMessage.remove();
    addMessage(`Error: ${error.message}`, 'assistant');
  } finally {
    chatInput.disabled = false;
    sendButton.disabled = false;
    chatInput.focus();
  }
}

function createLoadingMessage() {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message assistant';
  messageDiv.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-body">
            <div class="message-content">
                <div class="loading">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `;
  return messageDiv;
}

function addMessage(content, type, sources = null, isWelcome = false) {
  const messageId = Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
  messageDiv.id = `message-${messageId}`;

  const displayContent = type === 'assistant' ? marked.parse(content) : escapeHtml(content);

  if (type === 'assistant') {
    let bodyHtml = `<div class="message-content">${displayContent}</div>`;
    if (sources && sources.length > 0) {
      bodyHtml += `
                <details class="sources-collapsible">
                    <summary class="sources-header">Sources</summary>
                    <div class="sources-content">${renderSources(sources)}</div>
                </details>
            `;
    }
    messageDiv.innerHTML = `
            <div class="message-avatar">AI</div>
            <div class="message-body">${bodyHtml}</div>
        `;
  } else {
    messageDiv.innerHTML = `<div class="message-content">${displayContent}</div>`;
  }
  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  return messageId;
}

function renderSources(sources) {
  return sources
    .map((s) => {
      const label = typeof s === 'string' ? s : s.label;
      const url = typeof s === 'object' ? s.url : null;
      if (url) {
        return `<a href="${url}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
      }
      return escapeHtml(label);
    })
    .join(', ');
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Removed removeMessage function - no longer needed since we handle loading differently

async function createNewSession() {
  currentSessionId = null;
  chatMessages.innerHTML = '';
  addMessage(
    'Welcome to the Course Materials Assistant! I can help you with questions about courses, lessons and specific content. What would you like to know?',
    'assistant',
    null,
    true
  );
}

// Load course statistics
async function loadCourseStats() {
  try {
    console.log('Loading course stats...');
    const response = await fetch(`${API_URL}/courses`);
    if (!response.ok) throw new Error('Failed to load course stats');

    const data = await response.json();
    console.log('Course data received:', data);

    // Update stats in UI
    if (totalCourses) {
      totalCourses.textContent = data.total_courses;
    }

    // Update course titles
    if (courseTitles) {
      if (data.course_titles && data.course_titles.length > 0) {
        courseTitles.innerHTML = data.course_titles
          .map((title) => `<div class="course-title-item">${title}</div>`)
          .join('');
      } else {
        courseTitles.innerHTML =
          '<span class="no-courses">No courses loaded yet. Add .txt files to the docs/ folder.</span>';
      }
    }
  } catch (error) {
    console.error('Error loading course stats:', error);
    // Set default values on error
    if (totalCourses) {
      totalCourses.textContent = '0';
    }
    if (courseTitles) {
      courseTitles.innerHTML = '<span class="error">Failed to load courses</span>';
    }
  }
}
