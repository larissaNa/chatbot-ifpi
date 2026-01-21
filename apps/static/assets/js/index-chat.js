const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const chatBox = document.getElementById('chat-box');
const chatContainer = document.getElementById('chat-container');

const thoughtsIconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-lightbulb" viewBox="0 0 16 16" style="margin-right: 8px;">
  <path d="M2 6a6 6 0 1 1 10.174 4.31c-.203.196-.359.4-.453.619l-.762 1.769A.5.5 0 0 1 10.5 13a.5.5 0 0 1 0 1 .5.5 0 0 1 0 1l-.224.447a1 1 0 0 1-.894.553H6.618a1 1 0 0 1-.894-.553L5.5 15a.5.5 0 0 1 0-1 .5.5 0 0 1 0-1 .5.5 0 0 1 10.5-13a.5.5 0 0 1 0-1 .5.5 0 0 1 0 1 .5.5 0 0 1-.762-1.769C2.359 10.4 2.203 10.196 2 10.174 2 6zm4.95.243a.5.5 0 0 1 .5.5V6a.5.5 0 0 1-1 0v-.257a.5.5 0 0 1 .5-.5z"/>
</svg>`;

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
      const loader = document.createElement('div');
      loader.className = 'loader';
      bubble.appendChild(loader);
    } else {
      const md = window.markdownit({
        breaks: true,
        linkify: true,
      });
      const formattedText = md.render(text || '');
      bubble.innerHTML = formattedText;
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


document.addEventListener('DOMContentLoaded', async () => {
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
