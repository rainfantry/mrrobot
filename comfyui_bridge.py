"""
ComfyUI HTTP API bridge for SERVITOR.

Loads gen_template.json, swaps in user prompt + random seed,
submits to ComfyUI's local API, polls until done, returns PNG bytes.

ComfyUI must be running with --listen 0.0.0.0 (or localhost is fine if
SERVITOR runs on same machine). Default port 8188.

Environment:
    COMFY_HOST           = http://localhost:8000   (where ComfyUI is reachable)
    COMFY_TEMPLATE_PATH  = path to gen_template.json
    COMFY_TIMEOUT_SEC    = max wait per generation, default 300
    TRIGGER_TOKEN        = "sks_woman, woman"      (auto-prepend if missing)

Public:
    async generate_image(user_prompt: str, seed: int|None = None) -> tuple[bytes, int]
        returns (png_bytes, seed_used) so caller can surface the seed for
        money-seed bookkeeping.
"""

import asyncio
import json
import os
import random
import uuid
from pathlib import Path

import aiohttp

# Load .env so this module works standalone (CLI test) AND when imported
# by mrrobot.py. python-dotenv's load_dotenv is idempotent — safe to call
# again even if mrrobot.py already ran it.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass  # dotenv not installed — env vars must be in shell env

# === Config (read from env, sensible defaults) ===
COMFY_HOST          = os.getenv("COMFY_HOST", "http://localhost:8188").rstrip("/")
COMFY_TEMPLATE_PATH = os.getenv(
    "COMFY_TEMPLATE_PATH",
    str(Path(__file__).parent / "gen_template.json"),
)
# Scene/landscape workflow — no LoRA, landscape aspect, scene-tuned sampler.
# Used by !scene command. Independent of gen_template.json.
COMFY_SCENE_TEMPLATE_PATH = os.getenv(
    "COMFY_SCENE_TEMPLATE_PATH",
    str(Path(__file__).parent / "scene_template.json"),
)
COMFY_TIMEOUT_SEC   = int(os.getenv("COMFY_TIMEOUT_SEC", "300"))
COMFY_POLL_INTERVAL = float(os.getenv("COMFY_POLL_INTERVAL", "1.0"))
TRIGGER_TOKEN       = os.getenv("TRIGGER_TOKEN", "sks_woman, woman")

# === Node IDs from gen_template.json (must match) ===
NODE_POSITIVE_PROMPT = "3"   # CLIPTextEncode (positive)
NODE_KSAMPLER        = "6"   # KSampler (contains seed)


async def _watch_progress(session, prompt_id, client_id, on_progress, timeout_sec):
    """
    Open ComfyUI WebSocket and listen for progress + completion events.

    Calls on_progress(current_step, total_steps) for every KSampler step.
    Returns True when 'executing with node=None' arrives (= prompt fully complete).
    Returns False on any failure — caller falls back to polling /history.

    ComfyUI WebSocket protocol (relevant events):
      - {"type": "progress", "data": {"value": N, "max": M, "prompt_id": "..."}}
      - {"type": "executing", "data": {"node": null, "prompt_id": "..."}}  ← completion
    """
    ws_url = COMFY_HOST.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    ws_url = f"{ws_url}/ws?clientId={client_id}"
    try:
        async with session.ws_connect(ws_url, timeout=aiohttp.ClientWSTimeout(ws_close=10)) as ws:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + timeout_sec
            while loop.time() < deadline:
                remaining = deadline - loop.time()
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=min(remaining, 60))
                except asyncio.TimeoutError:
                    return False  # ws stalled — fall back to polling
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except (ValueError, json.JSONDecodeError):
                        continue
                    msg_type = data.get("type")
                    msg_data = data.get("data") or {}
                    if msg_data.get("prompt_id") != prompt_id:
                        continue
                    if msg_type == "progress":
                        if on_progress is not None:
                            try:
                                await on_progress(
                                    int(msg_data.get("value", 0)),
                                    int(msg_data.get("max", 1)),
                                )
                            except Exception:
                                pass  # callback failure shouldn't kill gen
                    elif msg_type == "executing" and msg_data.get("node") is None:
                        return True  # prompt fully complete
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.ERROR,
                ):
                    return False
            return False
    except (aiohttp.ClientError, OSError, asyncio.TimeoutError):
        return False


async def generate_image(
    user_prompt: str,
    seed: int | None = None,
    timeout_sec: int = COMFY_TIMEOUT_SEC,
    template_path: str | None = None,
    skip_trigger: bool = False,
    on_progress=None,
) -> tuple[bytes, int]:
    """
    Generate one image via ComfyUI.

    Args:
        template_path: Override default gen_template.json (e.g. scene_template.json).
        skip_trigger: Skip TRIGGER_TOKEN auto-prepend. Used for scene/non-LoRA gen
                      where the trigger token would only pollute the prompt.
        on_progress: Optional async callable on_progress(current, total) invoked for
                     every KSampler step via ComfyUI WebSocket. Use for streaming
                     Discord progress bars. Callback failures are swallowed silently.

    Returns (png_bytes, seed_used) — caller surfaces the seed in Discord
    so operator can note money seeds.
    Raises TimeoutError / RuntimeError on failure.
    """
    # 1. Load workflow template (re-read each call — supports hot-edit)
    path = template_path or COMFY_TEMPLATE_PATH
    with open(path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # 2. Construct full prompt — auto-prepend trigger unless caller opted out
    # (scene/landscape workflows have no LoRA, so the trigger does nothing useful
    # there and just pollutes the conditioning).
    if skip_trigger:
        full_prompt = user_prompt
    elif TRIGGER_TOKEN and TRIGGER_TOKEN.split(",")[0].strip().lower() not in user_prompt.lower():
        full_prompt = f"{TRIGGER_TOKEN}, {user_prompt}"
    else:
        full_prompt = user_prompt

    # 3. Inject prompt + seed
    workflow[NODE_POSITIVE_PROMPT]["inputs"]["text"] = full_prompt
    seed_was_random = seed is None
    if seed_was_random:
        seed = random.randint(0, 2**63 - 1)
    workflow[NODE_KSAMPLER]["inputs"]["seed"] = seed
    # Print to stdout so you can see the actual seed used (useful when seed=None
    # auto-randomizes — lets you note any "money seed" results for re-use later).
    print(f"[comfyui_bridge] prompt={full_prompt[:80]!r} seed={seed} ({'random' if seed_was_random else 'fixed'})")

    # 4. Submit to ComfyUI
    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{COMFY_HOST}/prompt", json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    raise RuntimeError(f"ComfyUI POST /prompt {resp.status}: {err[:300]}")
                data = await resp.json()
        except aiohttp.ClientConnectorError:
            raise RuntimeError(f"can't reach ComfyUI at {COMFY_HOST} — is it running?")

        prompt_id = data["prompt_id"]

        # 5a. Watch progress via WebSocket — preferred path. Streams step-level
        # progress to on_progress callback and signals completion when the prompt
        # finishes executing. Falls through to polling if WS fails or stalls.
        ws_completed = await _watch_progress(
            session, prompt_id, client_id, on_progress, timeout_sec,
        )

        # 5b. Fetch from /history. If WS confirmed completion, this is typically
        # a single-shot fetch. If WS fell through, poll normally until the run
        # appears in history.
        if ws_completed:
            deadline = asyncio.get_event_loop().time() + 15
            poll_interval = 0.0  # fetch immediately, no warmup sleep
        else:
            deadline = asyncio.get_event_loop().time() + timeout_sec
            poll_interval = COMFY_POLL_INTERVAL

        first_iteration = True
        while asyncio.get_event_loop().time() < deadline:
            if not first_iteration or poll_interval > 0:
                await asyncio.sleep(COMFY_POLL_INTERVAL if not first_iteration else poll_interval)
            first_iteration = False
            try:
                async with session.get(f"{COMFY_HOST}/history/{prompt_id}") as resp:
                    if resp.status != 200:
                        continue
                    history = await resp.json()
            except aiohttp.ClientError:
                continue

            run = history.get(prompt_id)
            if not run:
                continue
            outputs = run.get("outputs", {})

            # Find the SaveImage node's emitted image
            for node_id, node_out in outputs.items():
                imgs = node_out.get("images")
                if not imgs:
                    continue
                meta = imgs[0]
                params = {
                    "filename": meta["filename"],
                    "subfolder": meta.get("subfolder", ""),
                    "type": meta.get("type", "output"),
                }
                async with session.get(f"{COMFY_HOST}/view", params=params) as img_resp:
                    if img_resp.status == 200:
                        return await img_resp.read(), seed
                    raise RuntimeError(f"ComfyUI /view returned {img_resp.status}")

        raise TimeoutError(f"ComfyUI generation didn't complete within {timeout_sec}s")


# === CLI test mode ===
# Run `python comfyui_bridge.py "test prompt"` to verify ComfyUI is reachable
if __name__ == "__main__":
    import sys
    test_prompt = sys.argv[1] if len(sys.argv) > 1 else "at golden hour park"

    async def _main():
        print(f"Testing with prompt: {test_prompt!r}")
        try:
            png, seed_used = await generate_image(test_prompt)
            out_path = Path(__file__).parent / "test_gen.png"
            out_path.write_bytes(png)
            print(f"OK — saved {out_path} ({len(png):,} bytes) seed={seed_used}")
        except Exception as e:
            print(f"FAIL: {type(e).__name__}: {e}")

    asyncio.run(_main())
