"""
Standalone batch vision CLI — fires + forgets in a terminal so u can keep
using the Discord bot for other shit while this grinds.

Hits Ollama directly. No bot in the loop. Outputs to stdout (so u can
watch progress live) AND optionally writes a consolidated .txt next to
the source directory.

Usage:
    python vision_cli_batch.py <directory>
    python vision_cli_batch.py <directory> "<prompt>"
    python vision_cli_batch.py <directory> "<prompt>" --out <output.txt>
    python vision_cli_batch.py <directory> "<prompt>" --model <model_name>

Examples:
    python vision_cli_batch.py C:/Users/gwu07/Desktop/refs
    python vision_cli_batch.py C:/Users/gwu07/Desktop/refs "describe lighting and composition"
    python vision_cli_batch.py C:/Users/gwu07/Desktop/refs "generate SDXL prompt tags" --out refs.txt
    python vision_cli_batch.py C:/Users/gwu07/Desktop/refs "describe in detail" --model huihui_ai/qwen2.5-vl-abliterated:7b

Environment (reads from .env in same folder, then OS env):
    VISION_MODEL_NAME     (default: qwen2.5vl:3b — light, fast)
    OLLAMA_URL            (default: http://localhost:11434/api/chat)
    VISION_MAX_DIM        (default: 1536, set 0 to disable resize)
    SEE_BATCH_MAX         (default: unlimited in CLI — only Discord side caps)
"""
import sys, os, base64, json, urllib.request, urllib.error, io, time
from pathlib import Path

# Load .env from same directory if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass

OLLAMA_URL          = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
DEFAULT_MODEL       = os.getenv("VISION_MODEL_NAME", "qwen2.5vl:3b")
VISION_MAX_DIM      = int(os.getenv("VISION_MAX_DIM", "1536"))
DEFAULT_PROMPT      = "describe this image in detail"
IMAGE_EXTS          = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def parse_args():
    """Returns (directory, prompt, output_file_or_None, model)."""
    args = sys.argv[1:]
    if not args:
        print("ERROR: no directory provided", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    directory = args[0]
    prompt = DEFAULT_PROMPT
    output_file = None
    model = DEFAULT_MODEL

    # Walk remaining args
    i = 1
    positional = []
    while i < len(args):
        if args[i] == "--out":
            output_file = args[i + 1]
            i += 2
        elif args[i] == "--model":
            model = args[i + 1]
            i += 2
        else:
            positional.append(args[i])
            i += 1
    if positional:
        prompt = " ".join(positional)

    return directory, prompt, output_file, model


def load_and_resize(path):
    """Read image + resize via VISION_MAX_DIM, return base64."""
    with open(path, "rb") as f:
        raw = f.read()
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
        except ImportError:
            pass
        except Exception:
            pass
    return base64.b64encode(raw).decode("ascii")


def stream_one(model, b64, prompt):
    """Stream a single image's description from Ollama. Yields token chunks."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": True,
        "keep_alive": -1,
        "options": {"temperature": 0.7, "num_ctx": 4096},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
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
                yield tok
            if chunk.get("done"):
                break


def main():
    directory, prompt, output_file, model = parse_args()

    if not os.path.exists(directory):
        print(f"ERROR: directory not found: {directory}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(directory):
        print(f"ERROR: not a directory: {directory}", file=sys.stderr)
        sys.exit(1)

    # Find images
    images = sorted(
        entry for entry in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, entry))
        and os.path.splitext(entry)[1].lower() in IMAGE_EXTS
    )
    if not images:
        print(f"ERROR: no images in {directory}", file=sys.stderr)
        sys.exit(1)

    print(f"=== BATCH VISION ANALYSIS ===")
    print(f"Directory:  {os.path.abspath(directory)}")
    print(f"Model:      {model}")
    print(f"Prompt:     {prompt}")
    print(f"Images:     {len(images)}")
    if output_file:
        print(f"Output:     {output_file}")
    print("===")
    print()

    # Optional file output
    out_handle = None
    if output_file:
        out_handle = open(output_file, "w", encoding="utf-8")
        out_handle.write(f"=== BATCH VISION ANALYSIS ===\n")
        out_handle.write(f"Directory:  {os.path.abspath(directory)}\n")
        out_handle.write(f"Model:      {model}\n")
        out_handle.write(f"Prompt:     {prompt}\n")
        out_handle.write(f"Images:     {len(images)}\n")
        out_handle.write(f"===\n\n")

    batch_start = time.monotonic()
    successes = 0
    for i, fname in enumerate(images, 1):
        fpath = os.path.join(directory, fname)
        img_start = time.monotonic()
        print(f"--- [{i}/{len(images)}] {fname} ---")
        if out_handle:
            out_handle.write(f"--- [{i}/{len(images)}] {fname} ---\n")
        try:
            b64 = load_and_resize(fpath)
        except Exception as e:
            err_msg = f"  resize/encode failed: {type(e).__name__}: {e}"
            print(err_msg, file=sys.stderr)
            if out_handle:
                out_handle.write(err_msg + "\n\n")
            continue

        try:
            chunks = []
            for tok in stream_one(model, b64, prompt):
                print(tok, end="", flush=True)
                if out_handle:
                    out_handle.write(tok)
                chunks.append(tok)
            elapsed = int(time.monotonic() - img_start)
            print(f"\n  [done in {elapsed}s]\n")
            if out_handle:
                out_handle.write(f"\n[done in {elapsed}s]\n\n")
                out_handle.flush()
            successes += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            err_msg = f"  HTTP {e.code}: {body}"
            print(err_msg, file=sys.stderr)
            if out_handle:
                out_handle.write(err_msg + "\n\n")
        except urllib.error.URLError as e:
            err_msg = f"  Ollama unreachable: {e}"
            print(err_msg, file=sys.stderr)
            if out_handle:
                out_handle.write(err_msg + "\n\n")
        except Exception as e:
            err_msg = f"  {type(e).__name__}: {e}"
            print(err_msg, file=sys.stderr)
            if out_handle:
                out_handle.write(err_msg + "\n\n")

    total = int(time.monotonic() - batch_start)
    avg = total / max(len(images), 1)
    summary = f"\n=== DONE: {successes}/{len(images)} successful in {total}s (avg {avg:.1f}s/img) ===\n"
    print(summary)
    if out_handle:
        out_handle.write(summary)
        out_handle.close()
        print(f"Output written to: {output_file}")


if __name__ == "__main__":
    main()
