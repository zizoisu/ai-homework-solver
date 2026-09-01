"""AI Homework Solver - Flask Application
Pollinations AI Integration with automatic model selection.

Free tier (no API key): Anonymous requests to text.pollinations.ai
BYOP tier (with API key): Authenticated requests to gen.pollinations.ai

Developer markup: 25% (app earnings go to zizo)
"""

import os
import json
import urllib.parse
from flask import Flask, render_template, request, jsonify, session
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32).hex())
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# ── Pollinations API endpoints ──────────────────────────────────────────
# Free tier: text.pollinations.ai/openai — anonymous, no key needed,
# always defaults to gpt-oss-20b. No model parameter required or used.
TEXT_FREE_ENDPOINT = "https://text.pollinations.ai/openai"
TEXT_FREE_GET_ENDPOINT = "https://text.pollinations.ai"
# BYOP tier: gen.pollinations.ai/v1 — authenticated, full model selection
GEN_AUTH_ENDPOINT = "https://gen.pollinations.ai/v1/chat/completions"
GEN_MODELS_ENDPOINT = "https://gen.pollinations.ai/v1/models"

# Fallback model list when API is unreachable (BYOP tier only)
FALLBACK_MODELS = [
    {"id": "openai", "name": "OpenAI", "description": "Reasoning LLM - chat completions", "free": False, "vision": True, "owned_by": "OpenAI"},
    {"id": "openai-fast", "name": "OpenAI Fast", "description": "Fast reasoning LLM", "free": False, "vision": True, "owned_by": "OpenAI"},
    {"id": "nemotron", "name": "Nemotron", "description": "NVIDIA model", "free": False, "vision": False, "owned_by": "NVIDIA"},
    {"id": "qwen-coder", "name": "Qwen Coder", "description": "Coding-specialized model", "free": False, "vision": False, "owned_by": "Qwen"},
]


# ── Helpers ─────────────────────────────────────────────────────────────

def get_user_key():
    """Return the user's BYOP key from session, or None."""
    return session.get("pollinations_key")


def is_connected():
    """Check if user has a BYOP key stored in session."""
    return get_user_key() is not None


def get_selected_model():
    """Get the model the user has selected (BYOP tier only).
    Free tier always uses gpt-oss-20b — no selection needed."""
    if is_connected():
        return session.get("selected_model", "openai")
    return None


def fetch_models_from_api(key):
    """Fetch available models from the Pollinations API for the given key."""
    headers = {"Authorization": f"Bearer {key}"}
    resp = requests.get(GEN_MODELS_ENDPOINT, headers=headers, timeout=15)
    if resp.status_code != 200:
        return None

    data = resp.json()
    raw_models = data.get("data", [])
    result = []
    for m in raw_models:
        if not isinstance(m, dict):
            continue
        model_id = m.get("id", "")
        owned_by = m.get("owned_by", "Pollinations")
        input_mods = m.get("input_modalities", [])
        vision = "image" in input_mods
        # Determine if it's the free/default model for the user
        is_free_tier = model_id == "gpt-oss-20b" or "free" in model_id.lower()
        # Build a human-friendly name
        name = model_id.replace("-", " ").title().replace("/", " / ")
        result.append({
            "id": model_id,
            "name": name,
            "description": f"Owned by {owned_by}" + (" · vision" if vision else ""),
            "free": is_free_tier,
            "vision": vision,
            "owned_by": owned_by,
        })
    return result or FALLBACK_MODELS


def solve_free(question, qtype=None, image_b64=None):
    """Solve using free anonymous tier (no API key needed).

    The free anonymous tier has a very limited token budget (~30 chars of
    input).  Sending a long system prompt (e.g. "You are an expert
    homework solver…") exhausts this budget immediately and triggers a
    402 Payment Required, even for anonymous requests.  Therefore we
    send ONLY the raw question text — no system prompt, no formatting.

    We try the POST endpoint first (returns JSON), then fall back to the
    GET endpoint (returns plain text).  Rate limit: one request every
    ~15 seconds per IP, so we space retries accordingly.
    """
    import time

    # Send ONLY the question — no system prompt, no formatting wrappers.
    # This keeps the prompt under the anonymous token budget.
    if image_b64:
        return "Image-based questions require a BYOP key. Connect your Pollinations account in Settings.", False

    last_error = None

    # Strategy 1: POST to text.pollinations.ai/ (root) — returns JSON
    for attempt in range(3):
        try:
            payload = {"messages": [{"role": "user", "content": question}]}
            resp = requests.post(
                TEXT_FREE_ENDPOINT.rsplit("/openai", 1)[0] + "/",
                json=payload,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"]["content"], True
                return resp.text, True
            elif resp.status_code == 429:
                last_error = f"Rate limited (HTTP {resp.status_code})"
            elif resp.status_code == 402:
                last_error = f"Payment required / budget exhausted"
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            last_error = str(e)
        # Exponential backoff: 5s, 10s, 15s (respects 15s IP rate limit)
        time.sleep(5 * (attempt + 1))

    # Strategy 2: Simple GET endpoint (plain text, no JSON)
    try:
        encoded = urllib.parse.quote(question)
        url = f"{TEXT_FREE_GET_ENDPOINT}/{encoded}"
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return resp.text, True
        last_error = f"GET endpoint returned HTTP {resp.status_code}"
    except Exception as e:
        last_error = str(e)

    return (
        f"Free tier unavailable: {last_error}. "
        "The free anonymous tier has a limited budget. "
        "Please wait a minute and try again, or connect a BYOP key for more reliable results.",
        False,
    )


def solve_byop(prompt, model=None, image_b64=None):
    """Solve using authenticated BYOP tier.

    If *image_b64* is provided and the model supports vision, the image is
    sent as a vision message alongside the text prompt.
    """
    key = get_user_key()
    if not key:
        return "Please connect your Pollinations account in Settings first.", False

    if not model:
        model = get_selected_model()

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # Build the message payload
    if image_b64 and model in ("openai", "openai-fast", "gpt-4o", "gpt-4o-mini"):
        # Vision-capable model – send image as base64
        content = []
        if prompt:
            content.append({"type": "text", "text": prompt})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
        })
        messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "user", "content": prompt}]

    payload = {"model": model, "messages": messages}

    try:
        resp = requests.post(GEN_AUTH_ENDPOINT, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices and "message" in choices[0]:
                return choices[0]["message"]["content"], True
            return json.dumps(data, indent=2), True

        if resp.status_code in (401, 403):
            return "Invalid API key. Please check your key in Settings.", False
        if resp.status_code == 402:
            return "Insufficient Pollen credits. Top up at enter.pollinations.ai.", False

        # Fallback: try the 'openai' model on BYOP endpoint
        if model != "openai":
            payload["model"] = "openai"
            resp2 = requests.post(GEN_AUTH_ENDPOINT, headers=headers, json=payload, timeout=60)
            if resp2.status_code == 200:
                data = resp2.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"]["content"], True

        return f"API error (HTTP {resp.status_code}). Check your API key or try another model.", False
    except Exception as e:
        return f"Network error: {e}", False


def build_prompt(question, qtype):
    """Build an instruction prompt based on question type."""
    base = "You are an expert homework solver. Provide a clear, direct answer."
    prompts = {
        "mcq": f"{base}\n\nMULTIPLE CHOICE QUESTION:\n{question}\n\nProvide:\n1. The correct answer\n2. Brief reasoning",
        "short_answer": f"{base}\n\nQUESTION:\n{question}\n\nProvide a concise, accurate answer.",
        "true_false": f"{base}\n\nTRUE OR FALSE:\n{question}\n\nAnswer with: TRUE or FALSE, then a brief explanation.",
        "fill_in_blank": f"{base}\n\nFILL IN THE BLANK:\n{question}\n\nProvide the most appropriate completion.",
        "default": f"{base}\n\nQUESTION:\n{question}\n\nProvide a clear, accurate answer.",
    }
    return prompts.get(qtype, prompts["default"])


# ── Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        connected=is_connected(),
        selected_model=get_selected_model(),
    )


@app.route("/settings")
def settings():
    connected = is_connected()
    models = []
    if connected:
        models = fetch_models_from_api(get_user_key())
        if not models:
            models = FALLBACK_MODELS
    return render_template(
        "settings.html",
        connected=connected,
        models=models,
        selected_model=session.get("selected_model", "openai" if connected else ""),
        key_hint=get_user_key()[:8] + "…" if connected else "",
    )


@app.route("/api/solve", methods=["POST"])
def solve_api():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    qtype = data.get("question_type", "short_answer")
    image_b64 = data.get("image_b64")  # base64-encoded image (optional)

    if not question and not image_b64:
        return jsonify(success=False, error="Please enter a question or upload an image"), 400

    prompt = build_prompt(question, qtype)
    selected = get_selected_model()

    # If image is uploaded, we need BYOP (vision model)
    if image_b64 and not is_connected():
        return jsonify(
            success=False,
            error="Image-based questions require a BYOP key. Connect your Pollinations account in Settings.",
        ), 402

    # Use BYOP if connected, else free tier
    if is_connected():
        solution, ok = solve_byop(prompt, selected, image_b64)
        tier = "BYOP" if ok else "BYOP (failed)"
        # Fallback to free tier if BYOP fails and no image
        if not ok and not image_b64:
            solution, ok = solve_free(question, qtype, image_b64)
            tier = "Free (fallback)" if ok else "Free (failed)"
    else:
        solution, ok = solve_free(question, qtype, image_b64)
        tier = "Free" if ok else "Free (failed)"

    # Only include model info for BYOP tier; free tier uses gpt-oss-20b
    # automatically and the model name should not be exposed to users
    response = {
        "success": True,
        "solution": solution,
        "tier": tier,
        "used_byop": is_connected(),
    }
    if is_connected() and selected:
        response["model"] = selected
    return jsonify(**response)


@app.route("/api/models", methods=["GET"])
def models_api():
    if is_connected():
        models = fetch_models_from_api(get_user_key())
        if models:
            return jsonify(success=True, models=models, selected_model=session.get("selected_model"))
    # Free tier: no models to show (system uses gpt-oss-20b automatically)
    return jsonify(success=True, models=[], selected_model="")


@app.route("/api/select-model", methods=["POST"])
def select_model_api():
    data = request.get_json(silent=True) or {}
    model_id = (data.get("model_id") or "").strip()
    if not model_id:
        return jsonify(success=False, error="Model ID required"), 400
    session["selected_model"] = model_id
    return jsonify(success=True, model=model_id)


@app.route("/api/connect", methods=["POST"])
def connect_api():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or data.get("api_key") or "").strip()
    if not key:
        return jsonify(success=False, error="Please enter your API key"), 400

    # Verify the key works by fetching models
    models = fetch_models_from_api(key)
    if models is None:
        return jsonify(success=False, error="Invalid API key or server error"), 403

    # Store key and select a good default model
    session["pollinations_key"] = key
    # Prefer a free-tier model if available, otherwise the first model
    default_model = None
    for m in models:
        if m.get("free"):
            default_model = m["id"]
            break
    if not default_model and models:
        default_model = models[0]["id"]
    if not default_model:
        default_model = "openai"
    session["selected_model"] = default_model

    return jsonify(
        success=True,
        message="Connected successfully!",
        models=models,
        selected_model=default_model,
    )


@app.route("/api/disconnect", methods=["POST"])
def disconnect_api():
    session.pop("pollinations_key", None)
    session.pop("selected_model", None)
    return jsonify(success=True, message="Disconnected")


@app.route("/api/upload-image", methods=["POST"])
def upload_image_api():
    """Handle image upload and return base64 for inline use."""
    if "file" not in request.files:
        return jsonify(success=False, error="No file part"), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify(success=False, error="No file selected"), 400

    # Read and encode
    import base64
    raw = file.read()
    b64 = base64.b64encode(raw).decode("utf-8")

    # Determine image type
    ext = file.filename.rsplit(".", 1)[-1].lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif"}.get(ext, "image/png")

    return jsonify(
        success=True,
        image_b64=b64,
        mime_type=mime,
        filename=file.filename,
    )


if __name__ == "__main__":
    print("AI Homework Solver running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
