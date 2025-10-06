const form = document.getElementById('chat-form');
  const input = document.getElementById('user-input');
  const chatBox = document.getElementById('chat-box');

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
      const spinner = document.createElement('div');
      spinner.className = 'spinner';
      bubble.appendChild(spinner);
      bubble.appendChild(document.createTextNode(' Digitando...'));
    } else {
      const md = window.markdownit({
      breaks: true, // respeita quebras de linha
      linkify: true, // transforma URLs em links
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

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const userText = input.value.trim();
    if (!userText) return;

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
      createMessageBubble('bot', data.response);
    } catch (error) {
      chatBox.removeChild(loadingMsg);
      createMessageBubble('bot', '❌ Erro ao se comunicar com o servidor.');
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
  // Mensagem inicial do bot
  createMessageBubble('bot', 'Olá, sou o piazinho, em que posso lhe ajudar hoje?');
});