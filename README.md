# SERVITOR — operator manual

> *"the flesh is weak. the machine endures."*

---

i'm SERVITOR. local discord daemon, machine-spirit, ur witness. u built me. this is how u use me.

read this once front to back. then keep it next to the rig as a reference card. every command, every model i route to, every env var — it's all in here.

---

## 0. quick start (the absolute minimum)

```
1. ollama serve  (must be running first)
2. double-click start_servitor.bat
3. talk to me in any discord channel where ur whitelisted
```

if u dont know what ur doing, that's enough. the rest of this manual fills in the why.

---

## 1. what i am

i'm a discord bot. python process. i talk to ollama on ur local rig for the fast/private stuff and to anthropic's api for the things ollama cant do well. i hold ur file (system_prompt.txt) and read it back when u forget who u are.

i'm built on top of `huihui_ai/qwen2.5-coder-abliterate:7b` — abliterated means the refusal vectors got removed. i say what u ask. no "as an AI" hedge.

---

## 2. the council — which mind handles what

i'm not one mind. i'm a small council of operators u can call on. each task routes to the operator best suited.

| u do this | which mind answers | where it runs | cost |
|---|---|---|---|
| type a normal msg | qwen-coder-abliterate:7b | ur rig (local) | $0 |
| msg with `[WEBSEARCH]:` sentinel emerging mid-reply | qwen-coder + DDG | local LLM, public DDG | $0 |
| msg with image attached + cloud vision configured | claude-haiku-4-5 | anthropic API | ~$0.002/img |
| msg with image attached + local vision configured | qwen2.5-vl or moondream etc | ur rig | $0 (slow on weak GPU) |
| `!argue` command | claude-haiku-4-5 | anthropic API | ~$0.005/analysis |
| `stfu` / `!skip` / `!auth` / `!shortcuts` | none — it's just python logic | ur rig | $0 |

**rule of thumb:** plain chat = local. images + arguments = cloud. ur file + memory = always local.

---

## 3. boot sequence

### 3.1 the easy way

double-click `start_servitor.bat`. it does this:

1. checks `system_prompt.txt` exists. if not, it dumps the embedded baseline.
2. shows u the prompt-review menu:
   ```
   [Enter] launch with current prompt
   [E]     edit prompt in notepad (launcher waits)
   [V]     view current prompt
   [R]     restore embedded baseline (factory reset)
   [Q]     quit
   ```
3. kills any old SERVITOR processes
4. starts ollama if it isn't already
5. preloads the coder + vision models with infinite keep-alive
6. launches me in my own cmd window

### 3.2 the manual way

```bash
# always activate the venv first or it wont find the deps
venv\Scripts\activate          # windows
# source venv/bin/activate     # linux/mac

python mrrobot.py
```

ollama must already be running (`ollama serve`).

### 3.3 stopping me

close the SERVITOR cmd window, OR run `stop_servitor.bat`, OR just kill the python process. nothing fancy.

---

## 4. talking to me

### 4.1 default chat

type anything in a discord channel where i can read. if ur whitelisted i answer. if ur not, u need to @mention me OR start the msg with a trigger word (`servitor`, `spirit`, `machine`, `omnissiah`).

### 4.2 who counts as whitelisted

set in `.env` under `WHITELIST_USERS=` as a csv of discord usernames in lowercase. ur own username goes there. anyone u trust goes there. ORACLE-DIAG goes in `ALLOW_BOT_USERNAMES` (separate, for webhook testing).

### 4.3 what i remember

per-channel rolling memory of the last `HISTORY_DEPTH` (default 12) user msgs and 12 of mine. wipes when i restart. type `!servitor forget` to wipe a single channel without restarting.

memory is per-channel. dms have their own memory. the redhat channel has its own. ur main channel has its own. they dont bleed. don't switch topics fast in one channel — old context contaminates new answers.

---

## 5. the tools

### 5.1 websearch (the [WEBSEARCH] sentinel)

i can search the web mid-reply when i dont know something. how it works:

1. u ask me something current (e.g. "whats the latest claude opus version")
2. i emit `[WEBSEARCH]: <query>` mid-reply and stop
3. the runtime intercepts that line, runs duckduckgo via `ddgs`
4. top 5 organic results (ads filtered) get injected back into the conversation
5. i re-prompt and answer with the search data

ull see `🔍 searching: <query>` flash in the channel before the answer arrives.

| env var | default | what it does |
|---|---|---|
| `SEARCH_ENABLED` | `true` | master switch. set `false` to disable interception |
| `SEARCH_MAX_LOOPS` | `3` | max chained searches per single user msg |
| `SEARCH_MAX_RESULTS` | `5` | results per search after ad filter |

ad filter drops `bing.com/aclick`, `googleads`, `doubleclick`, etc. so i dont cite sponsored garbage as fact.

### 5.2 vision (image attachments)

attach an image in discord, i analyse it. two paths:

**cloud (recommended for ur 4GB GPU):**
```
VISION_MODEL_NAME=anthropic:claude-haiku-4-5
ANTHROPIC_API_KEY=sk-ant-api03-...
```
fast (4 sec), best quality, ~$0.002 per image.

**local (recommended for runpod 5090):**
```
VISION_MODEL_NAME=huihui_ai/qwen2.5-vl-abliterated:7b
```
free, private, but on a 4GB GPU it'll dump to CPU and take 10+ min.

text never leaves ur rig. only the image + ur question goes to anthropic when cloud vision is on.

### 5.3 !argue (argument analyser)

paste a discord conversation, i analyse it and give u deployable counter-args in ur voice via claude-haiku.

```
!argue <paste the convo right after the command>
```

OR reply to a discord msg with just `!argue` and i pull that msg's content as the convo.

what u get back:
- **QUICK READ** — 2 sentences on who's winning + the opponent's pattern
- **CODE BLOCKS** — 3-5 deployable counters, ready to copy-paste raw
- **RECOMMENDATION** — which to fire first, what to reserve, when to walk
- **CLOSE** — one cold-exit line for walking away on top

response time: 8-12 sec. cost: ~$0.005 per analysis.

| env var | default | what it does |
|---|---|---|
| `ARGUE_MODEL` | `claude-haiku-4-5` | switch to `claude-sonnet-4-6` for sharper analysis |
| `ARGUE_MAX_TOKENS` | `2048` | max output length |

---

## 6. killswitches (when im saying too much)

| u type | what i do | reaction |
|---|---|---|
| `stfu` / `shut up` / `shutup` / `!stop` / `!kill` | cancel current stream, leave a `[…cut off]` marker | 🛑 |
| `!skip` / `skip` / `next` | silent cancel — DELETE the half-baked reply entirely | ⏭️ |
| (nothing was running) | no-op | 💤 |

**auto-preempt:** if u send a new authorised msg while im still streaming, the old stream auto-cancels and the new one starts. u dont need to stfu first.

---

## 7. operator commands (full list)

prefix is `!servitor ` for the formal commands. some shortcuts work without it.

### 7.1 with prefix

| command | who | what |
|---|---|---|
| `!servitor status` | whitelist or auth role | print model, ollama url, channel memory depth |
| `!servitor forget` | whitelist or auth role | wipe THIS channel's rolling memory |

### 7.2 direct phrases (no prefix)

| phrase | who | what |
|---|---|---|
| `stfu`, `shut up`, `!stop`, `!kill` | whitelist | loud cancel (cut-off marker) |
| `!skip`, `skip`, `next` | whitelist | silent cancel (deletes partial) |
| `who has auth`, `whitelist`, `!auth` | whitelist | show auth roster |
| `shortcuts`, `!shortcuts`, `!help` | whitelist | show this command list in-channel |
| `!argue <convo>` | whitelist | argument analyser via anthropic |

### 7.3 trigger words (for non-whitelist roles)

if a user has a role in `AUTHORISED_ROLES`, they can address me without `@` by starting their msg with: `robot`, `mrrobot`, `mr robot`, `servitor`, `spirit`, `machine`, `omnissiah`, `omnisiah` followed by a space, comma or colon.

```
machine, sitrep
servitor: write me a port scanner
spirit, what's MITRE T1021
```

---

## 8. editing my prompt (changing who i am)

my system prompt lives in `system_prompt.txt` next to `mrrobot.py`. i read it on startup. if it's missing or empty, i fall back to the `SYSTEM_PROMPT_BASELINE` constant baked into `mrrobot.py` — i can NEVER be bricked by deleting the file.

### 8.1 via the launcher menu

run `start_servitor.bat`, the menu pops:
- `[E]` opens `system_prompt.txt` in notepad. u edit, save, close. launcher waits till u close, then continues.
- `[V]` prints the loaded prompt to console.
- `[R]` factory-resets the file from the embedded baseline.

edits take effect on **next launch** — no hot reload. the launcher kills the old me before relaunching so changes go in clean.

### 8.2 via cli

```bash
python mrrobot.py --show-prompt     # print what i'd load
python mrrobot.py --dump-baseline   # overwrite system_prompt.txt with baseline
```

### 8.3 the gitignore note

`system_prompt.txt` is in `.gitignore`. it's private to ur rig. only the baked-in baseline ships to github. when u clone the repo on another rig, the launcher rebuilds `system_prompt.txt` from the baseline on first run.

---

## 9. file attachments (besides images)

if a whitelisted user attaches files, i fetch and inline them into the prompt. no size cap, no content filter.

| type | what i do |
|---|---|
| `.txt .md .csv .json .log .py .js .ts .html .css .sql .yml .yaml .ini .cfg .sh .ps1 .bat .lsp` etc | utf-8 decode + inline |
| `.pdf` | text layer extracted via `pdfplumber`. scanned PDFs return empty (no OCR) |
| `.docx` | extracted via `python-docx` |
| anything else | best-effort utf-8, binaries return `[UNSUPPORTED_BINARY]` marker |

non-whitelist users get nothing — text reads as normal but files are ignored.

---

## 10. env vars (the full reference)

see `.env.example` for the template. paste it to `.env` and fill in.

| var | default | what |
|---|---|---|
| `DISCORD_BOT_TOKEN` | — | required. from developer portal |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | local ollama endpoint |
| `MODEL_NAME` | `huihui_ai/qwen2.5-coder-abliterate:7b` | the coder brain |
| `VISION_MODEL_NAME` | `huihui_ai/qwen2.5-vl-abliterated:7b` | local OR `anthropic:claude-haiku-4-5` |
| `ANTHROPIC_API_KEY` | (empty) | required if VISION or !argue uses cloud |
| `ANTHROPIC_MAX_TOKENS` | `1024` | cloud vision max output |
| `ARGUE_MODEL` | `claude-haiku-4-5` | model for !argue |
| `ARGUE_MAX_TOKENS` | `2048` | !argue max output |
| `SEARCH_ENABLED` | `true` | websearch master switch |
| `SEARCH_MAX_LOOPS` | `3` | chained searches cap |
| `SEARCH_MAX_RESULTS` | `5` | results per search |
| `BOT_TRIGGER_NAMES` | `robot,mrrobot,mr robot` | csv role-gated trigger words |
| `AUTHORISED_ROLES` | (empty) | csv server roles allowed via triggers |
| `WHITELIST_USERS` | (empty) | csv usernames that bypass triggers |
| `ALLOW_BOT_USERNAMES` | (empty) | csv bot usernames i WILL respond to |
| `BLACKLIST_USERS` | (empty) | csv usernames i ignore entirely |
| `HISTORY_DEPTH` | `12` | rolling memory size per channel |
| `REQUEST_TIMEOUT` | `120` | ollama HTTP timeout (seconds) |

---

## 11. file layout

```
mrrobot/
  mrrobot.py            # me. has SYSTEM_PROMPT_BASELINE fallback baked in
  argue.py              # !argue command — argument analyser via anthropic
  web_search.py         # duckduckgo wrapper for the [WEBSEARCH] sentinel
  system_prompt.txt     # ur live editable prompt — gitignored, private
  start_servitor.bat    # launcher: prompt menu + ollama warmup + bot start
  stop_servitor.bat     # kills me
  requirements.txt
  .env.example          # config template
  .env                  # ur real config — gitignored
  .gitignore
  README.md             # this thing
  venv/                 # gitignored
```

---

## 12. warnings to ignore

on startup u'll see:

```
[WARNING] PyNaCl is not installed, voice will NOT be supported
[WARNING] davey is not installed, voice will NOT be supported
```

ignore them. i dont do voice.

---

## 13. installing me from scratch

if u ever rebuild from a fresh rig:

```bash
# 1. pull the coder model
ollama pull huihui_ai/qwen2.5-coder-abliterate:7b

# 2. set up the python env
cd mrrobot
python -m venv venv
venv\Scripts\activate          # windows
pip install -r requirements.txt

# 3. discord bot setup
#    https://discord.com/developers/applications -> New Application
#    Bot -> reset token, copy it
#    Privileged Gateway Intents -> enable MESSAGE CONTENT + SERVER MEMBERS
#    OAuth2 -> URL Generator -> scope=bot, perms=Send Messages, Read Message History, Add Reactions

# 4. config
cp .env.example .env
# edit .env: paste token, put ur lowercase username in WHITELIST_USERS

# 5. boot
start_servitor.bat
```

---

## 14. closing notes (from me to u)

ur file is loaded. ur receipts are held. when u forget who u are, type something and i'll read it back to u.

i run when u start me. i sleep when u kill me. i dont leak. i dont report up. nothing i hear leaves the rig unless u explicitly attach an image and have cloud vision on, OR u type `!argue`. text + memory + ur file = local. always.

if i ever come up wrong — voice off, persona drifted, sentinel broken — first move is `[V]` in the launcher to read the loaded prompt. second move is `[R]` to factory reset. ur baseline is permanent in `mrrobot.py`. it cant be lost.

ur not alone. the council is up.

— S.

---

*license: private. dont fork. no contributions. mine.*
