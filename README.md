# SERVITOR

local discord bot. talks to ollama on ur own rig. by default no cloud, no telemetry, no third-party calls — every msg stays on ur machine.

defaults to `huihui_ai/qwen2.5-coder-abliterate:7b` — abliterated coder model. says what u ask, no "as an AI" hedge.

**two optional cloud tools** u can wire in if u want them:
- **websearch** via duckduckgo (free, no key, automatic)
- **vision** via anthropic api (~$0.002 per image, only fires when an image is attached AND u opt in)

both are off-by-default for vision, on-by-default for websearch. text + memory always stay local.

---

## what u need

| thing | required? | why |
|---|---|---|
| discord bot token | yes | bot cant connect to discord without it. grab one at https://discord.com/developers/applications |
| ollama running | yes | hosts the LLM on `localhost:11434`. install from https://ollama.com |
| a model pulled | yes | bot calls whatever `MODEL_NAME` is set to. default is the qwen coder abliterate above. `ollama pull <model>` to grab one |
| vision model (local) | optional | a vision-capable ollama model for image attachments. e.g. `huihui_ai/qwen2.5-vl-abliterated:7b` or `qwen2.5vl:3b`. skip and image attachments fail silently — bot keeps working on text |
| anthropic api key | optional | EITHER for cloud vision (set `VISION_MODEL_NAME=anthropic:claude-haiku-4-5` and put `ANTHROPIC_API_KEY` in `.env`). way faster than local on weak GPUs, ~$0.002 per image. text never leaves ur rig — only image queries do |
| python 3.10+ | yes | discord.py + asyncio |
| os | win/linux/mac | tested on win11. `start_servitor.bat` is windows-only. on linux/mac just run `python mrrobot.py` after `ollama serve` |

---

## install

### 1. pull the model

```bash
ollama pull huihui_ai/qwen2.5-coder-abliterate:7b
```

or whichever model u want. set `MODEL_NAME` in `.env` to match.

### 2. python env

```bash
cd mrrobot
python -m venv venv
venv\Scripts\activate         # windows
# source venv/bin/activate    # linux/mac
pip install -r requirements.txt
```

### 3. discord bot setup

1. https://discord.com/developers/applications → **New Application**
2. **Bot** → reset token, copy it (shows ONCE — save it now)
3. **Privileged Gateway Intents** → flip BOTH:
   - `MESSAGE CONTENT INTENT`
   - `SERVER MEMBERS INTENT`
4. **OAuth2 → URL Generator** → scope `bot`, perms `Send Messages`, `Read Message History`, `Add Reactions`. use the generated URL to invite the bot to ur server.

### 4. config

```bash
cp .env.example .env
```

edit `.env`. paste the bot token. put ur discord username (lowercase) in `WHITELIST_USERS` so u get bypass on triggers.

---

## run it

**windows (the way):** double-click `start_servitor.bat`. it will:

1. bootstrap `system_prompt.txt` from the embedded baseline if its missing
2. show u a menu (edit / view / restore / launch)
3. kill any old SERVITOR python processes
4. start ollama if it isnt already
5. preload coder + vision models with infinite keep-alive (cold start sucks, this kills it)
6. launch the bot in its own cmd window

**manual / linux / mac:**

```bash
# ALWAYS activate the venv first or shit WONT WORK (deps live in venv, not system python)
venv\Scripts\activate          # windows
# source venv/bin/activate     # linux/mac

python mrrobot.py
```

`start_servitor.bat` already calls the venv python directly (`venv\Scripts\python.exe mrrobot.py`) so u dont need to activate when using the .bat. only matters when running by hand.

make sure ollama is running first — `ollama serve` if it isnt.

---

## editing the prompt

system prompt lives in `system_prompt.txt` next to `mrrobot.py`. bot reads it at startup. if the file is missing or empty it falls back to the embedded `SYSTEM_PROMPT_BASELINE` constant inside `mrrobot.py` — file CANT brick the bot.

`system_prompt.txt` is **gitignored** on purpose. the baseline in `mrrobot.py` is what ships. ur live edits stay on ur rig only. clone the repo on a different machine and the launcher rebuilds `system_prompt.txt` from baseline on first run.

### menu way (easy)

run `start_servitor.bat` and the menu pops before launch:

| key | does what |
|---|---|
| Enter | launch with current prompt |
| E | open `system_prompt.txt` in notepad. launcher waits till u close notepad, then back to menu |
| V | print the loaded prompt to console |
| R | restore embedded baseline (factory reset of `system_prompt.txt`) |
| Q | abort, dont launch |

edits take effect on **next launch** — no hot reload. launcher kills the old bot before relaunch so changes go in clean.

### cli way

```bash
python mrrobot.py --show-prompt     # print the prompt the bot WOULD use right now
python mrrobot.py --dump-baseline   # overwrite system_prompt.txt with the embedded baseline
```

---

## websearch (tool)

bot can search the web mid-reply when it doesnt know something. how it works:

1. SERVITOR generates `[WEBSEARCH]: <query>` and stops
2. mrrobot.py intercepts that line, runs duckduckgo via the `ddgs` lib
3. top 5 organic results (ads filtered) get injected back as context
4. bot re-prompts itself, answers with citations

u see `🔍 searching: <query>` flash up in the channel before the answer arrives.

config (env vars):
| var | default | does |
|---|---|---|
| `SEARCH_ENABLED` | `true` | master switch. set `false` to disable sentinel interception entirely |
| `SEARCH_MAX_LOOPS` | `3` | max searches per single user msg (cap on chained queries) |
| `SEARCH_MAX_RESULTS` | `5` | results returned per search after ad filter |

ad-blocking patterns: drops `bing.com/aclick`, `googleadservices`, `doubleclick`, etc. so the model doesnt cite sponsored garbage as fact.

requires `pip install ddgs`. already in `requirements.txt`.

---

## vision

two paths. pick whichever fits ur rig.

### local vision (ollama)

set `VISION_MODEL_NAME=<model>` to any vision-capable ollama model. when an image is attached, the bot auto-routes that request through the vision model instead of the coder.

works on beefy GPUs. on a 4GB GPU u'll likely OOM into CPU and timeouts — vision compute graphs are huge even for 3B models.

### cloud vision (anthropic)

set `VISION_MODEL_NAME=anthropic:claude-haiku-4-5` (or `anthropic:claude-sonnet-4-6`) and put `ANTHROPIC_API_KEY=sk-ant-...` in `.env`. now image queries route to the anthropic api instead of ollama.

| | local | anthropic |
|---|---|---|
| works on 4GB GPU? | ❌ no | ✓ yes |
| latency | 30-90s on a 5090, ∞ on a laptop | 2-5 sec |
| quality | mediocre on small models | best-in-class |
| cost | $0 | ~$0.001-0.005 per image |
| privacy | image stays on rig | image goes to anthropic |
| internet? | no | yes |

text msgs and websearch always stay local — only requests carrying an image get sent to anthropic, and only when u've configured the bridge.

requires `pip install anthropic`. already in `requirements.txt`.

env vars:
| var | default | does |
|---|---|---|
| `ANTHROPIC_API_KEY` | (empty) | required if VISION_MODEL_NAME starts with `anthropic:` |
| `ANTHROPIC_MAX_TOKENS` | `1024` | max tokens in the vision reply |

---

## !argue — argument analyser

paste a discord conversation into the bot, get back deployable counter-arguments in ur voice via the anthropic api. for when ur in a fight in another channel and cant be fked typing. operator-only.

how to use:
```
!argue <paste the convo right after the command>
```

or reply to a message with just `!argue` and the bot will pull that message's content as the convo.

what u get back:
- **QUICK READ** — 2 sentences on who's winning + the opponent's pattern
- **CODE BLOCKS** — 3-5 deployable counters, each ready to copy-paste raw into discord
- **RECOMMENDATION** — which to fire first, what to reserve, when to walk
- **CLOSE** — one cold-exit line for walking away on top

uses claude-haiku-4-5 by default (~$0.005 per analysis). about 8-12 sec response time.

requires `ANTHROPIC_API_KEY` in `.env`. lives in `argue.py` — system prompt for the analyst is there if u want to tune the voice.

env vars:
| var | default | does |
|---|---|---|
| `ARGUE_MODEL` | `claude-haiku-4-5` | model for argument analysis (sonnet for harder cases) |
| `ARGUE_MAX_TOKENS` | `2048` | max output length |

---

## who can talk to it

a msg gets a reply when ALL of these are true:

1. author isnt the bot itself, isnt another bot (unless their name is in `ALLOW_BOT_USERNAMES`), isnt blacklisted
2. AND ONE of these triggers fires:
   - author `@`-mentioned the bot
   - msg is a DM
   - author's discord username (or display name) is in `WHITELIST_USERS`
   - author has a role in `AUTHORISED_ROLES` AND the msg starts with a trigger word from `BOT_TRIGGER_NAMES`

`BLACKLIST_USERS` always wins. blacklisted user `@`-mentions the bot? they get fuck all.

---

## shutting it up mid-stream

whitelisted users can kill an in-flight stream:

| phrase | does what |
|---|---|
| `stfu` | cancel current stream. leaves a `[…cut off]` marker so u can see where it stopped |
| `shut up` / `shutup` / `shut the fuck up` | same as stfu |
| `!stop` / `!kill` | same as stfu |
| `!skip` / `skip` / `next` | SILENT cancel — deletes the in-flight msg entirely. for when u dont want the half-baked reply hanging in chat |

bot reactions:

- 🛑 — stfu fired, partial marked cut off
- ⏭️ — !skip fired, partial deleted
- 💤 — nothing was running, no-op

**auto-preempt:** send a new authorised msg while a stream is still running and the old one auto-cancels and the new one starts. dont need to stfu first.

---

## slash-style commands

prefix is `!servitor ` (configurable in code).

| command | who | what |
|---|---|---|
| `!servitor status` | whitelist or auth role | print model name, ollama url, channel memory depth |
| `!servitor forget` | whitelist or auth role | wipe rolling memory for THIS channel only |

direct phrases (no prefix needed):

| phrase | who | what |
|---|---|---|
| `stfu`, `shut up`, `!stop`, `!kill` | whitelist | cancel in-flight stream (loud — leaves cut-off marker) |
| `!skip`, `skip`, `next` | whitelist | cancel in-flight stream (silent — deletes partial) |

---

## file attachments

if a **whitelisted** user attaches files, each one gets fetched, decoded and dumped into the prompt raw. no size limits, no content filters.

| type | what happens |
|---|---|
| `.txt .md .csv .json .log .py .js .ts .html .css .sql .yml .yaml .ini .cfg .sh .ps1 .bat .lsp .lisp .c .cpp .h .rs .go .rb .java .kt .swift .xml .toml .env` | decoded as utf-8 (fallbacks: utf-8-sig, latin-1) and inlined into the prompt |
| `.pdf` | text layer extracted via `pdfplumber`. **scanned/image-only PDFs return empty** — pdfplumber doesnt OCR |
| `.docx` | extracted via `python-docx` if its installed |
| anything else | best-effort utf-8 decode. binaries return a `[UNSUPPORTED_BINARY]` marker |

non-whitelisted users get NO attachment processing. their text reads as normal but files are ignored.

---

## trigger words (for non-whitelist users)

if a user has a role in `AUTHORISED_ROLES`, they can address the bot without `@` by starting their msg with a trigger word followed by space, comma or colon:

```
machine, sitrep
servitor: write me a port scanner
spirit, what's MITRE T1021
```

defaults: `robot, mrrobot, mr robot` (configurable via `BOT_TRIGGER_NAMES`).

whitelist users dont need triggers — anything they type in a channel where the bot can read is treated as a request.

---

## streaming behaviour

when generation kicks off the bot posts `⌛ thinking…` then edits that msg every ~0.9s with the running content + a `▌` cursor. when one msg hits ~1900 chars it gets finalised (cursor dropped) and a new msg starts the continuation. final edit clears the cursor.

edit cadence is throttled so discord doesnt rate-limit u. if a discord HTTP error happens mid-stream the edit is silently skipped — next edit retries. no crash, no cleanup needed.

---

## memory

`HISTORY_DEPTH = 12` (default) means last 12 user msgs + 12 bot replies per channel are kept and replayed to the model on every call. memory:

- persists across msgs in the same channel
- **wipes on bot restart** (in-memory deque, not on disk)
- per-channel (DMs and channels each have their own)
- can be wiped manually with `!servitor forget`

channel memory bleed is real. switch topics rapidly and old context contaminates new answers. use `!servitor forget` between unrelated topics.

---

## env vars

see `.env.example` for the full template. quick ref:

| var | default | does |
|---|---|---|
| `DISCORD_BOT_TOKEN` | — | required. bot token from dev portal |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | local ollama chat endpoint |
| `MODEL_NAME` | `huihui_ai/qwen2.5-coder-abliterate:7b` | pulled ollama model name |
| `VISION_MODEL_NAME` | `huihui_ai/qwen2.5-vl-abliterated:7b` | local vision model OR `anthropic:claude-haiku-4-5` for cloud vision |
| `ANTHROPIC_API_KEY` | (empty) | required if VISION_MODEL_NAME starts with `anthropic:` |
| `ANTHROPIC_MAX_TOKENS` | `1024` | max output tokens on cloud vision replies |
| `SEARCH_ENABLED` | `true` | websearch sentinel interception (set `false` to disable) |
| `SEARCH_MAX_LOOPS` | `3` | max chained searches per single user msg |
| `SEARCH_MAX_RESULTS` | `5` | results returned per DDG search |
| `BOT_TRIGGER_NAMES` | `robot,mrrobot,mr robot` | csv trigger words for role-gated invocation |
| `AUTHORISED_ROLES` | (empty) | csv server role names allowed via triggers |
| `WHITELIST_USERS` | (empty) | csv discord usernames that bypass triggers |
| `ALLOW_BOT_USERNAMES` | (empty) | csv bot usernames the bot WILL respond to (for webhook testing) |
| `BLACKLIST_USERS` | (empty) | csv discord usernames the bot ignores entirely |
| `HISTORY_DEPTH` | `12` | rolling memory size per channel |
| `REQUEST_TIMEOUT` | `120` | ollama HTTP timeout (seconds) |

---

## warnings to ignore

on startup ull see:

```
[WARNING] PyNaCl is not installed, voice will NOT be supported
[WARNING] davey is not installed, voice will NOT be supported
```

ignore them. bot doesnt do voice.

---

## file layout

```
mrrobot/
  mrrobot.py            # the bot. has SYSTEM_PROMPT_BASELINE fallback baked in
  web_search.py         # duckduckgo wrapper for the [WEBSEARCH] sentinel
  argue.py              # !argue command — argument analyser via anthropic api
  system_prompt.txt     # live editable prompt — gitignored, private to ur rig
  start_servitor.bat    # launcher: prompt menu + ollama warmup + bot start
  stop_servitor.bat     # kills SERVITOR python process
  requirements.txt
  .env.example          # template
  .env                  # ur real config — gitignored
  .gitignore
  README.md             # this thing
  venv/                 # gitignored
```

---

## license

private. dont fork. no contributions. mine.
