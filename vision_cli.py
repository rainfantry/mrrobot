"""
Standalone vision-model CLI — runs alongside the Discord bot.

Hits Ollama's /api/chat directly with an image + prompt, streams the
description to stdout. Useful when u want fast vision analysis WITHOUT
sending the result to Discord OR while the bot is doing something else.

Usage:
    python vision_cli.py                              -> default path + prompt
    python vision_cli.py "describe the colors"        -> default path, custom prompt
    python vision_cli.py C:/path/to/img.jpg           -> custom path, default prompt
    python vision_cli.py C:/path/to/img.jpg what era  -> custom path, custom prompt

Environment (reads from .env in this folder, then OS env):
    VISION_MODEL_NAME    (default: huihui_ai/qwen2.5-vl-abliterated:3b)
    OLLAMA_URL           (default: http://localhost:11434/api/chat)
    VISION_MAX_DIM       (default: 1536, set 0 to disable resize)
    DEFAULT_VISION_PATH  (default: C:/Users/gwu07/Desktop/vision.png)
"""
import sys, os, base64, json, urllib.request, io
from pathlib import Path

# Load .env from same directory if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass

OLLAMA_URL          = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL               = os.getenv("VISION_MODEL_NAME", "huihui_ai/qwen2.5-vl-abliterated:3b")
VISION_MAX_DIM      = int(os.getenv("VISION_MAX_DIM", "1536"))
DEFAULT_VISION_PATH = os.getenv("DEFAULT_VISION_PATH", "C:/Users/gwu07/Desktop/vision.png")
DEFAULT_PROMPT      = "describe this image in detail"


def looks_like_path(s):
    """Heuristic: does this token look like a filesystem path?"""
    return "/" in s or "\\" in s or (len(s) >= 2 and s[1] == ":")


def parse_args():
    args = sys.argv[1:]
    if not args:
        return DEFAULT_VISION_PATH, DEFAULT_PROMPT
    if len(args) == 1:
        if looks_like_path(args[0]):
            return args[0], DEFAULT_PROMPT
        else:
            return DEFAULT_VISION_PATH, args[0]
    # 2+ args: first is path if pathy, rest is prompt
    if looks_like_path(args[0]):
        return args[0], " ".join(args[1:])
    else:
        return DEFAULT_VISION_PATH, " ".join(args)


def load_and_resize(path):
    """Read image file + resize via VISION_MAX_DIM if needed. Returns base64 string."""
    with open(path, "rb") as f:
        raw = f.read()
    original_size = len(raw)
    ext = os.path.splitext(path)[1].lower()
    if VISION_MAX_DIM > 0:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(raw))
            if max(img.size) > VISION_MAX_DIM:
                img.thumbnail((VISION_MAX_DIM, VISION_MAX_DIM), Image.LANCZOS)
                buf = io.BytesIO()
                fmt = "PNG" if ext == ".png" else "JPEG"
                if fmt == "JPEG" and img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(buf, format=fmt, quality=92)
                raw = buf.getvalue()
                print(f"[resized {original_size:,} -> {len(raw):,} bytes ({VISION_MAX_DIM}px max)]",
                      file=sys.stderr)
        except ImportError:
            print("[PIL not installed — sending raw. install via: pip install Pillow]",
                  file=sys.stderr)
        except Exception as e:
            print(f"[resize failed: {e} — sending raw]", file=sys.stderr)
    return base64.b64encode(raw).decode("ascii")


def stream_vision(path, prompt):
    """POST to Ollama, stream tokens to stdout."""
    if not os.path.exists(path):
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if os.path.isdir(path):
        print(f"ERROR: path is a directory: {path}", file=sys.stderr)
        sys.exit(1)

    b64 = load_and_resize(path)

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": True,
        "keep_alive": -1,
        "options": {"temperature": 0.7, "num_ctx": 4096},
    }

    print(f"=== model={MODEL}", file=sys.stderr)
    print(f"=== path={path}", file=sys.stderr)
    print(f"=== prompt={prompt!r}", file=sys.stderr)
    print("---", file=sys.stderr)

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                tok = chunk.get("message", {}).get("content", "")
                if tok:
                    print(tok, end="", flush=True)
                if chunk.get("done"):
                    break
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"\nERROR: Ollama HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(2)
    except urllib.error.URLError as e:
        print(f"\nERROR: can't reach Ollama at {OLLAMA_URL} — is it running?\n  {e}",
              file=sys.stderr)
        sys.exit(3)
    print()  # final newline


if __name__ == "__main__":
    path, prompt = parse_args()
    stream_vision(path, prompt)
