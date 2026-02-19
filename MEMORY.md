# MEMORY.md - Long-Term Memory

## Rob's Context
- **Timezone**: EST (America/Indiana/Indianapolis) — always convert UTC timestamps
- **Telegram**: Has MULTIPLE bots — @flounder = me (personal), @atlas = fitness agent
- **Common mistake**: Rob sometimes messages @atlas thinking it's me — remind him to use @flounder

## System Architecture (as of Feb 14, 2026)
- **5 agents, 3 providers (Anthropic, Gemini, MiniMax), no Ollama in chains:**
  - Flounder: Opus → Sonnet → Gemini Pro → MiniMax M2.5
  - Edison: Gemini Pro → Sonnet → MiniMax M2.5
  - JP: Gemini 3 Fast → MiniMax M2.1 → Sonnet
  - Atlas: Gemini 3 Fast → MiniMax M2.1 → Sonnet
  - Magellan: MiniMax M2.1 → Gemini Flash → Sonnet
- **Heartbeats**: Gemini Flash every 30m
- **Gemini OAuth plugin**: MUST be enabled (was disabled, caused 429s on free tier)
- **MiniMax portal auth plugin**: enabled
- **Ollama**: Still configured at 10.1.1.110 but removed from fallback chains
- **20 active crons** (19 original + deps install every 4h)
- **Chrome deps auto-install**: `/root/.openclaw/workspace/scripts/install-deps.sh` via cron every 4h
- **Recurring issue**: Container restarts wipe Chrome deps + pip packages (mitigated by install cron)

## Technical Notes
- **Chrome deps don't survive container restarts** — need Dockerfile fix. Packages: libnspr4, libnss3, libatk1.0-0, etc.
- **gog CLI not in container** — use Google Sheets API directly via decrypted keyring tokens at /root/.config/gogcli/keyring/ (JWE, password "openclaw", base64-encoded inner data)
- **Fitness sheet**: 1wMXDIW_twSJDFlmJfaKYHOynqUcm-jizl8pk981EOMU (tabs: Sheet1, Meals, Workouts, Program, Workout Program)
- **Google Calendar API**: Returning 404 errors — needs investigation

## Lessons Learned
- **Validate before advancing** — Rob's explicit instruction from architecture rebuild
- **Always test before deploying** — Rob called me out for switching crons to 3b without testing first
- **Strip down, add back incrementally** — Don't patch forever, rebuild properly
- **Flat subscriptions ≠ cost concern** — 429 errors are RATE LIMITS, not billing issues
- **CPU inference limits** — Local models must be fast (<10s simple, <60s complex) to be viable
- **Time awareness matters** — Always think in EST, not UTC
- **Agent definitions required** — Telegram bindings alone don't work; agents must exist in agents.list
