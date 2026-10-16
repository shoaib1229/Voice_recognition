(() => {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('message-input');
  const messages = document.getElementById('messages');
  const welcome = document.getElementById('welcome');
  const status = document.getElementById('status');
  const micButton = document.getElementById('mic-button');
  let recognition = null;
  let listening = false;

  function setStatus(message, kind = '') {
    status.textContent = message;
    status.className = `status ${kind}`.trim();
  }

  function addMessage(text, who, links = []) {
    welcome.hidden = true;
    const row = document.createElement('div');
    row.className = `message ${who}`;
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = who === 'user' ? 'You' : 'N';
    avatar.setAttribute('aria-hidden', 'true');
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    const body = document.createElement('span');
    body.textContent = text;
    bubble.append(body);
    for (const link of links) {
      const anchor = document.createElement('a');
      anchor.textContent = link.label;
      anchor.href = link.url;
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
      bubble.append(document.createElement('br'), anchor);
    }
    row.append(avatar, bubble);
    messages.append(row);
    messages.scrollTop = messages.scrollHeight;
  }

  function speak(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    window.speechSynthesis.speak(utterance);
  }

  async function sendMessage(rawText) {
    const message = rawText.trim();
    if (!message) return;
    input.value = '';
    input.style.height = 'auto';
    addMessage(message, 'user');
    setStatus('Nova is thinking…');
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ message })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Nova could not process that request.');
      addMessage(data.reply, 'assistant', Array.isArray(data.links) ? data.links : []);
      setStatus('Ready when you are');
      speak(data.reply);
    } catch (error) {
      setStatus(error.message || 'Connection error. Please try again.', 'error');
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  document.querySelectorAll('.suggestion').forEach((button) => {
    button.addEventListener('click', () => sendMessage(button.textContent));
  });

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    micButton.disabled = true;
    micButton.title = 'Speech recognition is unavailable in this browser. You can type instead.';
    micButton.setAttribute('aria-label', 'Speech recognition unavailable; type your message');
  } else {
    recognition = new Recognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      listening = true;
      micButton.setAttribute('aria-label', 'Stop voice input');
      setStatus('Listening… speak now', 'listening');
    };
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript;
      if (transcript) sendMessage(transcript);
    };
    recognition.onerror = (event) => {
      const messagesByError = {
        'not-allowed': 'Microphone permission was denied. Type your message instead.',
        'no-speech': 'No speech was detected. Please try again or type your message.',
        'network': 'Browser speech recognition needs a network connection. You can type instead.'
      };
      setStatus(messagesByError[event.error] || 'Voice input failed. You can type your message instead.', 'error');
    };
    recognition.onend = () => {
      listening = false;
      micButton.setAttribute('aria-label', 'Start voice input');
      if (status.classList.contains('listening')) setStatus('Ready when you are');
    };
    micButton.addEventListener('click', () => {
      if (listening) recognition.stop();
      else {
        try { recognition.start(); }
        catch { setStatus('Voice input could not start. Please type your message.', 'error'); }
      }
    });
  }
})();
