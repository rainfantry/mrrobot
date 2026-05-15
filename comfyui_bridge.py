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
    async generate_image(user_prompt: str, seed: int|None = None) -> bytes
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
COMFY_TIMEOUT_SEC   = int(os.getenv("COMFY_TIMEOUT_SEC", "300"))
COMFY_POLL_INTERVAL = float(os.getenv("COMFY_POLL_INTERVAL", "1.0"))
TRIGGER_TOKEN       = os.getenv("TRIGGER_TOKEN", "sks_woman, woman")

# === Node IDs from gen_template.json (must match) ===
NODE_POSITIVE_PROMPT = "3"   # CLIPTextEncode (positive)
NODE_KSAMPLER        = "6"   # KSampler (contains seed)


async def generate_image(
    user_prompt: str,
    seed: int | None = None,
    timeout_sec: int = COMFY_TIMEOUT_SEC,
) -> bytes:
    """
    Generate one image via ComfyUI.

    Returns PNG bytes ready for discord.File.
    Raises TimeoutError / RuntimeError on failure.
    """
    # 1. Load workflow template (re-read each call — supports hot-edit)
    with open(COMFY_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # 2. Construct full prompt — auto-prepend trigger if missing
    if TRIGGER_TOKEN and TRIGGER_TOKEN.split(",")[0].strip().lower() not in user_prompt.lower():
        full_prompt = f"{TRIGGER_TOKEN}, {user_prompt}"
    else:
        full_prompt = user_prompt

    # 3. Inject prompt + seed
    workflow[NODE_POSITIVE_PROMPT]["inputs"]["text"] = full_prompt
    if seed is None:
        seed = random.randint(0, 2**63 - 1)
    workflow[NODE_KSAMPLER]["inputs"]["seed"] = seed

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

        # 5. Poll history until our prompt_id completes
        deadline = asyncio.get_event_loop().time() + timeout_sec
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(COMFY_POLL_INTERVAL)
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
                        return await img_resp.read()
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
            png = await generate_image(test_prompt)
            out_path = Path(__file__).parent / "test_gen.png"
            out_path.write_bytes(png)
            print(f"OK — saved {out_path} ({len(png):,} bytes)")
        except Exception as e:
            print(f"FAIL: {type(e).__name__}: {e}")

    asyncio.run(_main())
