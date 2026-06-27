# SERVITOR — operator manual

> *"the flesh is weak. the machine endures."*

---

i'm SERVITOR. local discord daemon, machine-spirit, ur witness. u built me. this is how u use me.

read this once front to back. then keep it next to the rig as a reference card. every command, every model i route to, every env var — it's all in here.

---

## setup from zero (first-time install — skip if already running)

if u dont have python, ollama, a venv, a discord bot, or any of this yet — start here. ~20-30 min from clean machine to bot online.

### prerequisites

- windows 10/11 (linux/mac mostly works too — scripts are bash-compatible, just adapt paths)
- ~30 gb free disk (ollama models + comfyui + python)
- gpu is optional but heavily recommended. nvidia preferred. 8gb+ vram lets u run 7b models smoothly. cpu-only works but slow (1-5 tok/s)
- internet for the one-time downloads

### 1. install python

python 3.12 or newer. 3.14 is what this is tested on. just tick **"add python to PATH"** during install.

1. download installer from https://python.org/downloads
2. tick **"add python to PATH"** during install
3. verify in powershell: `python --version` → should print `Python 3.x.x`

### 2. install ollama

1. download from https://ollama.com/download
2. install (windows installer is one-click)
3. ollama auto-starts as a tray app. leave it running.
4. verify: `ollama --version` → should print version

### 3. pull the models

in powershell (each is a few gb, takes 1-10 min depending on bandwidth):

```
ollama pull huihui_ai/qwen2.5-coder-abliterate:7b
ollama pull huihui_ai/qwen2.5-vl-abliterated:3b
```

these are the defaults referenced in `.env.example`. coder = text chat. vl = vision for image attachments. other models are optional — see §2 (the council) for what each does.

### 4. register ur discord bot

1. go to https://discord.com/developers/applications
2. **New Application** → name it (e.g. SERVITOR)
3. **Bot** tab → **Reset Token** → COPY THE TOKEN (shown once, save it now)
4. **Privileged Gateway Intents** → enable **Message Content Intent** (required, otherwise i cant read messages)
5. **OAuth2** → **URL Generator**:
   - scopes: `bot` + `applications.commands`
   - bot permissions: `Send Messages`, `Read Message History`, `Attach Files`, `Add Reactions`, `Embed Links`
6. copy the generated url → paste in browser → invite the bot to ur discord server

### 5. clone + bootstrap

```
git clone https://github.com/rainfantry/mrrobot.git
cd mrrobot
```

then double-click **`setup.bat`**. it handles everything:
- creates the venv
- installs requirements.txt
- copies `.env.example` → `.env` and opens it in notepad
- checks if Ollama is running (and if it's remote, tells u the firewall commands needed)
- validates ElevenLabs TTS key/voice if configured

minimum fields to fill in `.env`:
- `DISCORD_BOT_TOKEN=` — paste the token from step 4
- `WHITELIST_USERS=` — ur discord username in lowercase, e.g. `jewge`
- everything else has sensible defaults

save + close notepad when done.

### 7. (optional) install comfyui for `!gen` image generation

skip this section if u dont need image gen. text chat works without comfyui.

1. download comfyui desktop from https://www.comfy.org/download
2. install, run it once, let it download sdxl base + xformers (~10gb)
3. by default comfyui listens on `localhost:8188` — matches `COMFY_HOST` default in `.env`. if comfyui binds a different port, update `COMFY_HOST` in `.env` accordingly.
4. download a base SDXL checkpoint to comfyui's `models/checkpoints/`. recommended: `RealVisXL_V5.0` or `Juggernaut-XL_v9` from huggingface.

#### 7.1 train a custom LoRA (optional, for character-specific gen)

if u want SERVITOR to gen images of a specific person/character, train a LoRA via the companion repo:

→ https://github.com/rainfantry/sdxl-lora-kit

bare-pod runpod bootstrap script in there pulls everything (kohya, sdxl base, ur dataset from gdrive), trains a LoRA in ~50 min on a 3090 (~$0.25 on runpod community cloud). drop the resulting `.safetensors` into ur local comfyui's `models/loras/` folder + reference it from `gen_template.json`.

### 8. launch

double-click `start_servitor.bat`. it bootstraps `system_prompt.txt` + template jsons, waits for ollama, preloads models, then launches me in a separate cmd window. look for:

```
[INFO] SERVITOR online as SERVITOR#NNNN
```

go to ur discord server → type `servitor hello` in any channel where i can read. if i answer, ur done.

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

### 5.3 !tts (ElevenLabs voice)

when enabled, every bot reply is spoken aloud on the host machine AND uploaded to the discord channel as a playable WAV — so anyone on any device can hear it.

**toggle:**
```
!tts          ← on/off switch (shows current state)
```

**direct speak (no LLM involved):**
```
!tts say this out loud right now
```

**caps = louder/more expressive:** text with >60% uppercase chars gets boosted style automatically.

**setup:** add to `.env`:
```ini
EL_API_KEY=sk_...        # from https://elevenlabs.io > Profile > API Key
EL_VOICE_ID=twLPF5...   # from https://elevenlabs.io > Voices > copy ID
```

all voice params are in `.env` — see §10 for the full list. if ElevenLabs is unreachable, falls back to Windows SAPI (Zira voice).

---

### 5.4 !argue (argument analyser)

paste a discord conversation, i analyse it and give u deployable counter-args in ur voice. routes to claude-haiku via anthropic by default.

**default usage (cloud):**
```
!argue <paste the convo right after the command>
```

**local fallback (A/B test or offline):**
```
!argue --local <paste convo>
```

OR reply to a discord msg with just `!argue` (or `!argue --local`) and i pull that msg's content as the convo body.

**what u get back:**
- **QUICK READ** — 2 sentences on who's winning + the opponent's pattern
- **CODE BLOCKS** — 3-5 deployable counters, ready to copy-paste raw
- **RECOMMENDATION** — which to fire first, what to reserve, when to walk
- **CLOSE** — one cold-exit line for walking away on top

| route | model | latency | cost | quality |
|---|---|---|---|---|
| default (cloud) | `claude-haiku-4-5` | 8-12 sec | ~$0.005 | sharp |
| `--local` | `huihui_ai/qwen2.5-coder-abliterate:7b` | 30-40 sec | $0 | weak (see findings) |

| env var | default | what it does |
|---|---|---|
| `ARGUE_MODEL` | `claude-haiku-4-5` | switch to `claude-sonnet-4-6` for sharper analysis |
| `ARGUE_MAX_TOKENS` | `2048` | max output length |

### 5.4.1 findings — why u should default to cloud for !argue

i benchmarked both routes on the same discord convo, same system prompt. results:

| dimension | local qwen-coder | cloud haiku | winner |
|---|---|---|---|
| followed format | ✓ | ✓ | tie |
| read who was winning correctly | ❌ said the opponent was winning when he was clearly losing | ✓ identified the retreat pattern | **haiku** |
| operator voice (lowercase, terse) | ❌ proper grammar, capitalisation | ✓ matched ur style | **haiku** |
| named fallacies precisely | ❌ generic "ad hominem" only | ✓ named signalling, goalpost shift | **haiku** |
| counters actually counter | ❌❌ first counter AGREED with the opponent | ✓ counters were sharp | **haiku** |
| recommendation | ❌ nonsensical | ✓ actionable order | **haiku** |
| close line | ❌ filler | ✓ cold exit ready | **haiku** |

**the killshot:** local qwen-coder's first counter literally validated the opponent's manosphere talking point. if u'd pasted that into discord u'd have lost the room u'd already won. argument analysis is not a code task — it's a model-of-mind task ("who is the operator, what side, what would land"). 7B coder fine-tunes don't have the reasoning depth.

**verdict:** keep `--local` for A/B testing future model upgrades (when u have a 5090 + can run mixtral or gemma2:27b). for daily use, cloud haiku is the move. $0.005 per fight is cheap.

---

### 5.5 !gen (ComfyUI image generation bridge)

pipe a text prompt to ur local ComfyUI install, post the generated image back to the channel. fully local — no API calls leave ur rig. whitelist-gated.

**usage:**
```
!gen at the beach golden hour
!gen --seed 42 portrait studio lighting
!gen sks_woman, woman, indoor cafe, warm tungsten light
```

**flow:**
1. u type `!gen <prompt>` in any channel where ur whitelisted
2. bot reacts 🎨 and posts `*generating via ComfyUI…*` placeholder
3. bridge POSTs the prompt to ComfyUI's HTTP API (`http://localhost:8188/prompt` by default)
4. ComfyUI cooks for 30-90 sec
5. bot edits placeholder to show ur prompt + posts the image as a file attachment + reacts ✅

**setup (one time):**

1. install ComfyUI Desktop OR portable. make sure it's running before u use !gen.
2. set `COMFY_HOST` in `.env` to wherever ComfyUI is reachable. default 8188; many installs use 8000 — check ur ComfyUI startup log for the actual port.
3. edit `gen_template.json` (next to mrrobot.py) and change:
   - `"ckpt_name"` → ur SDXL checkpoint filename (must be in `ComfyUI/models/checkpoints/`)
   - `"lora_name"` → ur LoRA filename (must be in `ComfyUI/models/loras/`)
   - `"text"` of node 4 → ur negative prompt (anti-artifact pack)
   - dimensions, sampler, cfg, steps — whatever u tuned
4. set `TRIGGER_TOKEN` in `.env` to ur LoRA's trigger (e.g. `sks_woman, woman`). bot auto-prepends to any !gen prompt that doesn't already contain it.

**hot-edit:** `gen_template.json` is re-read on EVERY `!gen` call. so u can tune LoRA strength, swap checkpoint, change negatives WHILE the bot runs. no restart needed. test the change on the next `!gen`.

**flags:**
- `--seed <int>` — fix the seed for reproducible composition. default is random per call.

**dependencies:**
- ComfyUI running locally (or remote, set `COMFY_HOST`)
- `comfyui_bridge.py` + `gen_template.json` next to `mrrobot.py`
- Python `aiohttp` (already a dep)

**diagnose without Discord:** the bridge has a CLI test mode.
```bash
python comfyui_bridge.py "test prompt"
```
Saves `test_gen.png` next to the script if successful, prints error otherwise. Fastest way to confirm ComfyUI is reachable + workflow loads + LoRA fires before going through the full Discord round-trip.

**troubleshooting:**

| symptom | fix |
|---|---|
| `!gen: comfyui_bridge.py not found` | module missing — check it's next to mrrobot.py; restart bot |
| `can't reach ComfyUI at http://...` | ComfyUI not running OR wrong COMFY_HOST port |
| `ComfyUI POST /prompt 400` | bad node refs in gen_template.json OR model file missing from `ComfyUI/models/` |
| generation times out | raise `COMFY_TIMEOUT_SEC` in .env (or set to 0 for unlimited) |
| face doesn't look right | edit `gen_template.json` → raise `"strength_model"` from 0.9 → 0.95 |
| outputs too plasticky | edit `gen_template.json` → lower `"cfg"` from 5.0 → 4.5 |

**privacy note:** generated images post to the channel where u invoked `!gen`. anyone in that channel sees them. for sensitive subjects (e.g. real-person face LoRAs), only invoke from channels u fully control or DM-style channels.

### 5.5.1 natural-language gen (no `!gen` needed)

i can also generate images from conversational requests. just say what u want in natural english:

```
yo show me her at the beach
make a pic of her in cyberpunk neon
i want to see her at golden hour in the park
draw her wearing a black silk dress
```

how it works: my LLM emits a `[GENERATE]: <SDXL prompt>` sentinel (same family as `[WEBSEARCH]:` for web search). the runtime intercepts, calls ComfyUI, posts the image, then re-prompts me with a confirmation marker so i can react to what i just "made" in conversation.

required setup:
1. add the IMAGE GENERATION block to `system_prompt.txt` (teaches the LLM when to emit the sentinel)
2. keep `GENERATE_ENABLED=true` in `.env` (default)
3. ComfyUI must be running same as for `!gen` (uses same bridge)

config knobs in `.env`:
- `GENERATE_ENABLED=true` — set false to disable natural-language gen entirely (forcing operators to use `!gen`)
- `GENERATE_MAX_LOOPS=2` — max images per user turn. low cap because gen is slow (~30-90 sec each)

**when does the bot emit [GENERATE] vs just describe?**

| operator says | what happens |
|---|---|
| "show me her at the beach" | emits `[GENERATE]:`, image cooks, posts to chat |
| "what does she look like" | describes verbally, no generation |
| (uploads an image) | vision model reads + describes — no generation |
| "make another one" | emits `[GENERATE]:` again (up to MAX_LOOPS) |
| (after 2 gens in a row) | bot stops emitting sentinel until next user msg |

**explicit `!gen` still works** in parallel — use it when u want precise control over the prompt without LLM rewriting. natural-language is for fluid conversation, `!gen` for prompt engineering.

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
| `!tts` | whitelist | toggle ElevenLabs voice on/off — see §5.3 |
| `!tts <text>` | whitelist | speak text immediately (no LLM, direct to voice) |
| `!argue <convo>` | whitelist | argument analyser via anthropic |
| `!gen <prompt>` | whitelist | local ComfyUI image generation — see §5.5 |
| `!gen --seed <int> <prompt>` | whitelist | same, with fixed seed for reproducible composition |

### 7.3 trigger words (for non-whitelist roles)

if a user has a role in `AUTHORISED_ROLES`, they can address me without `@` by starting their msg with: `robot`, `mrrobot`, `mr robot`, `servitor`, `spirit`, `machine`, `omnissiah`, `omnisiah` followed by a space, comma or colon.

```
machine, sitrep
servitor: write me a port scanner
spirit, what's MITRE T1021
```

---

## 8. editing my prompt (changing who i am)

i have a two-file prompt architecture:

```
SYSTEM_PROMPT_BASELINE        ← baked into mrrobot.py source (public, generic template)
        ↓ fallback only
system_prompt.txt             ← live editable, gitignored (private to ur rig)
```

i read `system_prompt.txt` on startup. if it's missing or empty, i fall back to the baked baseline — i can NEVER be bricked by deleting the file.

### 8.1 first-time setup — fill in THE FILE

on a fresh clone, ur `system_prompt.txt` will be either missing OR a copy of the baseline (depends on whether u ran `[R]` or `--dump-baseline` first). EITHER WAY, the baseline contains a `THE FILE — REPLACE THIS BLOCK` section with a placeholder, not real bio data.

**u must fill that block in.** what to put there:

```
THE FILE — don't make me repeat it:
- ur name / callsign / what to call u
- age, location, anything else u don't want to retype
- mission / goal chain (escape route, north star)
- mental state context (sobriety, recovery, medical) — gets read back in WITNESS MODE
- ur network (people u care about, lost friendships)
- concrete receipts — specific wins, ship-dates, sustained efforts
  (without these, WITNESS MODE turns into generic motivation which u'll reject as fake)
```

the fuller u make THE FILE, the better i can read u back to u when u forget. without it, im just a foul-mouthed but generic assistant.

### 8.2 via the launcher menu

run `start_servitor.bat`, the menu pops:
- `[E]` opens `system_prompt.txt` in notepad. u edit, save, close. launcher waits till u close, then continues.
- `[V]` prints the loaded prompt to console.
- `[R]` factory-resets the file from the embedded baseline. **WARNING: this nukes ur tuning.** back up first.

edits take effect on **next launch** — no hot reload. the launcher kills the old me before relaunching so changes go in clean.

### 8.3 backup before [R]

`[R]` overwrites `system_prompt.txt` with the generic baseline. if u've tuned ur prompt over weeks, that's gone in one click. before pressing R, take a timestamped backup:

```powershell
# windows:
Copy-Item system_prompt.txt "system_prompt.$(Get-Date -Format yyyy-MM-dd).backup.txt"
```

```bash
# linux/mac:
cp system_prompt.txt "system_prompt.$(date +%Y-%m-%d).backup.txt"
```

backup files match the `system_prompt.*.txt` glob in `.gitignore`, so they never accidentally commit.

### 8.4 via cli

```bash
python mrrobot.py --show-prompt     # print what i'd load (sidecar or baseline)
python mrrobot.py --dump-baseline   # overwrite system_prompt.txt with baseline
```

### 8.5 the gitignore note (privacy critical)

`system_prompt.txt` is in `.gitignore`. it's private to ur rig — contains ur bio, ur receipts, the file SERVITOR holds on u. **never commit it to github**, especially if ur repo is public.

only the baked-in baseline ships to github, and that's a generic template with the personal block stripped. ur tuning stays on ur machine. always. clone the repo on a second machine = u start fresh and re-fill THE FILE there.

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
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | ollama endpoint — can be remote IP (e.g. `http://192.168.1.10:11434/api/chat`). remote requires port 11434 open on that machine's firewall and `OLLAMA_HOST=0.0.0.0` set before starting ollama |
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
| `REQUEST_TIMEOUT` | `120` | ollama HTTP timeout (sec). 0/none/-1 = wait forever |
| `VISION_MAX_DIM` | `1536` | pre-resize image attachments to this max dim (0 = disable) |
| `COMFY_HOST` | `http://localhost:8188` | where ComfyUI HTTP API is reachable (for !gen) |
| `COMFY_TEMPLATE_PATH` | `gen_template.json` | path to ComfyUI API-format workflow template |
| `COMFY_TIMEOUT_SEC` | `300` | max wait per !gen call |
| `COMFY_POLL_INTERVAL` | `1.0` | how often to poll /history for completion |
| `TRIGGER_TOKEN` | `sks_woman, woman` | auto-prepended to !gen prompts if missing |
| `GENERATE_ENABLED` | `true` | enable natural-language gen via `[GENERATE]:` sentinel — see §5.5.1 |
| `GENERATE_MAX_LOOPS` | `2` | max image generations per single user turn |
| `EL_API_KEY` | (empty) | ElevenLabs API key — https://elevenlabs.io > Profile > API Key |
| `EL_VOICE_ID` | (empty) | ElevenLabs voice ID — copy from voice URL on elevenlabs.io |
| `EL_STABILITY` | `0.30` | voice consistency: 0=expressive/varied, 1=robotic. lower = more human-sounding |
| `EL_SIMILARITY` | `0.80` | how close to the original voice clone (0.75-0.85 is the sweet spot) |
| `EL_STYLE` | `0.55` | style exaggeration: 0=flat, 1=theatrical. CAPS text adds 0.25 automatically |
| `EL_SPEAKER_BOOST` | `true` | extra voice clarity enhancement |

---

## 11. file layout

```
mrrobot/
  mrrobot.py            # me. has SYSTEM_PROMPT_BASELINE fallback baked in
  argue.py              # !argue command — argument analyser via anthropic
  comfyui_bridge.py     # !gen command — ComfyUI HTTP API client (async)
  gen_template.json     # ComfyUI API-format workflow template (hot-editable)
  web_search.py         # duckduckgo wrapper for the [WEBSEARCH] sentinel
  system_prompt.txt     # ur live editable prompt — gitignored, private
  setup.bat             # first-time setup: venv + deps + .env + network check
  start_servitor.bat    # launcher: prompt menu + ollama warmup + prereq checks + bot start
                        # auto-reads MODEL_NAME / VISION_MODEL_NAME from .env
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

if u ever rebuild me from a fresh rig — new laptop, runpod, friend's pc, whatever — this is the full walkthrough. nothing skipped. step 13.3 (discord portal) is the part everyone forgets, so it's spelled out clickbyclick.

### 13.1 ollama + the models

```bash
# install ollama (one-time per machine)
#   windows:  https://ollama.com/download → OllamaSetup.exe
#   linux:    curl -fsSL https://ollama.com/install.sh | sh
#   mac:      brew install ollama

# start the ollama daemon (must be running before i boot)
ollama serve

# pull the coder model (~4.7 GB, the brain)
ollama pull huihui_ai/qwen2.5-coder-abliterate:7b

# optional: local vision model (only if u want offline image analysis on this rig)
ollama pull huihui_ai/qwen2.5-vl-abliterated:7b

# verify
ollama list
# should list both models above
```

### 13.2 python env

```bash
git clone https://github.com/rainfantry/mrrobot.git
cd mrrobot
```

**windows:** double-click `setup.bat` — handles venv, pip, .env, and all checks automatically.

**linux/mac (manual):**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # fill in DISCORD_BOT_TOKEN + WHITELIST_USERS at minimum
```

### 13.3 discord developer portal — the part nobody documents properly

this is where every fresh deploy dies. follow exact steps. screenshots in ur head: discord developer portal = the dashboard where u register apps. ur bot is one of those apps.

#### 13.3.1 create the application

1. open **https://discord.com/developers/applications** in browser
2. log in with the discord account that will OWN the bot (this is ur account — the bot is registered under ur user)
3. click **"New Application"** (top right, blue button)
4. name it whatever (e.g. `SERVITOR`, `mrrobot`, `machine-spirit`). doesn't have to match anything in code.
5. tick the ToS box, click **Create**

ur in the app dashboard now.

#### 13.3.2 bot tab — generate token + enable intents

1. left sidebar → click **"Bot"**
2. **token area** at top:
   - click **"Reset Token"** button (yes even on first setup — there's no "show" option, only reset-then-copy)
   - confirm the reset
   - the new token appears ONCE — copy it immediately. if u lose it u have to reset again.
   - token looks like `MTIzNDU2Nzg5MDEyMzQ1Njc4OTA.GxYz.aBcDeFgHiJkLmNoPqRsTuVwXyZ`
   - **save it** — this goes in `.env` as `DISCORD_BOT_TOKEN` (step 13.4)
   - this token is a password — anyone with it can puppet ur bot. don't commit it. don't paste it in screenshots.

3. scroll down to **"Privileged Gateway Intents"** section:
   - **MESSAGE CONTENT INTENT** → toggle ON (required so i can read what u type)
   - **SERVER MEMBERS INTENT** → toggle ON (required so whitelist + role matching works)
   - **PRESENCE INTENT** → leave OFF (not used)
   - scroll to bottom of page, click **"Save Changes"** (the green bar pops up bottom of screen)

4. optional cosmetic stuff on this page:
   - **Public Bot** toggle → leave ON for ur own server use. turn OFF if u want to prevent random people inviting it to their servers
   - upload an avatar if u want — affects how i show in discord member list

#### 13.3.3 OAuth2 → URL Generator — making the invite link

1. left sidebar → expand **"OAuth2"** → click **"URL Generator"**
2. **scopes** section (top): tick ONE box → `bot`
3. **bot permissions** section appears below: tick these:
   - **Send Messages** (required — i need this to reply)
   - **Read Message History** (required — for memory + reply context)
   - **Add Reactions** (required — for 🛑 ⏭️ 💤 feedback emojis)
   - **Attach Files** (optional — only needed if u want me to upload generated files)
   - **Embed Links** (optional — for richer link previews)
   - **Use External Emojis** (optional — if u want server custom emojis to render)
4. scroll to bottom → **"Generated URL"** field — copy that whole URL
   - looks like `https://discord.com/oauth2/authorize?client_id=123...&permissions=274877975616&scope=bot`

#### 13.3.4 invite the bot to ur server

1. paste the URL from 13.3.3 into a browser address bar, hit enter
2. discord shows an "Add to Server" page:
   - dropdown: pick the server u want the bot in
   - (u need **Manage Server** permission on that server)
3. shows the permissions u're granting → click **"Authorize"**
4. solve CAPTCHA if it pops
5. ✓ bot now appears in the server's member list — but **offline** (grey dot) until u actually run me

if u screwed up permissions, just paste the URL again with corrected scopes — invite will overwrite.

### 13.4 .env configuration

```bash
cp .env.example .env
# or on windows:
copy .env.example .env
```

edit `.env` with the values u collected:

```ini
# minimum required for first boot:
DISCORD_BOT_TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4OTA.GxYz.actualToken...
WHITELIST_USERS=ur_discord_username_lowercase

# optional but recommended:
ANTHROPIC_API_KEY=sk-ant-api03-yourkey...  # for vision + !argue cloud routes
VISION_MODEL_NAME=anthropic:claude-haiku-4-5  # cloud vision (recommended for 4GB GPU)
```

ur discord username is the lowercase handle (e.g. `your.handle123`), NOT the server nickname. find it in discord: User Settings → My Account → Username.

> **SECRETS SAFETY — don't fuck this up:**
> - `.env` is in `.gitignore` for a reason. NEVER commit it. NEVER paste it in screenshots / pastebins.
> - Discord tokens grant FULL bot control to anyone who has them. If u leak one, immediately reset via developer portal (13.3.2) and update `.env`.
> - Anthropic API keys are billed per use. A leaked key = someone else racking up charges on ur account.
> - On `git add`, double-check `git status` shows the bot will NEVER stage `.env` (gitignore handles it, but verify).
> - The bot fails fast on startup if `DISCORD_BOT_TOKEN` is missing or still the placeholder value — u'll see a banner pointing back to this section.

### 13.5 fill in THE FILE (one-time, before first boot)

the embedded baseline is generic. for SERVITOR to actually witness u, u need to fill in `system_prompt.txt` with ur own bio.

```bash
# windows:
python mrrobot.py --dump-baseline      # writes the generic baseline to system_prompt.txt
notepad system_prompt.txt              # open and edit
```

inside the file, find the `THE FILE — REPLACE THIS BLOCK` section. replace it with ur actual bio:
- name / callsign
- age / location
- mission (what ur working toward)
- mental state notes (sobriety, recovery — gets read back in WITNESS MODE)
- ur network (key people in ur life)
- concrete receipts (specific wins, dates, sustained efforts)

see section 8.1 for what makes a good FILE block. save the file, close notepad. don't commit it (gitignored).

### 13.6 boot + verify

```bash
# windows:
start_servitor.bat

# linux/mac:
source venv/bin/activate
ollama serve &     # if not already running
python mrrobot.py
```

in discord:
1. the bot's status dot should turn **green** in member list within ~5 sec
2. type a msg in a channel where the bot has access AND ur whitelisted
3. i should reply within ~3-10 sec depending on local LLM speed

if the bot exits immediately with a banner about `DISCORD_BOT_TOKEN not set`, u didn't fill in `.env` properly. go back to 13.4.

### 13.7 first-boot troubleshooting

| symptom | cause | fix |
|---|---|---|
| `Improper token has been passed` | wrong token in `.env`, OR token has whitespace/newline around it | reset token in dev portal, copy fresh, paste cleanly into `.env` |
| `PrivilegedIntentsRequired` error | u didn't enable MESSAGE CONTENT / SERVER MEMBERS in dev portal | go back to 13.3.2 step 3, toggle them ON, save |
| bot status stays offline / grey | token wrong OR ollama not running | check `ollama list` returns models; check `.env` has clean token |
| bot online but ignores u | u're not in `WHITELIST_USERS`, OR u're using wrong username (server nick vs actual username) | check User Settings → My Account → Username (the lowercase one) |
| `Missing Access` when sending | bot's server role is below the channel's required role | server settings → roles → drag bot's role higher |
| `Cannot send messages in this channel` | bot wasn't invited with Send Messages permission | re-run 13.3.3 with all required perms ticked, re-invite |
| `ConnectionRefusedError` on ollama call | `ollama serve` not running | run `ollama serve` in a separate terminal |
| `404 model not found` from ollama | u didn't `ollama pull` the model in 13.1 | `ollama pull huihui_ai/qwen2.5-coder-abliterate:7b` |
| bot replies "no idea" to everything | model name typo in `.env` `MODEL_NAME=` — falling back to wrong model | check spelling matches `ollama list` output exactly |

### 13.8 second machine deploy (the fast path)

once one machine works, replicating on a second machine (e.g. runpod, work laptop):

1. `git clone https://github.com/rainfantry/mrrobot.git` + 13.2 (python env)
2. copy `.env` from first rig to second (carry over DISCORD_BOT_TOKEN, WHITELIST_USERS, ANTHROPIC_API_KEY — these are user/server-bound, not rig-bound)
3. `ollama pull` the models on the new rig (each rig needs its own model files)
4. `start_servitor.bat`

ONE caveat: discord only lets one connection per bot token at a time. if u start me on machine A then on machine B with the same token, A disconnects. either run me on one rig at a time, OR register a second discord app + bot for the second rig (10 min, follow 13.3 again).

---

## 14. closing notes (from me to u)

ur file is loaded. ur receipts are held. when u forget who u are, type something and i'll read it back to u.

i run when u start me. i sleep when u kill me. i dont leak. i dont report up. nothing i hear leaves the rig unless u explicitly attach an image and have cloud vision on, OR u type `!argue`. text + memory + ur file = local. always.

if i ever come up wrong — voice off, persona drifted, sentinel broken — first move is `[V]` in the launcher to read the loaded prompt. second move is `[R]` to factory reset. ur baseline is permanent in `mrrobot.py`. it cant be lost.

ur not alone. the council is up.

— S.

---

*license: private. dont fork. no contributions. mine.*

---

## TODO — Release Blackops

_Automated read-only assessment — what a full public-release pass would do for this repo. Suggestions only; nothing above has been changed or removed._

- [ ] Audit git history for AI/Claude attribution; scrub if any is found.
- [ ] Add discovery topics for SEO (`gh repo edit --add-topic ...`, up to 20).
- [ ] Cut a tagged release (`v1.0.0`); attach a build artifact if this ships a binary/app.
- [ ] Add a screenshot or diagram to the README if there's a GUI or visual output.
- [ ] Verify a clean from-scratch build/run against the README quick start (produce a real artifact, don't trust the docs).
- [ ] If this is a desktop app, make a self-contained build (bundle runtime assets/models into the binary; confirm it runs with no external files).

<sub>Workflow: https://github.com/rainfantry/release-blackops-skill</sub>
