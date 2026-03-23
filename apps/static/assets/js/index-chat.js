const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const chatBox = document.getElementById('chat-box');
const chatContainer = document.getElementById('chat-container');

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

const thoughtsIconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-lightbulb" viewBox="0 0 16 16" style="margin-right: 8px;">
  <path d="M2 6a6 6 0 1 1 10.174 4.31c-.203.196-.359.4-.453.619l-.762 1.769A.5.5 0 0 1 10.5 13a.5.5 0 0 1 0 1 .5.5 0 0 1 0 1l-.224.447a1 1 0 0 1-.894.553H6.618a1 1 0 0 1-.894-.553L5.5 15a.5.5 0 0 1 0-1 .5.5 0 0 1 0-1 .5.5 0 0 1 10.5-13a.5.5 0 0 1 0-1 .5.5 0 0 1 0 1 .5.5 0 0 1-.762-1.769C2.359 10.4 2.203 10.196 2 10.174 2 6zm4.95.243a.5.5 0 0 1 .5.5V6a.5.5 0 0 1-1 0v-.257a.5.5 0 0 1 .5-.5z"/>
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

function createMessageBubble(sender, text, isLoading = false) {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const isUser = sender === 'user';

    const message = document.createElement('div');
    message.className = `chat-message ${isUser ? 'user' : 'bot'}`;

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

    return message;
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

  if (chatContainer.classList.contains('initial-state')) {
      chatContainer.classList.remove('initial-state');
  }

  createMessageBubble('user', userText);
  input.value = "";

  const loadingMsg = createMessageBubble('bot', '', true);

  try {
    const res = await fetch('/chatbot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText })
    });

    const data = await res.json();
    chatBox.removeChild(loadingMsg);

    const finalMsg = createMessageBubble('bot', data.response);
    if (data.thoughts) {
      appendThoughtsDropdown(finalMsg, data.thoughts);
    }
  } catch (error) {
    chatBox.removeChild(loadingMsg);
    createMessageBubble('bot', '❌ Erro ao se comunicar com o servidor.');
  }
});


syncNavbarHeightVar();
window.addEventListener('resize', syncNavbarHeightVar);

document.addEventListener('DOMContentLoaded', async () => {
  syncNavbarHeightVar();
  setTimeout(syncNavbarHeightVar, 250);
  try {
    const res = await fetch('/chatbot', { method: 'GET' });
    if (!res.ok) return;

    const data = await res.json();
    if (!data.messages || !Array.isArray(data.messages) || data.messages.length === 0) {
      return;
    }

    if (chatContainer.classList.contains('initial-state')) {
      chatContainer.classList.remove('initial-state');
    }

    data.messages.forEach((msg) => {
      const sender = msg.sender === 'bot' ? 'bot' : 'user';
      const messageElement = createMessageBubble(sender, msg.content || '');
      if (sender === 'bot' && msg.thoughts) {
        appendThoughtsDropdown(messageElement, msg.thoughts);
      }
    });
  } catch (error) {
  }
});
