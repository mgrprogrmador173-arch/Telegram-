const fs = require('fs');
const path = require('path');

const CHAT_HISTORY_DIR = process.env.CHAT_HISTORY_DIR || 'chat-history';
const CHAT_HISTORY_FILE = path.join(CHAT_HISTORY_DIR, 'conversations.jsonl');

function ensureDir() {
  fs.mkdirSync(CHAT_HISTORY_DIR, { recursive: true });
}

function safeText(value, limit = 4000) {
  return String(value || '').replace(/\s+/g, ' ').trim().slice(0, limit);
}

function saveChatMessage({ userId, direction, type, text }) {
  try {
    ensureDir();
    const entry = {
      timestamp: new Date().toISOString(),
      userId: String(userId || ''),
      direction: direction || 'unknown',
      type: type || 'text',
      text: safeText(text),
    };
    fs.appendFileSync(CHAT_HISTORY_FILE, JSON.stringify(entry) + '\n', 'utf8');
  } catch (error) {
    console.error('Erro ao salvar historico:', error && error.message ? error.message : error);
  }
}

module.exports = { saveChatMessage };
