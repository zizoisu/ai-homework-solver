# AI Homework Solver

Solve homework problems with AI — **free for text** (anonymous tier), advanced features with **BYOP** (Bring Your Own Pollen) authentication.

**🌐 Live Demo:** https://zizoisu.github.io/ai-homework-solver/

## Screenshots

### Main Solver Interface
![Main Interface](docs/screenshot-main.png)

### Settings Dashboard
![Settings Dashboard](docs/screenshot-settings.png)

### Demo: Solving a Question
![Demo](docs/demo-solved.png)

## Quick Start

### Option 1: GitHub Pages (Static — Recommended)

The app works fully static on GitHub Pages! All API calls go directly from the browser to Pollinations.ai (CORS enabled).

1. Visit: https://zizoisu.github.io/ai-homework-solver/

### Option 2: Local Flask Server

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

### Option 3: Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?templateDir=.&repo=https://github.com/zizoisu/ai-homework-solver)

## Features

- ✅ **Free tier**: Anonymous requests to `text.pollinations.ai/openai` (model: `gpt-oss-20b`)
- ✅ **BYOP tier**: Authenticated requests to `gen.pollinations.ai/v1/chat/completions`
- ✅ **Image upload**: Upload homework sheets for vision-capable models (requires BYOP key)
- ✅ **4 question types**: MCQ, short answer, true/false, fill in the blank
- ✅ **Settings dashboard**: Connect/disconnect BYOP key, view models, select active model
- ✅ **25% developer markup** on BYOP requests (your key must include the markup)
- ✅ **Static hosting**: Works on GitHub Pages with no backend needed

## How It Works

```
Free tier (no key):
  Browser → text.pollinations.ai/openai (anonymous, no auth)

BYOP tier (with key):
  Browser → gen.pollinations.ai/v1/chat/completions (Bearer token auth)
  Browser → gen.pollinations.ai/v1/models (Bearer token auth)
```

All Pollinations API endpoints support CORS, so no backend is needed. Your BYOP key (`sk_...`) is stored in browser `sessionStorage` (never in localStorage, URLs, or logs).

## Getting a BYOP Key

1. Go to [enter.pollinations.ai](https://enter.pollinations.ai)
2. Click **Authorize** (OAuth login)
3. Copy your `sk_…` key
4. Paste it in the **Settings** page → **Connect**
5. Choose your model and start solving!

## API Endpoints (Flask backend, if running locally)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/solve` | Solve a homework question (auto-selects free/BYOP) |
| `GET`  | `/api/models` | List available models (requires BYOP key) |
| `POST` | `/api/select-model` | Set active model |
| `POST` | `/api/connect` | Connect BYOP key |
| `POST` | `/api/disconnect` | Disconnect BYOP key |
| `POST` | `/api/upload-image` | Upload image for vision models |

## Deployment

### GitHub Pages (Static)

The static version runs directly from the browser. To enable GitHub Pages:

1. Go to your repo: https://github.com/zizoisu/ai-homework-solver
2. Settings → Pages → Source: `Deploy from a branch` → `master` → `/root` (or `/(root)`)
3. Save — your app will be live at https://zizoisu.github.io/ai-homework-solver/

### Railway (Flask backend)

1. Fork this repository
2. Go to https://railway.app
3. Create a new project and link your GitHub repo
4. Set environment variable: `SECRET_KEY=your-random-secret`
5. Deploy!

### Render (Flask backend)

1. Fork this repository
2. Go to https://render.com
3. Create a new Web Service, connect your GitHub repo
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `gunicorn app:app`
6. Deploy!

## Architecture

```
Static (GitHub Pages):
  Browser ↔ text.pollinations.ai (free tier, anonymous)
  Browser ↔ gen.pollinations.ai/v1 (BYOP tier, Bearer token)

Flask (optional backend for local dev):
  Browser → /api/solve → text.pollinations.ai/openai (free)
  Browser → /api/solve → gen.pollinations.ai/v1/chat/completions (BYOP)
```

## License

MIT