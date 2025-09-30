const form = document.getElementById('chat-form');
  const input = document.getElementById('user-input');
  const chatBox = document.getElementById('chat-box');
  const sendBtn = document.getElementById('send-btn');
  const sendIcon = document.getElementById('send-icon');

  function setSendingState(isSending) {
    if (isSending) {
      sendBtn.setAttribute('disabled', 'true');
      input.setAttribute('disabled', 'true');
      sendIcon.style.opacity = '0.35';
      sendBtn.style.cursor = 'not-allowed';
    } else {
      sendBtn.removeAttribute('disabled');
      input.removeAttribute('disabled');
      sendIcon.style.opacity = '1';
      sendBtn.style.cursor = 'pointer';
      input.focus();
    }
  }

  function escapeHtml(unsafe) {
    return unsafe
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function renderMessageText(rawText) {
    let text = escapeHtml(rawText);
    text = text.replace(/```([\s\S]*?)```/g, function(_, code) {
      return '<pre><code>' + code + '</code></pre>';
    });
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/(https?:\/\/[^\s<]+[^<.,;:!?)"\]\s])/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    text = text.split('\n\n').map(p => '<p>' + p.replaceAll('\n', '<br>') + '</p>').join('');
    return text;
  }

  function createMessageBubble(sender, text, isLoading = false) {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const isUser = sender === 'user';

    const message = document.createElement('div');
    message.className = `chat-message ${isUser ? 'user' : 'bot'}`;

    const avatar = document.createElement('img');
    avatar.className = 'chat-avatar';
    const botAvatar = (typeof window !== 'undefined' && window.BOT_AVATAR_URL) ? window.BOT_AVATAR_URL : '/static/assets/images/ifpia_logo.png';
    avatar.src = isUser
      ? 'https://cdn-icons-png.flaticon.com/512/9131/9131529.png'
      : botAvatar;

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';

    if (isLoading) {
      const spinner = document.createElement('div');
      spinner.className = 'spinner';
      bubble.appendChild(spinner);
      bubble.appendChild(document.createTextNode(' Digitando...'));
    } else {
      bubble.innerHTML = renderMessageText(text);
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

  // Enter to send, Shift+Enter for newline
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  // Welcome message
  window.addEventListener('DOMContentLoaded', () => {
    createMessageBubble('bot', 'Olá! Eu sou o Piazinho. Como posso ajudar você hoje?');
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const userText = input.value.trim();
    if (!userText) return;

    createMessageBubble('user', userText);
    input.value = "";
    setSendingState(true);
    const loadingMsg = createMessageBubble('bot', '', true);

    try {
      const res = await fetch('/chatbot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userText })
      });

      const data = await res.json();
      chatBox.removeChild(loadingMsg);
      if (data && typeof data.response === 'string') {
        createMessageBubble('bot', data.response);
      } else {
        createMessageBubble('bot', '❕ Resposta inesperada do servidor.');
      }
    } catch (error) {
      chatBox.removeChild(loadingMsg);
      createMessageBubble('bot', '❌ Erro ao se comunicar com o servidor. Tente novamente.');
    }
    setSendingState(false);
  });