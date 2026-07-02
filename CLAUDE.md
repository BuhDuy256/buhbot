# CLAUDE.md for BuhBot

## Project

OptiSigns OptiBot mini-clone: scrapes `support.optisigns.com` articles into Markdown,
loads them into an OpenAI Vector Store, and re-runs daily in Docker to upload only
new/changed articles.

## Project Structure

1. Requirements: @"docs/reqs/OptiSigns_Take-Home_Test_Updated.pdf"
2. Entry point: @"main.py" — repo root, not inside `src/`.
3. Source code: @"src/" — currently empty except `__init__.py`. All implementation
   belongs here as it's built; `main.py` should stay a thin orchestrator that imports from `src/`, not host logic itself.
4. Dependencies: @"requirements.txt" — pip-installed, no Poetry/uv.
5. Env template: @".env.example" — documents required env vars (`OPENAI_API_KEY`, etc.);
   `.env` itself is git-ignored and never committed.
6. Prior attempt analysis (reference only, do not copy): @"docs/prior/prior-implementation.md"

## Code style

- Language: Python
- Naming: snake_case
- Dependencies: `requirements.txt` + pip (no Poetry/uv)
- AI platform: OpenAI (Assistants/Responses API + OpenAI Vector Store)
- Secrets: never hard-code API keys — read from environment variables; document
  required vars in `.env.example` (never commit `.env`)

## Constraints from requirements (do not relax without asking)

- Scrape ≥30 articles via the Zendesk API; convert to clean Markdown; preserve
  relative links, code blocks, and headings; strip nav/ads
- Vector store upload is API-based only — no UI drag-and-drop
- Chunking strategy is a free choice, but must be explained in the README
- Assistant system prompt must match verbatim (see below)
- Daily job: logic wrapped in `main.py`, Dockerized; `docker run -e API_KEY=... main.py`
  must run once and exit 0
- Daily job must detect new/updated articles (hash or `Last-Modified`) and upload only
  the delta; log counts for added / updated / skipped
- README ≤ 1 page: setup, how to run locally, link to job logs, screenshot of the
  assistant answering a sample question with cited URLs
- GitHub repo name must be cryptic — must not contain "optisigns"

## Assistant system prompt (verbatim — do not paraphrase)

```
You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply.
```

## Workflow

- Read the requirements doc each time you enter the project
