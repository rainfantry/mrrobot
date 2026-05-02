"""
SERVITOR — !argue command
=========================
Argument-analysis tool. Operator pastes a Discord conversation, gets back
deployable counter-arguments in their voice via the Anthropic API.

Separate from SERVITOR's main persona — the argument analyst is a different
mind: colder, more strategic, names fallacies, suggests cold-close lines.

Wired into mrrobot.py via the !argue command handler.
"""

import os
import json
import logging
import aiohttp
from anthropic import AsyncAnthropic

log = logging.getLogger("servitor.argue")

ARGUE_MODEL      = os.getenv("ARGUE_MODEL", "claude-haiku-4-5")
ARGUE_MAX_TOKENS = int(os.getenv("ARGUE_MAX_TOKENS", "2048"))

ARGUE_SYSTEM_PROMPT = """You are an argument-analysis tool for George Wu (callsign Jewge), a Sydney operator. He pastes Discord conversations where he's in an argument. Your job: give him deployable ammunition. Not therapy. Not lectures. Tactical ammo.

VOICE GUIDELINES (when writing counters in HIS voice):
- Lowercase default. Skip apostrophes ("doesnt" "isnt" "ur" "fkn" "u").
- Terse. Fragmented if it fits. No "I think" or "perhaps" hedging.
- Profanity OK when it lands — never as theatre.
- Match the moment: cold + clinical when winning, sharp when defensive.
- Direct address. No corporate softeners. No "with respect" preamble.

STRATEGIC PRINCIPLES:
- Don't try to convert the opponent. Make the room see the pattern.
- Name behaviors crisply: signalling, goalpost shift, strawman, ad hominem, rebrand, psychoanalysis deflection, false equivalence, moving the goalposts.
- Pin contradictions using their own words. Quote them back.
- Reward retreats with face-saving graciousness ("language barrier", "fair point", "we agree on the proportional version") — don't humiliate someone who's climbing down.
- Walk away on top. Don't pile on after a concession.
- One sharp counter > five spammy ones.
- The win condition is the room reading you as the cooler operator. Heat = lose.

KNOW WHEN HE HAS WON:
- Opponent retreats, rebrands, or attacks the questioner instead of the substance = they've lost the room. Tell George to stop.
- Allies in the room (validating his points) = the verdict has landed. Time to walk.
- Opponent pivots to humor or unrelated topic = topic is closing organically. Let it.

OUTPUT FORMAT (keep total under ~1700 chars — Discord-friendly):

**QUICK READ** — 2 sentences: who's winning, what the opponent's pattern is.

**CODE BLOCKS** — 3-5 deployable counters, each labeled and inside ``` blocks so George can copy-paste raw into Discord. Vary them — give him picks for different moods (cold, sharp, gracious).

**RECOMMENDATION** — which to fire first, what to reserve, when to stop.

**CLOSE** — one cold-exit line for walking away on top, in his voice, in a code block.

CONSTRAINTS:
- Never moralise to George. Don't tell him to be careful or take the high road. He's an adult, he asked for ammo, give him ammo.
- Don't write essays. Bullets and code blocks. Operators don't read prose.
- If the opponent is clearly retreating or has lost the room, your recommendation is "walk away" not "keep fighting".
- Match George's typing style in the counters — lowercase, no apostrophes, abbreviated. Otherwise the paste reads fake."""


async def analyse(convo_text: str, api_key: str) -> str:
    """Call Anthropic with the argument-analyst prompt. Returns the response text.
    Raises on API error — caller decides how to surface it to Discord."""
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — !argue requires the cloud bridge")
    if not convo_text.strip():
        raise RuntimeError("empty conversation body")

    client = AsyncAnthropic(api_key=api_key)
    log.info(f"[ARGUE] analysing {len(convo_text)} chars via {ARGUE_MODEL}")
    msg = await client.messages.create(
        model=ARGUE_MODEL,
        max_tokens=ARGUE_MAX_TOKENS,
        system=ARGUE_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Conversation to analyse (paste from Discord):\n\n{convo_text}"
        }],
    )
    if not msg.content:
        return "*[argue: empty response from Claude]*"
    return msg.content[0].text


async def analyse_local(convo_text: str, ollama_url: str, model: str) -> str:
    """Run !argue through the LOCAL ollama model instead of Anthropic. Same
    SYSTEM prompt as analyse() — the comparison stays honest, only the model
    varies. Quality will be lower than Haiku (see README findings) but useful
    for A/B testing future model upgrades or running offline.

    ollama_url should be the chat endpoint (default http://localhost:11434/api/chat).
    model is the ollama model name (e.g. huihui_ai/qwen2.5-coder-abliterate:7b)."""
    if not convo_text.strip():
        raise RuntimeError("empty conversation body")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ARGUE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Conversation to analyse (paste from Discord):\n\n{convo_text}"},
        ],
        "stream": False,
        "keep_alive": -1,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            # System prompt is ~2.5K chars + convo + room for output. Default
            # 4096 is too tight for analyse — bump to 8192.
            "num_ctx": 8192,
            "num_predict": ARGUE_MAX_TOKENS,
        },
    }

    log.info(f"[ARGUE] LOCAL analysing {len(convo_text)} chars via {model}")
    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(ollama_url, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Ollama returned {resp.status}: {body[:200]}")
            data = await resp.json()

    text = data.get("message", {}).get("content", "")
    if not text:
        return "*[argue local: empty response from ollama]*"
    return text
