const fs = require('fs');
const path = require('path');
const https = require('https');
const { execFile } = require('child_process');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const googleTTS = require('google-tts-api');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const { GoogleGenAI } = require('@google/genai');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GOOGLE_AI_MODEL = process.env.GOOGLE_AI_MODEL || 'gemini-2.5-flash-lite';
const QR_DIR = process.env.QR_DIR || 'qr-code';
const PHONE = (process.env.WHATSAPP_PAIRING_NUMBER || '').replace(/\D/g, '');
const QR_INTERVAL_SECONDS = Number(process.env.QR_INTERVAL_SECONDS || 90);
const PHONE_AFTER_QR_DELAY_SECONDS = Number(process.env.PHONE_AFTER_QR_DELAY_SECONDS || 30);
const TTS_SPEED = process.env.TTS_SPEED || '1.5';
const WHATSAPP_PROXY_SERVER = process.env.WHATSAPP_PROXY_SERVER || '';

if (!GEMINI_API_KEY) throw new Error('GEMINI_API_KEY nao encontrada.');
fs.mkdirSync(QR_DIR, { recursive: true });
fs.mkdirSync('tmp-audio', { recursive: true });

const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY });
const memory = new Map();
let ready = false;
let qrCount = 0;
let phoneCount = 0;
let lastQrAt = 0;

const SYSTEM = `Voce atende clientes da MGR Design Studio. Servicos: logomarca R$30, marketing digital R$30, video R$60, pacote completo R$90. Responda muito curto, em portugues brasileiro, de forma simpatica e profissional. Nao diga que e IA.`;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function addMemory(id, line) {
  if (!memory.has(id)) memory.set(id, []);
  const h = memory.get(id);
  h.push(line);
  if (h.length > 10) h.shift();
}

function safeText(text, limit = 700) {
  return String(text || '').replace(/\s+/g, ' ').trim().slice(0, limit);
}

function runCommand(cmd, args) {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, (error) => {
      if (error) reject(error);
      else resolve();
    });
  });
}

function downloadFile(url, outputPath) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(outputPath);
    https.get(url, (response) => {
      if (response.statusCode !== 200) {
        reject(new Error(`Download falhou: ${response.statusCode}`));
        return;
      }
      response.pipe(file);
      file.on('finish', () => file.close(resolve));
    }).on('error', reject);
  });
}

async function answer(id, text) {
  addMemory(id, `Cliente: ${text}`);
  const history = memory.get(id).join('\n');
  const response = await ai.models.generateContent({
    model: GOOGLE_AI_MODEL,
    contents: `${SYSTEM}\n\n${history}\n\nResponda como atendente da MGR Design Studio.`,
  });
  const out = safeText(response.text || 'Certo. Me passa mais detalhes para eu te ajudar melhor.');
  addMemory(id, `MGR: ${out}`);
  return out;
}

async function transcribeAudio(filePath, mimeType = 'audio/ogg') {
  const audioBase64 = fs.readFileSync(filePath).toString('base64');
  const response = await ai.models.generateContent({
    model: GOOGLE_AI_MODEL,
    contents: [
      { text: 'Transcreva este audio em portugues brasileiro. Responda somente com o texto transcrito.' },
      { inlineData: { mimeType, data: audioBase64 } },
    ],
  });
  return safeText(response.text || '', 1000);
}

async function createVoice(text) {
  const clean = safeText(text, 650);
  const stamp = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const mp3 = path.join('tmp-audio', `${stamp}.mp3`);
  const ogg = path.join('tmp-audio', `${stamp}.ogg`);

  const url = googleTTS.getAudioUrl(clean, {
    lang: 'pt-BR',
    slow: false,
    host: 'https://translate.google.com',
  });

  await downloadFile(url, mp3);
  await runCommand('ffmpeg', ['-y', '-i', mp3, '-filter:a', `atempo=${TTS_SPEED}`, '-c:a', 'libopus', ogg]);
  fs.rmSync(mp3, { force: true });
  return ogg;
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

const puppeteerArgs = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--lang=pt-BR,pt'];
if (WHATSAPP_PROXY_SERVER) {
  puppeteerArgs.push(`--proxy-server=${WHATSAPP_PROXY_SERVER}`);
  console.log('Proxy configurado para o WhatsApp Web JS.');
}

const client = new Client({
  authStrategy: new LocalAuth({ clientId: 'mgr-whatsapp-webjs' }),
  puppeteer: { headless: true, args: puppeteerArgs },
});

client.on('qr', async (qr) => {
  if (ready) return;
  const now = Date.now();
  const elapsed = (now - lastQrAt) / 1000;
  if (lastQrAt && elapsed < QR_INTERVAL_SECONDS) {
    console.log(`QR ignorado. Faltam ${Math.ceil(QR_INTERVAL_SECONDS - elapsed)}s.`);
    return;
  }
  lastQrAt = now;
  await saveQr(qr);
  console.log(`Aguardando ${PHONE_AFTER_QR_DELAY_SECONDS}s antes de tentar por telefone...`);
  await sleep(PHONE_AFTER_QR_DELAY_SECONDS * 1000);
  await tryPhoneCode();
});

client.on('ready', () => {
  ready = true;
  console.log('Bot conectado e rodando com audio.');
});

client.on('message', async (msg) => {
  try {
    if (msg.hasMedia) {
      const media = await msg.downloadMedia();
      if (media && media.mimetype && media.mimetype.startsWith('audio/')) {
        const ext = media.mimetype.includes('mpeg') ? 'mp3' : 'ogg';
        const audioPath = path.join('tmp-audio', `${Date.now()}.${ext}`);
        fs.writeFileSync(audioPath, Buffer.from(media.data, 'base64'));

        const text = await transcribeAudio(audioPath, media.mimetype);
        fs.rmSync(audioPath, { force: true });

        if (!text) {
          await msg.reply('Nao consegui entender o audio. Pode mandar em texto?');
          return;
        }

        const reply = await answer(msg.from, text);
        try {
          const voicePath = await createVoice(reply);
          const voiceMedia = MessageMedia.fromFilePath(voicePath);
          await client.sendMessage(msg.from, voiceMedia, { sendAudioAsVoice: true });
          fs.rmSync(voicePath, { force: true });
        } catch (voiceError) {
          console.error('Erro ao gerar voz:', voiceError);
          await msg.reply(reply);
        }
        return;
      }
    }

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
