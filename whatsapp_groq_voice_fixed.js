const fs = require('fs');
const path = require('path');
const https = require('https');
const { execFile } = require('child_process');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const googleTTS = require('google-tts-api');
const Groq = require('groq-sdk');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const { saveChatMessage } = require('./chat_history');

const GROQ_API_KEY = process.env.GROQ_API_KEY;
const CHAT_MODEL = process.env.GROQ_CHAT_MODEL || 'llama-3.1-8b-instant';
const AUDIO_MODEL = process.env.GROQ_TRANSCRIBE_MODEL || 'whisper-large-v3-turbo';
const QR_DIR = process.env.QR_DIR || 'qr-code';
const PHONE = (process.env.WHATSAPP_PAIRING_NUMBER || '').replace(/\D/g, '');
const QR_INTERVAL_SECONDS = Number(process.env.QR_INTERVAL_SECONDS || 90);
const PHONE_AFTER_QR_DELAY_SECONDS = Number(process.env.PHONE_AFTER_QR_DELAY_SECONDS || 30);
const TTS_SPEED = process.env.TTS_SPEED || '1.5';
const PROXY = process.env.WHATSAPP_PROXY_SERVER || '';

if (!GROQ_API_KEY) throw new Error('GROQ_API_KEY nao encontrada.');

fs.mkdirSync(QR_DIR, { recursive: true });
fs.mkdirSync('tmp-audio', { recursive: true });

const groq = new Groq({ apiKey: GROQ_API_KEY });
const memory = new Map();
const handled = new Set();
let ready = false;
let qrCount = 0;
let lastQrAt = 0;

const systemPrompt = 'Voce atende clientes da MGR Design Studio. Servicos: logomarca R$30, marketing digital R$30, video R$60, pacote completo R$90. Responda muito curto, em portugues brasileiro, de forma simpatica e profissional. Nao diga que e IA. Nao use emojis.';

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function clean(text, limit = 700) { return String(text || '').replace(/\s+/g, ' ').trim().slice(0, limit); }
function addMemory(id, line) { if (!memory.has(id)) memory.set(id, []); const h = memory.get(id); h.push(line); if (h.length > 10) h.shift(); }
function run(cmd, args) { return new Promise((resolve, reject) => execFile(cmd, args, err => err ? reject(err) : resolve())); }
function idOf(msg) { return msg?.id?._serialized || msg?.id?.id || `${msg.from}-${msg.timestamp}-${msg.body || ''}`; }
function shouldHandle(msg) { const id = idOf(msg); if (handled.has(id)) return false; handled.add(id); if (handled.size > 500) handled.clear(); return true; }

function download(url, out) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(out);
    https.get(url, response => {
      if (response.statusCode !== 200) return reject(new Error('download falhou'));
      response.pipe(file);
      file.on('finish', () => file.close(resolve));
    }).on('error', reject);
  });
}

async function makeAnswer(userId, text) {
  const input = clean(text, 1000);
  saveChatMessage({ userId, direction: 'in', type: 'text', text: input });
  addMemory(userId, `Cliente: ${input}`);
  const history = memory.get(userId).join('\n');
  console.log('Mensagem recebida:', input);

  const result = await groq.chat.completions.create({
    model: CHAT_MODEL,
    temperature: 0.5,
    max_tokens: 180,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: `Historico:\n${history}\n\nResponda como atendente da MGR Design Studio.` }
    ]
  });

  const output = clean(result.choices?.[0]?.message?.content || 'Certo. Me passa mais detalhes para eu te ajudar melhor.');
  addMemory(userId, `MGR: ${output}`);
  saveChatMessage({ userId, direction: 'out', type: 'text', text: output });
  console.log('Resposta gerada:', output);
  return output;
}

async function transcribeAudio(filePath) {
  const result = await groq.audio.transcriptions.create({
    file: fs.createReadStream(filePath),
    model: AUDIO_MODEL,
    language: 'pt',
    response_format: 'text'
  });
  return clean(typeof result === 'string' ? result : result.text, 1000);
}

async function makeVoice(text) {
  const stamp = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const mp3 = path.join('tmp-audio', `${stamp}.mp3`);
  const ogg = path.join('tmp-audio', `${stamp}.ogg`);
  const url = googleTTS.getAudioUrl(clean(text, 650), { lang: 'pt-BR', slow: false, host: 'https://translate.google.com' });
  await download(url, mp3);
  await run('ffmpeg', ['-y', '-i', mp3, '-filter:a', `atempo=${TTS_SPEED}`, '-c:a', 'libopus', ogg]);
  fs.rmSync(mp3, { force: true });
  return ogg;
}

async function saveQr(qr) {
  qrCount += 1;
  const n = String(qrCount).padStart(3, '0');
  await QRCode.toFile(path.join(QR_DIR, `qr-${n}.png`), qr, { type: 'png', margin: 2, width: 900 });
  await QRCode.toFile(path.join(QR_DIR, 'qr-latest.png'), qr, { type: 'png', margin: 2, width: 900 });
  fs.writeFileSync(path.join(QR_DIR, 'qr-updated.txt'), new Date().toISOString(), 'utf8');
  console.log(`QR ${n} salvo.`);
  qrcode.generate(qr, { small: true });
}

async function tryPhoneCode() {
  if (!PHONE || ready) return;
  try {
    const code = await client.requestPairingCode(PHONE);
    fs.writeFileSync(path.join(QR_DIR, 'pairing-code-latest.txt'), code, 'utf8');
    console.log('CODIGO PARA CONECTAR COM NUMERO:');
    console.log(code);
  } catch (error) {
    console.log('Tentativa por numero falhou:', error.message || error);
  }
}

async function handleMessage(msg, eventName) {
  if (!shouldHandle(msg)) return;
  if (msg.fromMe) { console.log(`Ignorando mensagem propria em ${eventName}.`); return; }

  try {
    console.log(`Evento ${eventName} recebido de ${msg.from}.`);

    if (msg.hasMedia) {
      const media = await msg.downloadMedia();
      if (media?.mimetype?.startsWith('audio/')) {
        const audioPath = path.join('tmp-audio', `${Date.now()}.ogg`);
        fs.writeFileSync(audioPath, Buffer.from(media.data, 'base64'));
        const text = await transcribeAudio(audioPath);
        fs.rmSync(audioPath, { force: true });
        if (!text) return await msg.reply('Nao consegui entender o audio. Pode mandar em texto?');

        const reply = await makeAnswer(msg.from, text);
        try {
          const voicePath = await makeVoice(reply);
          await client.sendMessage(msg.from, MessageMedia.fromFilePath(voicePath), { sendAudioAsVoice: true });
          fs.rmSync(voicePath, { force: true });
          console.log('Resposta por voz enviada.');
        } catch (error) {
          console.log('Falha na voz, enviando texto:', error.message || error);
          await msg.reply(reply);
        }
        return;
      }
    }

    const text = clean(msg.body || '', 1000);
    if (!text) return;
    if (text.toLowerCase() === '/reset') {
      memory.delete(msg.from);
      await msg.reply('Memoria apagada. Qual servico voce precisa?');
      return;
    }

    const reply = await makeAnswer(msg.from, text);
    await msg.reply(reply);
    console.log('Resposta em texto enviada.');
  } catch (error) {
    console.error('Erro ao responder:', error.message || error);
    try { await msg.reply('Tive um problema para responder agora. Tente novamente em instantes.'); } catch (_) {}
  }
}

const args = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--lang=pt-BR,pt'];
if (PROXY) args.push(`--proxy-server=${PROXY}`);

const client = new Client({
  authStrategy: new LocalAuth({ clientId: 'mgr-whatsapp-webjs' }),
  puppeteer: { headless: true, args }
});

client.on('qr', async qr => {
  if (ready) return;
  const now = Date.now();
  if (lastQrAt && (now - lastQrAt) / 1000 < QR_INTERVAL_SECONDS) return;
  lastQrAt = now;
  await saveQr(qr);
  await sleep(PHONE_AFTER_QR_DELAY_SECONDS * 1000);
  await tryPhoneCode();
});

client.on('authenticated', () => {
  fs.writeFileSync(path.join(QR_DIR, 'connected.txt'), new Date().toISOString(), 'utf8');
  console.log('WhatsApp autenticado.');
});

client.on('ready', () => {
  ready = true;
  fs.writeFileSync(path.join(QR_DIR, 'connected.txt'), new Date().toISOString(), 'utf8');
  console.log('Bot conectado com Groq e audio.');
});

client.on('message', msg => handleMessage(msg, 'message'));
client.on('message_create', msg => handleMessage(msg, 'message_create'));

client.initialize();
