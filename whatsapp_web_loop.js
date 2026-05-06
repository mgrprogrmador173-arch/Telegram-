const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const { Client, LocalAuth } = require('whatsapp-web.js');
const { GoogleGenAI } = require('@google/genai');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GOOGLE_AI_MODEL = process.env.GOOGLE_AI_MODEL || 'gemini-2.5-flash-lite';
const QR_DIR = process.env.QR_DIR || 'qr-code';
const PHONE = (process.env.WHATSAPP_PAIRING_NUMBER || '').replace(/\D/g, '');
const QR_INTERVAL_SECONDS = Number(process.env.QR_INTERVAL_SECONDS || 60);
const WHATSAPP_PROXY_SERVER = process.env.WHATSAPP_PROXY_SERVER || '';

if (!GEMINI_API_KEY) throw new Error('GEMINI_API_KEY nao encontrada.');
fs.mkdirSync(QR_DIR, { recursive: true });

const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY });
const memory = new Map();
let ready = false;
let qrCount = 0;
let phoneCount = 0;
let lastQrAt = 0;

const SYSTEM = `Voce atende clientes da MGR Design Studio. Servicos: logomarca R$30, marketing digital R$30, video R$60, pacote completo R$90. Responda curto, em portugues, de forma simpatica e profissional.`;

function addMemory(id, line) {
  if (!memory.has(id)) memory.set(id, []);
  const h = memory.get(id);
  h.push(line);
  if (h.length > 10) h.shift();
}

async function answer(id, text) {
  addMemory(id, `Cliente: ${text}`);
  const history = memory.get(id).join('\n');
  const response = await ai.models.generateContent({
    model: GOOGLE_AI_MODEL,
    contents: `${SYSTEM}\n\n${history}\n\nResponda como atendente da MGR Design Studio.`,
  });
  const out = (response.text || 'Certo. Me passa mais detalhes para eu te ajudar melhor.').trim();
  addMemory(id, `MGR: ${out}`);
  return out;
}

async function saveQr(qr) {
  qrCount += 1;
  const n = String(qrCount).padStart(3, '0');
  const file = path.join(QR_DIR, `qr-${n}.png`);
  const latest = path.join(QR_DIR, 'qr-latest.png');
  await QRCode.toFile(file, qr, { type: 'png', margin: 2, width: 900 });
  await QRCode.toFile(latest, qr, { type: 'png', margin: 2, width: 900 });
  fs.writeFileSync(path.join(QR_DIR, 'qr-updated.txt'), new Date().toISOString(), 'utf8');
  console.log(`QR ${n} salvo: ${file}`);
  console.log('QR mais recente: qr-code/qr-latest.png');
  qrcode.generate(qr, { small: true });
}

async function tryPhoneCode() {
  if (!PHONE || ready) return;
  phoneCount += 1;
  try {
    console.log('============================================================');
    console.log(`TENTATIVA POR NUMERO ${phoneCount}`);
    console.log(`Numero terminado em ${PHONE.slice(-4)}`);
    const code = await client.requestPairingCode(PHONE);
    fs.writeFileSync(path.join(QR_DIR, `pairing-code-${phoneCount}.txt`), code, 'utf8');
    fs.writeFileSync(path.join(QR_DIR, 'pairing-code-latest.txt'), code, 'utf8');
    console.log('CODIGO PARA CONECTAR COM NUMERO:');
    console.log(code);
    console.log('============================================================');
  } catch (e) {
    console.log(`Tentativa por numero ${phoneCount} falhou.`);
    console.log(e && e.message ? e.message : e);
  }
}

const puppeteerArgs = [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-dev-shm-usage',
  '--disable-gpu',
  '--lang=pt-BR,pt',
];

if (WHATSAPP_PROXY_SERVER) {
  puppeteerArgs.push(`--proxy-server=${WHATSAPP_PROXY_SERVER}`);
  console.log('Proxy configurado para o WhatsApp Web JS.');
}

const client = new Client({
  authStrategy: new LocalAuth({ clientId: 'mgr-whatsapp-webjs' }),
  puppeteer: {
    headless: true,
    args: puppeteerArgs,
  },
});

client.on('qr', async (qr) => {
  if (ready) return;

  const now = Date.now();
  const elapsed = (now - lastQrAt) / 1000;
  if (lastQrAt && elapsed < QR_INTERVAL_SECONDS) {
    console.log(`QR ignorado. Aguardando intervalo de ${QR_INTERVAL_SECONDS}s. Faltam ${Math.ceil(QR_INTERVAL_SECONDS - elapsed)}s.`);
    return;
  }

  lastQrAt = now;
  await saveQr(qr);
  await tryPhoneCode();
  console.log(`Aguardando pelo menos ${QR_INTERVAL_SECONDS}s antes de aceitar outro QR...`);
});

client.on('ready', () => {
  ready = true;
  console.log('Bot conectado e rodando.');
});

client.on('message', async (msg) => {
  try {
    const text = (msg.body || '').trim();
    if (!text) return;
    if (text.toLowerCase() === '/reset') {
      memory.delete(msg.from);
      await msg.reply('Memoria apagada. Qual servico voce precisa?');
      return;
    }
    const reply = await answer(msg.from, text);
    await msg.reply(reply);
  } catch (e) {
    console.error(e);
    await msg.reply('Tive um problema para responder agora. Tente novamente em instantes.');
  }
});

client.initialize();
