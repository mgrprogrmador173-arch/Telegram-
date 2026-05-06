from pathlib import Path

p = Path('whatsapp_groq_voice_fixed.js')
s = p.read_text()

# Add phone interval variable if missing
if "PHONE_CODE_INTERVAL_SECONDS" not in s:
    s = s.replace(
        "const PHONE_AFTER_QR_DELAY_SECONDS = Number(process.env.PHONE_AFTER_QR_DELAY_SECONDS || 30);",
        "const PHONE_AFTER_QR_DELAY_SECONDS = Number(process.env.PHONE_AFTER_QR_DELAY_SECONDS || 5);\nconst PHONE_CODE_INTERVAL_SECONDS = Number(process.env.PHONE_CODE_INTERVAL_SECONDS || 75);"
    )

# Add last phone attempt control if missing
if "let lastPhoneCodeAt = 0;" not in s:
    s = s.replace("let lastQrAt = 0;", "let lastQrAt = 0;\nlet lastPhoneCodeAt = 0;")

# Make phone code throttled and visible
old = """async function tryPhoneCode() {
  if (!PHONE || ready) return;
  try {
    const code = await client.requestPairingCode(PHONE);
    fs.writeFileSync(path.join(QR_DIR, 'pairing-code-latest.txt'), code, 'utf8');
    console.log('CODIGO PARA CONECTAR COM NUMERO:');
    console.log(code);
  } catch (error) {
    console.log('Tentativa por numero falhou:', error.message || error);
  }
}"""

new = """async function tryPhoneCode() {
  if (ready) return;

  if (!PHONE) {
    console.log('WHATSAPP_PAIRING_NUMBER nao configurado. Configure o numero para login por telefone.');
    return;
  }

  const now = Date.now();
  const elapsed = (now - lastPhoneCodeAt) / 1000;
  if (lastPhoneCodeAt && elapsed < PHONE_CODE_INTERVAL_SECONDS) {
    console.log(`Aguardando novo codigo por telefone. Faltam ${Math.ceil(PHONE_CODE_INTERVAL_SECONDS - elapsed)}s.`);
    return;
  }

  lastPhoneCodeAt = now;

  try {
    console.log('============================================================');
    console.log('MODO TELEFONE ATIVO. Gerando codigo por numero.');
    console.log(`Numero terminado em ${PHONE.slice(-4)}.`);
    const code = await client.requestPairingCode(PHONE);
    fs.writeFileSync(path.join(QR_DIR, 'pairing-code-latest.txt'), code, 'utf8');
    fs.writeFileSync(path.join(QR_DIR, 'pairing-code-updated.txt'), new Date().toISOString(), 'utf8');
    console.log('CODIGO PARA CONECTAR COM NUMERO:');
    console.log(code);
    console.log('Use no WhatsApp: Aparelhos conectados > Conectar aparelho > Conectar com numero de telefone.');
    console.log('============================================================');
  } catch (error) {
    console.log('Tentativa por numero falhou:', error.message || error);
  }
}"""

if old in s:
    s = s.replace(old, new)

# Disable QR saving and force phone pairing attempt
start = s.find("client.on('qr', async qr => {")
end = s.find("\n\nclient.on('authenticated'", start)
if start != -1 and end != -1:
    replacement = """client.on('qr', async () => {
  if (ready) return;
  console.log('WhatsApp solicitou QR, mas o modo QR esta desativado. Tentando login por numero.');
  await sleep(PHONE_AFTER_QR_DELAY_SECONDS * 1000);
  await tryPhoneCode();
});"""
    s = s[:start] + replacement + s[end:]

p.write_text(s)
print('Modo telefone sem QR aplicado.')
