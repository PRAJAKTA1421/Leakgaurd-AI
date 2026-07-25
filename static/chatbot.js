(() => {
  const launcher = document.querySelector('#chat-launcher'), panel = document.querySelector('#chat-panel'), closeButton = document.querySelector('#chat-close'), form = document.querySelector('#chat-form'), input = document.querySelector('#chat-input'), messagesElement = document.querySelector('#chat-messages');
  if (!launcher || !panel || !form || !input || !messagesElement) return;
  const messages = [];
  const setOpen = (open) => { panel.hidden = !open; launcher.setAttribute('aria-expanded', String(open)); if (open) input.focus(); };
  const addMessage = (content, role, isError = false) => { const message = document.createElement('div'); message.className = `chat-message ${isError ? 'error' : role}`; message.textContent = content; messagesElement.append(message); messagesElement.scrollTop = messagesElement.scrollHeight; };
  launcher.addEventListener('click', () => setOpen(panel.hidden));
  closeButton.addEventListener('click', () => setOpen(false));
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); const content = input.value.trim(); if (!content) return;
    messages.push({ role: 'user', content }); addMessage(content, 'user'); input.value = '';
    const submit = form.querySelector('button'); submit.disabled = true;
    try {
      const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Unable to send your message.');
      messages.push({ role: 'assistant', content: data.reply }); addMessage(data.reply, 'assistant');
    } catch (error) { addMessage(error.message || 'The assistant is unavailable. Please try again.', 'assistant', true); }
    finally { submit.disabled = false; input.focus(); }
  });
})();
