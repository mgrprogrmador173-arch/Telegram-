const fs = require('fs');
const path = require('path');
const https = require('https');
const { execFile } = require('child_process');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const googleTTS = require('google-tts-api');
const Groq = require('groq-sdk');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');

const groqKey = process.env.GROQ_API_KEY;
const chatModel = process.env.GROQ_CHAT_MODEL || 'llama-3.1-8b-instant';
const audioModel = process.env.GROQ_TRANSCRIBE_MODEL || 'whisper-large-v3-turbo';
const qrDir = process.env.QR_DIR || 'qr-code';
const phone = (process.env.WHATSAPP_PAIRING_NUMBER || '').replace(/\D/g, '');
const qrInterval = Number(process.env.QR_INTERVAL_SECONDS || 90);
const phoneDelay = Number(process.env.PHONE_AFTER_QR_DELAY_SECONDS || 30);
const ttsSpeed = process.env.TTS_SPEED || '1.5';
const proxy = process.env.WHATSAPP_PROXY_SERVER || '';

if (!groqKey) throw new Error('GROQ_API_KEY nao encontrada.');
fs.mkdirSync(qrDir, { recursive: true });
fs.mkdirSync('tmp-audio', { recursive: true });

const groq = new Groq({ apiKey: groqKey });
const memory = new Map();
let ready = false;
let qrCount = 0;
let phoneCount = 0;
let lastQrAt = 0;

const systemPrompt = 'Voce atende clientes da MGR Design Studio. Servicos: logomarca R$30, marketing digital R$30, video R$60, pacote completo R$90. Responda muito curto, em portugues brasileiro, de forma simpatica e profissional. Nao diga que e IA.';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function clean(t, n = 700) { return String(t || '').replace(/\s+/g, ' ').trim().slice(0, n); }
function addMem(id, line) { if (!memory.has(id)) memory.set(id, []); const h = memory.get(id); h.push(line); if (h.length > 10) h.shift(); }
function exec(cmd, args) { return new Promise((res, rej) => execFile(cmd, args, e => e ? rej(e) : res())); }
function download(url, out) { return new Promise((res, rej) => { const f = fs.createWriteStream(out); https.get(url, r => { if (r.statusCode !== 200) return rej(new Error('download falhou')); r.pipe(f); f.on('finish', () => f.close(res)); }).on('error', rej); }); }

async function answer(id, text) {
  addMem(id, `Cliente: ${text}`);
  const history = memory.get(id).join('\n');
  const r = await groq.chat.completions.create({
    model: chatModel,
    temperature: 0.5,
    max_tokens: 180,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: `Historico:\n${history}\n\nResponda como atendente da MGR Design Studio.` }
    ]
  });
  const out = clean(r.choices?.[0]?.message?.content || 'Certo. Me passa mais detalhes para eu te ajudar melhor.');
  addMem(id, `MGR: ${out}`);
  return out;
}

async function transcribe(file) {
  const r = await groq.audio.transcriptions.create({ file: fs.createReadStream(file), model: audioModel, language: 'pt', response_format: 'text' });
  return clean(typeof r === 'string' ? r : r.text, 1000);
}

async function voice(text) {
  const stamp = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const mp3 = path.join('tmp-audio', `${stamp}.mp3`);
  const ogg = path.join('tmp-audio', `${stamp}.ogg`);
  const url = googleTTS.getAudioUrl(clean(text, 650), { lang: 'pt-BR', slow: false, host: 'https://translate.google.com' });
  await download(url, mp3);
  await exec('ffmpeg', ['-y', '-i', mp3, '-filter:a', `atempo=${ttsSpeed}`, '-c:a', 'libopus', ogg]);
  fs.rmSync(mp3, { force: true });
  return ogg;
}

async function saveQr(qr) {
  qrCount += 1;
  const n = String(qrCount).padStart(3, '0');
  await QRCode.toFile(path.join(qrDir, `qr-${n}.png`), qr, { type: 'png', margin: 2, width: 900 });
  await QRCode.toFile(path.join(qrDir, 'qr-latest.png'), qr, { type: 'png', margin: 2, width: 900 });
  fs.writeFileSync(path.join(qrDir, 'qr-updated.txt'), new Date().toISOString(), 'utf8');
  console.log(`QR ${n} salvo.`);
  qrcode.generate(qr, { small: true });
}

async function tryPhone() {
  if (!phone || ready) return;
  phoneCount += 1;
  try {
    const code = await client.requestPairingCode(phone);
    fs.writeFileSync(path.join(qrDir, 'pairing-code-latest.txt'), code, 'utf8');
    console.log('CODIGO PARA CONECTAR COM NUMERO:');
    console.log(code);
  } catch (e) { console.log('Tentativa por numero falhou:', e.message || e); }
}

const args = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--lang=pt-BR,pt'];
if (proxy) args.push(`--proxy-server=${proxy}`);
const client = new Client({ authStrategy: new LocalAuth({ clientId: 'mgr-whatsapp-webjs' }), puppeteer: { headless: true, args } });

client.on('qr', async qr => {
  if (ready) return;
  const now = Date.now();
  if (lastQrAt && (now - lastQrAt) / 1000 < qrInterval) return;
  lastQrAt = now;
  await saveQr(qr);
  await sleep(phoneDelay * 1000);
  await tryPhone();
});

client.on('ready', () => { ready = true; console.log('Bot conectado com Groq e audio.'); });

client.on('message', async msg => {
  try {
    if (msg.hasMedia) {
      const media = await msg.downloadMedia();
      if (media?.mimetype?.startsWith('audio/')) {
        const file = path.join('tmp-audio', `${Date.now()}.ogg`);
        fs.writeFileSync(file, Buffer.from(media.data, 'base64'));
        const text = await transcribe(file);
        fs.rmSync(file, { force: true });
        const reply = await answer(msg.from, text);
        try {
          const out = await voice(reply);
          await client.sendMessage(msg.from, MessageMedia.fromFilePath(out), { sendAudioAsVoice: true });
          fs.rmSync(out, { force: true });
        } catch { await msg.reply(reply); }
        return;
      }
    }
    const text = (msg.body || '').trim();
    if (!text) return;
    if (text.toLowerCase() === '/reset') { memory.delete(msg.from); await msg.reply('Memoria apagada. Qual servico voce precisa?'); return; }
    await msg.reply(await answer(msg.from, text));
  } catch (e) { console.error(e); await msg.reply('Tive um problema para responder agora. Tente novamente em instantes.'); }
});

client.initialize();
