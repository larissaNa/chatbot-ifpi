const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const chatBox = document.getElementById('chat-box');
const chatContainer = document.getElementById('chat-container');
const conversationList = document.getElementById('conversation-list');
const newChatBtn = document.getElementById('new-chat-btn');
const sidebarChatToggle = document.getElementById('sidebar-chat-toggle');
const sidebarChatDropdown = document.getElementById('sidebar-chat-dropdown');
const sidebarChatItem = document.querySelector('.sidebar-chat-item');

let activeThreadId = null;

if (chatContainer && document.body) {
  document.body.classList.add('chat-layout-page');
}

function syncNavbarHeightVar() {
  const el =
    document.querySelector('.header.navbar') ||
    document.querySelector('nav.navbar') ||
    document.querySelector('.navbar') ||
    document.querySelector('header');

  const height = (() => {
    if (!el) return 0;
    const pos = window.getComputedStyle(el).position;
    if (pos !== 'fixed' && pos !== 'sticky') return 0;
    return Math.ceil(el.getBoundingClientRect().height);
  })();
  document.documentElement.style.setProperty('--navbar-height', `${height}px`);
}

const thoughtsIconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="margin-right: 8px;">
  <path d="M9 18h6"/>
  <path d="M10 22h4"/>
  <path d="M12 2a7 7 0 0 0-4.6 12.28c.72.62 1.26 1.46 1.5 2.39L9 17h6l.1-.33c.24-.93.78-1.77 1.5-2.39A7 7 0 0 0 12 2Z"/>
</svg>`;

function safeUrl(url) {
  try {
    const u = new URL(url, window.location.origin);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    return u.href;
  } catch {
    return null;
  }
}

function readableDocName(url) {
  try {
    const u = new URL(url);
    const path = u.pathname.replace(/\/+$/, '');
    const last = path.split('/').filter(Boolean).pop();
    if (last && last.length >= 3) return decodeURIComponent(last);
    return u.hostname;
  } catch {
    return 'Documento';
  }
}

function enhanceBotBubble(bubble) {
  if (!bubble) return;

  const anchors = Array.from(bubble.querySelectorAll('a'))
    .map((a) => {
      const href = safeUrl(a.getAttribute('href') || '');
      if (!href) return null;
      const rawText = (a.textContent || '').trim();
      const isRawLink = /^https?:\/\//i.test(rawText) || rawText === href;
      const label = isRawLink ? readableDocName(href) : rawText;
      return { a, href, label, isRawLink };
    })
    .filter(Boolean);

  if (anchors.length === 0) return;

  const unique = new Map();
  anchors.forEach(({ href, label }) => {
    if (!unique.has(href)) unique.set(href, label || readableDocName(href));
  });

  anchors.forEach(({ a, href, label, isRawLink }) => {
    a.setAttribute('href', href);
    a.setAttribute('target', '_blank');
    a.setAttribute('rel', 'noopener noreferrer');
    if (isRawLink) {
      a.textContent = label || readableDocName(href);
    }
  });

  const labelsToRemove = new Set(['fonte:', 'fontes:', 'referência:', 'referencias:', 'referências:']);
  Array.from(bubble.querySelectorAll('p')).forEach((p) => {
    const t = (p.textContent || '').trim().toLowerCase();
    if (labelsToRemove.has(t)) p.remove();
  });

  Array.from(bubble.querySelectorAll('p')).forEach((p) => {
    const onlyChild = p.childNodes.length === 1 ? p.childNodes[0] : null;
    if (!onlyChild || onlyChild.nodeType !== Node.ELEMENT_NODE) return;
    if (onlyChild.tagName.toLowerCase() !== 'a') return;
    const text = (onlyChild.textContent || '').trim();
    if (!/^https?:\/\//i.test(text)) return;
    p.remove();
  });

  Array.from(bubble.querySelectorAll('ul,ol')).forEach((listEl) => {
    const links = Array.from(listEl.querySelectorAll('a'))
      .map((a) => safeUrl(a.getAttribute('href') || ''))
      .filter(Boolean);
    if (links.length === 0) return;
    const allInUnique = links.every((h) => unique.has(h));
    if (allInUnique) listEl.remove();
  });

  const sources = document.createElement('div');
  sources.className = 'bot-sources';

  const chips = document.createElement('div');
  chips.className = 'bot-sources-chips';

  const docIcon = `<svg class="bot-source-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 3h7l3 3v15a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.8"/><path d="M14 3v4a1 1 0 0 0 1 1h4" stroke="currentColor" stroke-width="1.8"/></svg>`;

  unique.forEach((label, href) => {
    const link = document.createElement('a');
    link.className = 'bot-source-chip';
    link.href = href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.innerHTML = `${docIcon}<span class="bot-source-name"></span>`;
    const nameEl = link.querySelector('.bot-source-name');
    if (nameEl) nameEl.textContent = label;
    try {
      const u = new URL(href);
      const section = (u.hash || '').replace(/^#/, '').trim();
      if (section) {
        link.title = decodeURIComponent(section);
      }
    } catch {
    }
    chips.appendChild(link);
  });

  sources.appendChild(chips);
  bubble.appendChild(sources);
}

function createMessageBubble(sender, text, options = {}) {
    const normalizedOptions = typeof options === 'boolean' ? { isLoading: options } : (options || {});
    const isLoading = !!normalizedOptions.isLoading;
    const messageId = normalizedOptions.messageId || null;
    const feedbackRating = normalizedOptions.feedbackRating || null;
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const isUser = sender === 'user';

    const message = document.createElement('div');
    message.className = `chat-message ${isUser ? 'user' : 'bot'}`;
    if (messageId) {
      message.dataset.messageId = String(messageId);
    }

    const avatar = document.createElement('img');
    avatar.className = 'chat-avatar';
    avatar.src = isUser
      ? 'https://cdn-icons-png.flaticon.com/512/9131/9131529.png'
      : logoUrl;

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';

    if (isLoading) {
      message.classList.add('loading-message');
      const typing = document.createElement('div');
      typing.className = 'typing-indicator';

      const label = document.createElement('span');
      label.textContent = 'Digitando...';

      const loader = document.createElement('span');
      loader.className = 'loader';
      loader.innerHTML = `<span></span><span></span><span></span>`;

      typing.appendChild(label);
      typing.appendChild(loader);
      bubble.appendChild(typing);
    } else {
      const md = window.markdownit({
        breaks: true,
        linkify: true,
      });
      const formattedText = md.render(text || '');
      bubble.innerHTML = formattedText;
      if (!isUser) {
        enhanceBotBubble(bubble);
      }
    }

    const timestampElem = document.createElement('div');
    timestampElem.className = 'chat-timestamp';
    timestampElem.innerText = timestamp;

    const content = document.createElement('div');
    content.appendChild(bubble);
    content.appendChild(timestampElem);

    if (isUser) {
      message.appendChild(content);
      message.appendChild(avatar);
    } else {
      message.appendChild(avatar);
      message.appendChild(content);
    }

    chatBox.appendChild(message);
    chatBox.scrollTop = chatBox.scrollHeight;

    if (!isUser && !isLoading && messageId) {
      appendFeedbackControls(message, messageId, feedbackRating);
    }

    return message;
  }

function resetChatView() {
  chatBox.innerHTML = '';
}

function setInitialState(enabled) {
  if (enabled) {
    chatContainer.classList.add('initial-state');
  } else {
    chatContainer.classList.remove('initial-state');
  }
}

function truncateText(text, max = 60) {
  const value = (text || '').trim();
  if (!value) return 'Nova conversa';
  return value.length > max ? `${value.slice(0, max - 1)}...` : value;
}

function formatConversationDate(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString([], {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function renderConversationList(conversations = []) {
  if (!conversationList) return;
  conversationList.innerHTML = '';

  if (!Array.isArray(conversations) || conversations.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'conversation-empty';
    empty.innerHTML = `
      <div class="conversation-empty-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M8 10h8"/>
          <path d="M8 14h5"/>
          <path d="M6 4h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-7l-4 4v-4H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"/>
        </svg>
      </div>
      <div class="conversation-empty-title">Nenhuma conversa iniciada</div>
      <p class="conversation-empty-text">Clique em "Nova conversa" para começar um novo atendimento.</p>
    `;
    conversationList.appendChild(empty);
    return;
  }

  conversations.forEach((conversation) => {
    const row = document.createElement('div');
    row.className = 'conversation-item sidebar-conversation-item';
    if (conversation.thread_id === activeThreadId) {
      row.classList.add('active');
    }

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'sidebar-conversation-main';
    button.dataset.threadId = conversation.thread_id;

    const title = document.createElement('div');
    title.className = 'conversation-title sidebar-conversation-title';
    title.textContent = truncateText(conversation.title || 'Nova conversa', 80);

    button.appendChild(title);
    button.addEventListener('click', () => {
      if (!conversation.thread_id || conversation.thread_id === activeThreadId) return;
      loadConversation(conversation.thread_id);
    });

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'sidebar-conversation-delete';
    deleteBtn.setAttribute('aria-label', 'Apagar conversa');
    deleteBtn.title = 'Apagar conversa';
    deleteBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>`;
    deleteBtn.addEventListener('click', async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await deleteConversation(conversation.thread_id);
    });

    row.appendChild(button);
    row.appendChild(deleteBtn);
    conversationList.appendChild(row);
  });
}

function setSidebarDropdownOpen(isOpen) {
  if (!sidebarChatDropdown || !sidebarChatItem || !sidebarChatToggle) return;
  sidebarChatDropdown.classList.toggle('open', !!isOpen);
  sidebarChatItem.classList.toggle('open', !!isOpen);
  sidebarChatToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
}

// --- Feedback modal state ---
let _feedbackModalTarget = null; // { botMessageId, messageElement }

function openFeedbackModal(botMessageId, messageElement) {
  _feedbackModalTarget = { botMessageId, messageElement };
  const overlay = document.getElementById('feedback-modal-overlay');
  const textarea = document.getElementById('feedback-modal-text');
  const charCount = document.getElementById('feedback-modal-chars');
  if (!overlay) return;
  textarea.value = '';
  if (charCount) charCount.textContent = '0';
  overlay.style.display = 'flex';
  textarea.focus();
}

function closeFeedbackModal() {
  const overlay = document.getElementById('feedback-modal-overlay');
  if (overlay) overlay.style.display = 'none';
  _feedbackModalTarget = null;
}

async function submitFeedbackModal() {
  if (!_feedbackModalTarget) return;
  const { botMessageId, messageElement } = _feedbackModalTarget;
  const textarea = document.getElementById('feedback-modal-text');
  const userComment = (textarea ? textarea.value : '').trim();
  const submitBtn = document.getElementById('feedback-modal-submit');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Enviando...'; }

  try {
    const res = await fetch('/chatbot/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_message_id: botMessageId, rating: 'down', user_comment: userComment })
    });
    if (!res.ok) throw new Error('Erro ao enviar feedback');
    const data = await res.json();
    updateFeedbackState(messageElement, data.rating);
    setFeedbackProcessingState(messageElement, 'Obrigado pelo feedback!');
    setTimeout(() => setFeedbackProcessingState(messageElement, ''), 3000);
    closeFeedbackModal();
  } catch {
    setFeedbackProcessingState(messageElement, 'Nao foi possivel enviar o feedback agora.');
    setTimeout(() => setFeedbackProcessingState(messageElement, ''), 3000);
    closeFeedbackModal();
  } finally {
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Enviar feedback'; }
  }
}

async function sendFeedback(botMessageId, rating, messageElement) {
  // Feedback positivo: envia diretamente sem modal
  try {
    const res = await fetch('/chatbot/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_message_id: botMessageId, rating })
    });
    if (!res.ok) return;
    const data = await res.json();
    updateFeedbackState(messageElement, data.rating);
  } catch {
    // silencioso para feedback positivo
  }
}

// Inicializa eventos do modal de feedback
document.addEventListener('DOMContentLoaded', () => {
  const closeBtn = document.getElementById('feedback-modal-close');
  const cancelBtn = document.getElementById('feedback-modal-cancel');
  const submitBtn = document.getElementById('feedback-modal-submit');
  const overlay = document.getElementById('feedback-modal-overlay');
  const textarea = document.getElementById('feedback-modal-text');
  const charCount = document.getElementById('feedback-modal-chars');

  if (closeBtn) closeBtn.addEventListener('click', closeFeedbackModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeFeedbackModal);
  if (submitBtn) submitBtn.addEventListener('click', submitFeedbackModal);
  if (overlay) overlay.addEventListener('click', (e) => { if (e.target === overlay) closeFeedbackModal(); });
  if (textarea && charCount) {
    textarea.addEventListener('input', () => { charCount.textContent = textarea.value.length; });
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay && overlay.style.display !== 'none') closeFeedbackModal();
  });
});

function updateFeedbackState(messageElement, rating) {
  if (!messageElement) return;
  const controls = messageElement.querySelector('.chat-feedback');
  if (!controls) return;
  controls.dataset.rating = rating || '';
  controls.querySelectorAll('.chat-feedback-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.rating === rating);
  });
}

function setFeedbackProcessingState(messageElement, message = '') {
  if (!messageElement) return;
  const controls = messageElement.querySelector('.chat-feedback');
  if (!controls) return;

  let statusEl = controls.querySelector('.chat-feedback-status');
  if (!message) {
    if (statusEl) statusEl.remove();
    controls.classList.remove('is-processing');
    controls.querySelectorAll('.chat-feedback-btn').forEach((btn) => {
      btn.disabled = false;
    });
    return;
  }

  if (!statusEl) {
    statusEl = document.createElement('span');
    statusEl.className = 'chat-feedback-status';
    controls.appendChild(statusEl);
  }
  statusEl.textContent = message;
  controls.classList.add('is-processing');
  controls.querySelectorAll('.chat-feedback-btn').forEach((btn) => {
    btn.disabled = true;
  });
}

function appendFeedbackControls(messageElement, botMessageId, feedbackRating = null) {
  if (!messageElement || !botMessageId) return;
  const contentDiv = messageElement.querySelector('div:not(.chat-avatar)');
  if (!contentDiv) return;

  const thumbsUpIcon = `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11V5.8c0-.9.3-1.7.9-2.4L11.2 2l1 1c.5.5.8 1.2.8 1.9V8h4.4c1.1 0 1.9 1 1.7 2.1l-1 6.2c-.2 1-1 1.7-2 1.7H9"/><path d="M5 10h2a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1Z"/></svg>`;
  const thumbsDownIcon = `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M15 13v5.2c0 .9-.3 1.7-.9 2.4L12.8 22l-1-1a2.7 2.7 0 0 1-.8-1.9V16H6.6c-1.1 0-1.9-1-1.7-2.1l1-6.2c.2-1 1-1.7 2-1.7H15"/><path d="M19 14h-2a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1Z"/></svg>`;

  const wrapper = document.createElement('div');
  wrapper.className = 'chat-feedback';
  wrapper.dataset.rating = feedbackRating || '';

  const label = document.createElement('span');
  label.className = 'chat-feedback-label';
  label.textContent = 'Essa resposta ajudou?';

  const upBtn = document.createElement('button');
  upBtn.type = 'button';
  upBtn.className = 'chat-feedback-btn';
  upBtn.dataset.rating = 'up';
  upBtn.dataset.tooltip = 'Útil';
  upBtn.setAttribute('aria-label', 'Útil');
  upBtn.title = 'Útil';
  upBtn.innerHTML = thumbsUpIcon;

  const downBtn = document.createElement('button');
  downBtn.type = 'button';
  downBtn.className = 'chat-feedback-btn';
  downBtn.dataset.rating = 'down';
  downBtn.dataset.tooltip = 'Não útil';
  downBtn.setAttribute('aria-label', 'Não útil');
  downBtn.title = 'Não útil';
  downBtn.innerHTML = thumbsDownIcon;

  upBtn.addEventListener('click', async () => {
    await sendFeedback(botMessageId, 'up', messageElement);
  });
  downBtn.addEventListener('click', () => {
    // Abre modal para coletar comentário antes de enviar o feedback negativo
    openFeedbackModal(botMessageId, messageElement);
  });
  wrapper.appendChild(upBtn);
  wrapper.appendChild(downBtn);

  wrapper.prepend(label);
  contentDiv.appendChild(wrapper);
  updateFeedbackState(messageElement, feedbackRating);
}

async function refreshConversationList() {
  try {
    const res = await fetch('/chatbot/conversations', { method: 'GET' });
    if (!res.ok) return;
    const data = await res.json();
    if (data.active_thread_id) {
      activeThreadId = data.active_thread_id;
    }
    renderConversationList(data.conversations || []);
  } catch (error) {
  }
}

async function loadConversation(threadId = null) {
  try {
    const url = threadId ? `/chatbot?thread_id=${encodeURIComponent(threadId)}` : '/chatbot';
    const res = await fetch(url, { method: 'GET' });
    if (!res.ok) return;

    const data = await res.json();
    activeThreadId = data.thread_id || threadId || activeThreadId;
    resetChatView();

    if (!data.messages || !Array.isArray(data.messages) || data.messages.length === 0) {
      setInitialState(true);
      await refreshConversationList();
      return;
    }

    setInitialState(false);
    data.messages.forEach((msg) => {
      const sender = msg.sender === 'bot' ? 'bot' : 'user';
      const messageElement = createMessageBubble(sender, msg.content || '', {
        messageId: msg.id,
        feedbackRating: msg.feedback_rating || null,
      });
      if (sender === 'bot' && msg.thoughts) {
        appendThoughtsDropdown(messageElement, msg.thoughts);
      }
    });
    await refreshConversationList();
  } catch (error) {
  }
}

async function startNewConversation() {
  try {
    const res = await fetch('/chatbot/conversations', { method: 'POST' });
    if (!res.ok) return;
    const data = await res.json();
    activeThreadId = data.thread_id || null;
    resetChatView();
    setInitialState(true);
    input.focus();
    await refreshConversationList();
    setSidebarDropdownOpen(true);
  } catch (error) {
  }
}

async function deleteConversation(threadId) {
  if (!threadId) return;
  try {
    const res = await fetch(`/chatbot/conversations/${encodeURIComponent(threadId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) return;

    const data = await res.json();
    const deletedActive = activeThreadId === threadId;
    activeThreadId = data.active_thread_id || (deletedActive ? null : activeThreadId);

    await refreshConversationList();

    if (deletedActive) {
      if (activeThreadId) {
        await loadConversation(activeThreadId);
      } else {
        resetChatView();
        setInitialState(true);
      }
    }
  } catch (error) {
  }
}

function appendThoughtsDropdown(messageElement, thoughtsText) {
  if (!thoughtsText) return;

  const dropdown = document.createElement('details');
  dropdown.className = 'thoughts-dropdown';
  dropdown.innerHTML = `<summary class="d-flex align-items-center">${thoughtsIconSvg} Ver raciocínio do sistema</summary><pre>${thoughtsText}</pre>`;

  const contentDiv = messageElement.querySelector('div:not(.chat-avatar)');
  if (contentDiv) {
    contentDiv.appendChild(dropdown);
  } else {
    messageElement.appendChild(dropdown);
  }
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const userText = input.value.trim();
  if (!userText) return;

  setInitialState(false);

  createMessageBubble('user', userText);
  input.value = "";

  const loadingMsg = createMessageBubble('bot', '', { isLoading: true });

  try {
    const res = await fetch('/chatbot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText, thread_id: activeThreadId })
    });

    const data = await res.json();
    chatBox.removeChild(loadingMsg);
    activeThreadId = data.thread_id || activeThreadId;

    const finalMsg = createMessageBubble('bot', data.response, {
      messageId: data.bot_message_id,
      feedbackRating: data.feedback_rating || null,
    });
    if (data.thoughts) {
      appendThoughtsDropdown(finalMsg, data.thoughts);
    }
    await refreshConversationList();
  } catch (error) {
    chatBox.removeChild(loadingMsg);
    createMessageBubble('bot', '❌ Erro ao se comunicar com o servidor.');
  }
});

if (newChatBtn) {
  newChatBtn.addEventListener('click', async () => {
    await startNewConversation();
  });
}

if (sidebarChatToggle) {
  sidebarChatToggle.addEventListener('click', (event) => {
    const isChatPage = window.location.pathname === '/index' || window.location.pathname === '/';
    if (!isChatPage) {
      return;
    }
    event.preventDefault();
    const willOpen = !sidebarChatDropdown || !sidebarChatDropdown.classList.contains('open');
    setSidebarDropdownOpen(willOpen);
  });
}

document.addEventListener('click', (event) => {
  if (!sidebarChatItem || !sidebarChatDropdown || !sidebarChatDropdown.classList.contains('open')) return;
  if (sidebarChatItem.contains(event.target)) return;
  setSidebarDropdownOpen(false);
});

syncNavbarHeightVar();
window.addEventListener('resize', syncNavbarHeightVar);

document.addEventListener('DOMContentLoaded', async () => {
  syncNavbarHeightVar();
  setTimeout(syncNavbarHeightVar, 250);
  await refreshConversationList();
  await loadConversation();
  setSidebarDropdownOpen(true);
});
