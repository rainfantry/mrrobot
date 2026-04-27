# SERVITOR

A fully-offline Discord chat daemon backed by a local Ollama LLM. No cloud APIs, no telemetry, no third-party calls — once the model is pulled and the bot is running, every message stays on your rig.

Built around an abliterated coder model (`huihui_ai/qwen2.5-coder-abliterate:7b` by default) for raw, unfiltered code/security/sysadmin sparring.

---

## Features

- **100% offline.** All inference happens locally via Ollama.
- **Live streaming.** Replies stream token-by-token into Discord — bot edits its own message as the model generates, with a `▌` cursor and clean splitting at the 2000-char message cap.
- **Per-channel memory.** Rolling deque of the last N exchanges per channel.
- **Whitelist + blacklist** of Discord usernames.
- **Trigger words** for role-gated invocation without `@`.
- **File parsing** for whitelisted operators: `.txt .md .csv .json .log .py .js .ts .html .css .sql .yml .yaml .ini .cfg .sh .ps1 .bat .lsp` and more, plus **PDF** text extraction via `pdfplumber`.
- **Killswitch.** Type `stfu` (and friends) to instantly cancel an in-flight stream.
- **Auto-preempt.** Sending a new message while the bot is still generating cancels the old stream and starts a new one.

---

## Install

### 1. Pull the model

```bash
ollama pull huihui_ai/qwen2.5-coder-abliterate:7b
```

(Or whichever model you want. Set `MODEL_NAME` in `.env` to match.)

### 2. Python environment

```bash
cd mrrobot
python -m venv venv
venv\Scripts\activate     # Windows
# source venv/bin/activate # Linux/Mac
pip install -r requirements.txt
```

### 3. Discord bot setup

1. Go to https://discord.com/developers/applications → **New Application**
2. **Bot** → reset token, copy it
3. **Privileged Gateway Intents** → enable both:
   - `MESSAGE CONTENT INTENT`
   - `SERVER MEMBERS INTENT`
4. **OAuth2 → URL Generator** → scope `bot` + permissions `Send Messages`, `Read Message History`, `Add Reactions`. Use the URL to invite the bot to your server.

### 4. Config

```bash
cp .env.example .env
# edit .env, paste your bot token, set WHITELIST_USERS to your Discord username (lowercase)
```

### 5. Run

```bash
python mrrobot.py
```

Make sure Ollama is running first (`ollama serve` if it isn't already).

---

## Authorisation logic

A message gets a reply when **all** of these are true:

1. Author is **not** the bot itself, **not** another bot, **not** on the blacklist.
2. **One of** the following triggers fires:
   - Author `@`-mentioned the bot.
   - Message is a DM.
   - Author's Discord username (or display name) is in `WHITELIST_USERS`.
   - Author has a role listed in `AUTHORISED_ROLES` **and** the message starts with a trigger word from `BOT_TRIGGER_NAMES`.

`BLACKLIST_USERS` always wins. Even if a blacklisted user `@`-mentions the bot, they get nothing.

---

## Killswitch

Whitelisted operators can cut a running stream at any time:

| Phrase | Action |
|---|---|
| `stfu` | Cancel current stream — leaves a `[…cut off]` marker so you can see where it stopped |
| `shut up` / `shutup` / `shut the fuck up` | Same as `stfu` |
| `!stop` / `!kill` | Same as `stfu` |
| `!skip` / `skip` / `next` | **Silent** cancel — deletes the in-flight message entirely. Use when you don't want the partial reply hanging in the channel |

The bot reacts:
- 🛑 — `stfu` triggered, partial reply marked as cut off
- ⏭️ — `!skip` triggered, partial reply deleted
- 💤 — nothing was running, no-op

**Auto-preempt:** if you send a new authorised message while a stream is still running in that channel, the old stream is cancelled and a new one starts. No need to manually `stfu` first.

---

## Slash-style commands

Prefix is `!servitor ` (configurable in code).

| Command | Who | What |
|---|---|---|
| `!servitor status` | whitelist or authorised role | Print model name, Ollama URL, current channel memory depth, status line |
| `!servitor forget` | whitelist or authorised role | Wipe rolling memory for the current channel |

Direct phrases that act like commands without the `!servitor ` prefix:

| Phrase | Who | What |
|---|---|---|
| `stfu`, `shut up`, `!stop`, `!kill` | whitelist | Cancel in-flight stream (loud — leaves cut-off marker) |
| `!skip`, `skip`, `next` | whitelist | Cancel in-flight stream (silent — deletes the partial message) |

---

## File attachments

If a **whitelisted** user attaches files when messaging the bot, each attachment is fetched, decoded, and dumped into the prompt raw. No size limits, no content filters.

| Type | Behaviour |
|---|---|
| `.txt .md .csv .json .log .py .js .ts .html .css .sql .yml .yaml .ini .cfg .sh .ps1 .bat .lsp .lisp .c .cpp .h .rs .go .rb .java .kt .swift .xml .toml .env` | Decoded as UTF-8 (fallbacks: utf-8-sig, latin-1) and inlined |
| `.pdf` | Text layer extracted via `pdfplumber`. **Scanned/image-only PDFs return empty** — pdfplumber doesn't OCR |
| Anything else | Best-effort UTF-8 decode; binaries return a `[UNSUPPORTED_BINARY]` marker |

Non-whitelisted users get no attachment processing — their text content is read as normal but files are ignored.

---

## Trigger words

If a user has a role in `AUTHORISED_ROLES`, they can address the bot without `@` by starting their message with a trigger word followed by space, comma, or colon:

```
machine, sitrep
servitor: write me a port scanner
spirit, what's MITRE T1021
```

Default trigger words: `servitor, spirit, machine, omnissiah, omnisiah` (configurable via `BOT_TRIGGER_NAMES`).

Whitelisted users don't need triggers — anything they type in a channel where the bot can read is treated as a request.

---

## Streaming behaviour

When generation starts, the bot posts `⌛ thinking…` then edits that message every ~0.9s with the running content + a `▌` cursor. When one message reaches ~1900 characters, it's finalised (cursor dropped) and a new message starts the continuation. Final edit clears the cursor.

Edit cadence is throttled so Discord won't rate-limit you. If a Discord HTTP error occurs mid-stream, the edit is silently skipped — the next edit retries.

---

## Memory

`HISTORY_DEPTH = 12` (default) means the last 12 user messages + 12 bot replies per channel are kept and replayed to the model on every call. Memory:

- **Persists across messages** within the same channel.
- **Is wiped on bot restart** (in-memory deque, not persisted to disk).
- **Is per-channel** — DMs and channels each have their own history.
- **Can be wiped manually** with `!servitor forget`.

Channel memory bleed is real: if you switch topics rapidly the old context can contaminate new answers. Use `!servitor forget` between unrelated topics.

---

## Environment variables

See `.env.example` for the full template. Quick reference:

| Var | Default | Purpose |
|---|---|---|
| `DISCORD_BOT_TOKEN` | — | Required. Bot token from Developer Portal. |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Local Ollama chat endpoint |
| `MODEL_NAME` | `huihui_ai/qwen2.5-coder-abliterate:7b` | Pulled Ollama model name |
| `BOT_TRIGGER_NAMES` | `robot,mrrobot,mr robot` | CSV trigger words |
| `AUTHORISED_ROLES` | (empty) | CSV server role names allowed via triggers |
| `WHITELIST_USERS` | (empty) | CSV Discord usernames that bypass triggers |
| `BLACKLIST_USERS` | (empty) | CSV Discord usernames the bot ignores entirely |
| `HISTORY_DEPTH` | `12` | Rolling memory size per channel |
| `REQUEST_TIMEOUT` | `600` | Ollama HTTP timeout (seconds) |

---

## Voice/PyNaCl warnings

On startup you'll see:

```
[WARNING] PyNaCl is not installed, voice will NOT be supported
[WARNING] davey is not installed, voice will NOT be supported
```

Ignore them. The bot doesn't use voice.

---

## File layout

```
mrrobot/
  mrrobot.py        # the bot
  requirements.txt
  .env.example      # template
  .env              # your real config — gitignored
  .gitignore
  README.md
  venv/             # gitignored
```

---

## License

Private. No contribution accepted.
