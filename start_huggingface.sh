#!/usr/bin/env bash
set -e

mkdir -p qr-code tmp-audio chat-history .wwebjs_auth .wwebjs_cache

node hf_health_server.js &
node whatsapp_groq_voice.js
