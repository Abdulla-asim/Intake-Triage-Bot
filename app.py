from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from intake_triage_agent import IntakeTriageAgent

app = FastAPI(title="Intake Triage Bot")
agent = IntakeTriageAgent()

HOME_PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Intake Triage Bot</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f4f6f9; color: #111; }
    .page { max-width: 780px; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.9rem; font-weight: 700; margin-bottom: 0.35rem; }
    .subtitle { margin-bottom: 1.5rem; color: #555; line-height: 1.7; }
    .chat-window { background: #fff; border: 1px solid #d9dde4; border-radius: 20px; box-shadow: 0 14px 40px rgba(16, 24, 40, 0.05); display: flex; flex-direction: column; min-height: 520px; }
    .messages { flex: 1; padding: 1.25rem; display: flex; flex-direction: column; gap: 0.9rem; overflow-y: auto; }
    .message { max-width: 74%; padding: 0.95rem 1rem; border-radius: 20px; line-height: 1.55; position: relative; white-space: pre-wrap; word-break: break-word; }
    .message.bot { align-self: flex-start; background: #eef4ff; color: #111; border-bottom-left-radius: 6px; }
    .message.user { align-self: flex-end; background: #111; color: #fff; border-bottom-right-radius: 6px; }
    .message.meta { align-self: stretch; background: #f6f7fb; color: #555; font-size: 0.86rem; padding: 0.75rem 1rem; border-radius: 16px; }
    .summary-box { background: #fff; border: 1px solid #d2d8e2; border-radius: 16px; padding: 1rem; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.03); }
    .summary-title { font-weight: 700; margin-bottom: 0.7rem; }
    .footer { display: grid; grid-template-columns: 1fr auto; gap: 0.85rem; padding: 1rem 1.25rem 1.25rem; border-top: 1px solid #e3e7ed; }
    .footer-left { display: flex; flex-direction: column; gap: 0.75rem; }
    .api-key-input { width: 100%; border-radius: 16px; border: 1px solid #c8d0db; padding: 12px 14px; font-size: 0.9rem; line-height: 1.4; font-family: inherit; }
    .api-key-input:focus { outline: none; border-color: #7b8aff; box-shadow: 0 0 0 4px rgba(123, 138, 255, 0.12); }
    textarea { width: 100%; min-height: 78px; border-radius: 16px; border: 1px solid #c8d0db; padding: 14px 16px; font-size: 0.95rem; line-height: 1.5; resize: vertical; font-family: inherit; }
    textarea:focus { outline: none; border-color: #7b8aff; box-shadow: 0 0 0 4px rgba(123, 138, 255, 0.12); }
    button { border: none; border-radius: 16px; padding: 0.95rem 1.3rem; font-size: 0.95rem; font-weight: 700; cursor: pointer; }
    .send { background: #111; color: #fff; }
    .send:disabled { background: #9a9a9a; cursor: not-allowed; }
    .spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.55); border-top-color: #fff; border-radius: 50%; animation: spin 0.75s linear infinite; display: inline-block; vertical-align: middle; margin-left: 0.5rem; }
    .spinner.hidden { display: none; }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div class="page">
    <h1>Intake Triage Bot</h1>
    <p class="subtitle">Chat with the intake agent like a real assistant. Paste your request, answer follow-up questions, and get automated ticket escalation.</p>

    <div class="chat-window">
      <div class="messages" id="messages">
        <div class="message bot">Hi there! Paste the incoming request below and I’ll start triaging it.</div>
      </div>
      <div class="footer">
        <div class="footer-left">
          <input id="api-key-input" class="api-key-input" type="password" placeholder="Paste API key (optional)" autocomplete="off" />
          <textarea id="message-input" placeholder="Type your request or answer the agent’s question..." rows="3"></textarea>
        </div>
        <button id="send-btn" class="send">Send</button>
      </div>
    </div>
  </div>

  <script>
    const messagesEl = document.getElementById('messages');
    const inputEl = document.getElementById('message-input');
    const apiKeyEl = document.getElementById('api-key-input');
    const sendBtn = document.getElementById('send-btn');
    let rawRequest = '';
    let followUpAnswers = [];
    let apiKey = localStorage.getItem('apiKey') || '';
    let waiting = false;

    if (apiKey) {
      apiKeyEl.value = apiKey;
    }

    apiKeyEl.addEventListener('input', () => {
      apiKey = apiKeyEl.value.trim();
      if (apiKey) {
        localStorage.setItem('apiKey', apiKey);
      } else {
        localStorage.removeItem('apiKey');
      }
    });

    function appendMessage(text, role) {
      const msg = document.createElement('div');
      msg.className = 'message ' + role;
      msg.textContent = text;
      messagesEl.appendChild(msg);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function escapeHtml(text) {
      return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function renderMarkdown(text) {
      let html = escapeHtml(text);
      html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
      html = html.replace(/^\s*-\s+(.+)$/gm, '<li>$1</li>');
      html = html.replace(/(<li>[\s\S]*?<\/li>)/g, (match) => {
        return '<ul>' + match.replace(/\n/g, '') + '</ul>';
      });
      html = html.replace(/\n{2,}/g, '</p><p>');
      html = html.replace(/\n/g, '<br>');
      return '<p>' + html + '</p>';
    }

    function appendSummary(summary) {
      const wrapper = document.createElement('div');
      wrapper.className = 'message bot';
      const title = document.createElement('div');
      title.className = 'summary-title';
      title.textContent = 'Final intake summary';
      const box = document.createElement('div');
      box.className = 'summary-box';
      box.innerHTML = renderMarkdown(summary);
      wrapper.appendChild(title);
      wrapper.appendChild(box);
      messagesEl.appendChild(wrapper);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function appendMeta(text) {
      const meta = document.createElement('div');
      meta.className = 'message meta';
      meta.textContent = text;
      messagesEl.appendChild(meta);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    async function sendMessage() {
      const text = inputEl.value.trim();
      if (!text || waiting) return;

      if (!rawRequest) {
        rawRequest = text;
      } else {
        followUpAnswers.push(text);
      }
      appendMessage(text, 'user');
      inputEl.value = '';
      sendBtn.disabled = true;
      waiting = true;
      const spinner = document.createElement('span');
      spinner.className = 'spinner';
      sendBtn.appendChild(spinner);

      try {
        const response = await fetch('/api/triage', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ raw_request: rawRequest, follow_up_answers: followUpAnswers, api_key: apiKey || undefined }),
        });
        const result = await response.json();

        if (result.follow_up_question) {
          appendMessage(result.follow_up_question, 'bot');
          appendMeta('Reply to the bot with the missing detail to continue triage.');
        } else {
          appendSummary(result.ticket_summary || 'No ticket summary available.');
          const routeText = result.route ? 'Routed to: ' + result.route : 'No route assigned.';
          appendMeta(routeText + (result.escalate ? ' (Escalated)' : ''));
          if (result.escalation_reason) appendMeta('Escalation reason: ' + result.escalation_reason);
          rawRequest = '';
          followUpAnswers = [];
        }
      } catch (err) {
        appendMessage('Sorry, something went wrong. Please try again.', 'bot');
        appendMeta(err.message || 'Network or server error.');
      } finally {
        sendBtn.removeChild(spinner);
        sendBtn.disabled = false;
        waiting = false;
      }
    }

    sendBtn.addEventListener('click', sendMessage);
    inputEl.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });
  </script>
</body>
</html>'''

class TriageRequest(BaseModel):
    raw_request: str
    api_key: str | None = None
    follow_up_answer: str | None = None
    follow_up_answers: list[str] | None = None


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return HTMLResponse(HOME_PAGE)


@app.post("/api/triage")
async def triage(request: TriageRequest) -> dict:
    if request.follow_up_answers is not None:
        return agent.process(request.raw_request, request.follow_up_answers, api_key=request.api_key)
    if request.follow_up_answer:
        return agent.process(request.raw_request, [request.follow_up_answer], api_key=request.api_key)
    return agent.process(request.raw_request, [], api_key=request.api_key)
