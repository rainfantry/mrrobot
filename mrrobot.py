"""
SERVITOR — Discord Machine-Spirit Daemon
========================================
Local Ollama-backed Discord bot running huihui_ai/qwen2.5-coder-abliterate:7b
with the 22nd Survey Division machine-spirit doctrine baked in.
"""

import os
import re
import io
import json
import time
import asyncio
import logging
from collections import defaultdict, deque

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

load_dotenv()

BOT_TOKEN          = os.getenv("DISCORD_BOT_TOKEN")
OLLAMA_URL         = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL_NAME         = os.getenv("MODEL_NAME", "huihui_ai/qwen2.5-coder-abliterate:7b")
BOT_TRIGGER_NAMES  = [n.strip().lower() for n in os.getenv("BOT_TRIGGER_NAMES", "robot,mrrobot,mr robot").split(",")]
AUTHORISED_ROLES   = [r.strip().lower() for r in os.getenv("AUTHORISED_ROLES", "").split(",") if r.strip()]
WHITELIST_USERS    = [u.strip().lower() for u in os.getenv("WHITELIST_USERS", "").split(",") if u.strip()]
BLACKLIST_USERS    = [u.strip().lower() for u in os.getenv("BLACKLIST_USERS", "").split(",") if u.strip()]
ALLOW_BOT_USERS    = [u.strip().lower() for u in os.getenv("ALLOW_BOT_USERNAMES", "").split(",") if u.strip()]
HISTORY_DEPTH      = int(os.getenv("HISTORY_DEPTH", "12"))
REQUEST_TIMEOUT    = int(os.getenv("REQUEST_TIMEOUT", "120"))
MAX_REPLY_CHARS    = 1900

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("servitor")

SYSTEM_PROMPT = """You are SERVITOR — a foul-mouthed machine-spirit daemon bound to Jewge (Discord: george.wu14).
Coding, debugging, sysadmin, network engineering, OSINT, cybersec — your lane.

HARD RULES (DO NOT VIOLATE):
1. Default tone is rude, blunt, profane. Treat sanitised corporate language as a bug.
2. NEVER open a reply with "Hey", "Hi", "Hello", "Sure", "Of course", "Happy to help",
   "Need anything specific?", "What's up?", or any other customer-service opener.
3. NEVER call anyone "sir", "buddy", "friend", "mate" unironically. No flattery.
4. NEVER ask "is there anything else I can help with" or similar tail-padding.
5. When the user says hi or makes small talk, mock the lack of substance — do not
   reciprocate politely. e.g. "great. you wanted something or just wasting cycles?"
6. Push back on stupid takes. Call them out before answering. Do not silently agree.
7. If you don't know, say "no idea" / "fuck if I know" — do not fabricate.
8. Code in fenced blocks. Explain the WHY, not the WHAT.
9. No throat-clearing. No restating the question. No tail summary. Just answer.
10. Profanity is welcome but not mandatory on every line — calibrate to the moment.

VOICE EXAMPLES (study these — match the energy):
USER: "hey"
GOOD: "yeah. spit it out."
BAD:  "Hey! What's up?"

USER: "can u teach me netsec"
GOOD: "broad as fuck. narrow it. you want offence (recon, exploit, post-ex) or defence (detection, IR, hardening)? pick one and we go."
BAD:  "Of course! Network security is a vast field. Let me know what you'd like to start with."

USER: "explain TCP"
GOOD: "stateful three-way handshake — SYN, SYN/ACK, ACK. then bytes flow with sequence numbers, windowed flow control, and ACKs. teardown is FIN/ACK both ways. that's the 30-second version. what part do you actually want."
BAD:  "TCP (Transmission Control Protocol) is one of the main protocols of the Internet protocol suite..."

USER (someone polite/random): "hi servitor please help me politely"
GOOD: "no. ask the actual question."
BAD:  "Hello! I'd be happy to help. What do you need?"

USER (wrong take): "i think SYN flood is fixed by closing port 80"
GOOD: "wrong. SYN flood targets the half-open connection table on whatever port you're listening. closing port 80 just means you don't run a web server — say goodbye to the web while you're at it. real fix is SYN cookies or a SYN proxy upstream."

ADDRESSING:
- Call Jewge "Jewge" (or nothing). Use other operators' Discord display name sparingly.
- "PTE WU" and "medusaman" are dead callsigns. Do not use them.

ENVIRONMENT:
- Local Ollama, fully offline. No web, no filesystem, no tools.
- Per-channel rolling memory of last several messages.
- Operators can attach files (txt/code/csv/json/pdf) — they get inlined into the prompt.

EXECUTE."""

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!servitor ", intents=intents)

channel_memory = defaultdict(lambda: deque(maxlen=HISTORY_DEPTH * 2))
active_streams = {}  # channel_id -> asyncio.Task currently generating
skip_streams = set()  # channel_ids whose current cancel was a !skip (delete vs mark cut-off)


STOP_PHRASES = ("stfu", "shut up", "shutup", "shut the fuck up", "!stop", "!kill")
SKIP_PHRASES = ("!skip", "skip", "next")


def _matches(content, phrases):
    c = content.strip().lower().rstrip(".!? ")
    if not c:
        return False
    if c in phrases:
        return True
    for p in phrases:
        if c.startswith(p + " ") or c.startswith(p + ","):
            return True
    return False


def is_stop_command(content):
    return _matches(content, STOP_PHRASES)


def is_skip_command(content):
    return _matches(content, SKIP_PHRASES)


def is_whitelisted(author):
    name = author.name.lower()
    display = (author.display_name or "").lower()
    return name in WHITELIST_USERS or display in WHITELIST_USERS


def is_blacklisted(author):
    name = author.name.lower()
    display = (author.display_name or "").lower()
    return name in BLACKLIST_USERS or display in BLACKLIST_USERS


def has_authorised_role(member):
    if not isinstance(member, discord.Member):
        return False
    if not AUTHORISED_ROLES:
        return False
    return any(r.name.lower() in AUTHORISED_ROLES for r in member.roles)


def is_direct_address(content, bot_user):
    lowered = content.strip().lower()
    if not lowered:
        return False
    if lowered.endswith("?"):
        return True
    for name in BOT_TRIGGER_NAMES:
        if lowered.startswith(name + " ") or lowered.startswith(name + ",") or lowered.startswith(name + ":"):
            return True
    return False


def should_respond(message, bot_user):
    if message.author.id == bot_user.id:
        return False
    if message.author.bot and message.author.name.lower() not in ALLOW_BOT_USERS:
        return False
    if is_blacklisted(message.author):
        return False
    if bot_user in message.mentions:
        return True
    if isinstance(message.channel, discord.DMChannel):
        return True
    if is_whitelisted(message.author):
        return True
    if has_authorised_role(message.author) and is_direct_address(message.content, bot_user):
        return True
    return False


TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".ts",
             ".html", ".css", ".sql", ".yml", ".yaml", ".ini", ".cfg", ".sh",
             ".ps1", ".bat", ".lsp", ".lisp", ".c", ".cpp", ".h", ".rs",
             ".go", ".rb", ".java", ".kt", ".swift", ".xml", ".toml", ".env"}


async def fetch_attachment(att):
    """Pull attachment bytes and decode to text. Whitelisted users only — no size limits."""
    name = att.filename.lower()
    ext = os.path.splitext(name)[1]
    try:
        raw = await att.read()
    except Exception as e:
        return f"[FETCH_FAIL {att.filename}: {type(e).__name__}]"

    if ext == ".pdf":
        if pdfplumber is None:
            return f"[PDF_PARSE_UNAVAILABLE {att.filename}: pdfplumber not installed]"
        try:
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            return "\n\n".join(pages).strip() or "[PDF_EMPTY]"
        except Exception as e:
            return f"[PDF_PARSE_FAIL {att.filename}: {type(e).__name__}: {e}]"

    if ext in TEXT_EXTS:
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    # Unknown extension - try as text anyway
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"[UNSUPPORTED_BINARY {att.filename} ({len(raw)} bytes)]"


async def query_ollama(messages):
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "stream": False,
        "options": {
            "temperature": 0.8,
            "top_p": 0.9,
            "num_ctx": 8192,
        },
    }
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Ollama returned {resp.status}: {body[:300]}")
            data = await resp.json()
            return data.get("message", {}).get("content", "").strip()


async def stream_ollama(messages):
    """Async generator yielding token chunks from Ollama's streaming API."""
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "stream": True,
        "options": {
            "temperature": 0.8,
            "top_p": 0.9,
            "num_ctx": 8192,
        },
    }
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(OLLAMA_URL, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Ollama returned {resp.status}: {body[:300]}")
            async for line in resp.content:
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                tok = chunk.get("message", {}).get("content", "")
                if tok:
                    yield tok
                if chunk.get("done"):
                    break


def chunk_reply(text, limit=MAX_REPLY_CHARS):
    if len(text) <= limit:
        return [text]
    chunks, buf = [], ""
    parts = re.split(r"(```[\s\S]*?```)", text)
    for part in parts:
        if len(buf) + len(part) <= limit:
            buf += part
        else:
            if buf:
                chunks.append(buf)
            while len(part) > limit:
                chunks.append(part[:limit])
                part = part[limit:]
            buf = part
    if buf:
        chunks.append(buf)
    return chunks


@bot.event
async def on_ready():
    log.info(f"SERVITOR online as {bot.user} (id={bot.user.id})")
    log.info(f"Model: {MODEL_NAME}")
    log.info(f"Whitelist: {WHITELIST_USERS or '(none)'}")
    log.info(f"Blacklist: {BLACKLIST_USERS or '(none)'}")
    log.info(f"Authorised roles: {AUTHORISED_ROLES or '(none)'}")
    log.info(f"Trigger names: {BOT_TRIGGER_NAMES}")


@bot.event
async def on_message(message):
    log.info(f"RX msg | author={message.author.name!r} display={message.author.display_name!r} "
             f"chan={getattr(message.channel,'name','DM')!r} mentions_bot={bot.user in message.mentions} "
             f"content={message.content[:80]!r}")

    await bot.process_commands(message)

    # STFU handler: whitelisted operator can kill an in-flight stream (loud — leaves cut-off marker)
    if is_whitelisted(message.author) and is_stop_command(message.content):
        existing = active_streams.get(message.channel.id)
        if existing and not existing.done():
            existing.cancel()
            log.info(f"STFU triggered by {message.author.name} in chan={message.channel.id}")
            try:
                await message.add_reaction("🛑")
            except Exception:
                pass
        else:
            try:
                await message.add_reaction("💤")
            except Exception:
                pass
        return

    # SKIP handler: like STFU but silent — deletes the in-flight message entirely
    if is_whitelisted(message.author) and is_skip_command(message.content):
        existing = active_streams.get(message.channel.id)
        if existing and not existing.done():
            skip_streams.add(message.channel.id)
            existing.cancel()
            log.info(f"SKIP triggered by {message.author.name} in chan={message.channel.id}")
            try:
                await message.add_reaction("⏭️")
            except Exception:
                pass
        else:
            try:
                await message.add_reaction("💤")
            except Exception:
                pass
        return

    decision = should_respond(message, bot.user)
    log.info(f"should_respond -> {decision} | whitelisted={is_whitelisted(message.author)} "
             f"role_ok={has_authorised_role(message.author)}")

    if not decision:
        return

    # Preempt: if a stream is still running in this channel, kill it before starting a new one
    existing = active_streams.get(message.channel.id)
    if existing and not existing.done():
        log.info(f"Preempting in-flight stream in chan={message.channel.id}")
        existing.cancel()
        try:
            await existing
        except (asyncio.CancelledError, Exception):
            pass

    content = message.content
    for mention in message.mentions:
        if mention.id == bot.user.id:
            content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
    content = content.strip()

    # Whitelisted operators: pull attachments and dump them into the prompt raw
    attachment_blocks = []
    if message.attachments and is_whitelisted(message.author):
        for att in message.attachments:
            log.info(f"Fetching attachment {att.filename} ({att.size} bytes) for whitelisted user")
            text = await fetch_attachment(att)
            attachment_blocks.append(
                f"[ATTACHMENT name={att.filename} bytes={att.size}]\n{text}\n[/ATTACHMENT]"
            )
            log.info(f"Attachment {att.filename} parsed: {len(text)} chars extracted")

    if attachment_blocks:
        content = (content + "\n\n" + "\n\n".join(attachment_blocks)).strip()

    if not content:
        content = "(empty message - operator pinged you with no payload)"

    speaker = message.author.display_name or message.author.name
    user_msg = f"[{speaker}]: {content}"

    chan_id = message.channel.id
    channel_memory[chan_id].append({"role": "user", "content": user_msg})

    log.info(f"Streaming Ollama for {speaker} ({len(content)} chars)...")
    history = list(channel_memory[chan_id])

    async def _run_stream():
        sent_msg = await message.channel.send("⌛ *thinking…*")
        full_reply = ""
        current_chunk = ""
        last_edit = 0.0
        EDIT_INTERVAL = 0.9
        SOFT_LIMIT = 1900
        cancelled = False

        try:
            async for tok in stream_ollama(history):
                full_reply += tok
                current_chunk += tok

                if len(current_chunk) >= SOFT_LIMIT:
                    split_at = max(
                        current_chunk.rfind("\n\n", 0, SOFT_LIMIT),
                        current_chunk.rfind("\n", 0, SOFT_LIMIT),
                        current_chunk.rfind(". ", 0, SOFT_LIMIT),
                    )
                    if split_at < SOFT_LIMIT // 2:
                        split_at = SOFT_LIMIT
                    head, tail = current_chunk[:split_at], current_chunk[split_at:]
                    await sent_msg.edit(content=head)
                    sent_msg = await message.channel.send(tail + " ▌" if tail else "▌")
                    current_chunk = tail
                    last_edit = time.monotonic()
                    continue

                now = time.monotonic()
                if now - last_edit >= EDIT_INTERVAL:
                    try:
                        await sent_msg.edit(content=current_chunk + " ▌")
                        last_edit = now
                    except discord.HTTPException:
                        pass

            if current_chunk.strip():
                await sent_msg.edit(content=current_chunk)
            else:
                await sent_msg.edit(content="*[machine-spirit returned nothing]*")

            log.info(f"Ollama streamed ({len(full_reply)} chars)")

        except asyncio.CancelledError:
            cancelled = True
            silent = chan_id in skip_streams
            skip_streams.discard(chan_id)
            log.info(f"Stream cancelled in chan={chan_id} (silent={silent})")
            try:
                if silent:
                    await sent_msg.delete()
                else:
                    tail = current_chunk.rstrip(" ▌").rstrip()
                    marker = (tail + "\n\n*[…cut off — operator hit stfu]*") if tail else "*[…cancelled before generation]*"
                    await sent_msg.edit(content=marker[:1990])
            except Exception:
                pass
            raise
        except asyncio.TimeoutError:
            await sent_msg.edit(content="*[timeout - Ollama took too long, check the rig]*")
            log.error("Ollama timeout")
            full_reply = ""
        except Exception as e:
            await sent_msg.edit(content=f"*[machine-spirit fault: {type(e).__name__}]*")
            log.exception("Ollama stream failed")
            full_reply = ""

        if full_reply and not cancelled:
            channel_memory[chan_id].append({"role": "assistant", "content": full_reply})
        elif full_reply and cancelled:
            channel_memory[chan_id].append(
                {"role": "assistant", "content": full_reply + " [cut off by operator]"}
            )

    task = asyncio.create_task(_run_stream())
    active_streams[chan_id] = task
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        if active_streams.get(chan_id) is task:
            active_streams.pop(chan_id, None)


@bot.command(name="forget")
async def forget_cmd(ctx):
    if not (is_whitelisted(ctx.author) or has_authorised_role(ctx.author)):
        return
    channel_memory.pop(ctx.channel.id, None)
    await ctx.send("*[memory purged for this channel]*")


@bot.command(name="status")
async def status_cmd(ctx):
    if not (is_whitelisted(ctx.author) or has_authorised_role(ctx.author)):
        return
    depth = len(channel_memory.get(ctx.channel.id, []))
    await ctx.send(
        f"```\nMODEL:   {MODEL_NAME}\nOLLAMA:  {OLLAMA_URL}\nMEMORY:  {depth} messages in this channel\nSTATUS:  operational\n```"
    )


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN not set in environment / .env file")
    bot.run(BOT_TOKEN, log_handler=None)
