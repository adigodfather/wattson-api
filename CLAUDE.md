# ZYNAPSE

Turn n8n workflows into production web apps. Each app is a Next.js frontend that talks to a self-hosted n8n workflow via webhook. n8n handles all orchestration (AI, data transforms, external APIs). The FastAPI backend on Render stays as a pure calculation engine for the electrical calculator app.

**GitHub**: `adigodfather/zynapse` → auto-deploys to Vercel on push to `main`.

---

## Folder Structure

```
/
├── CLAUDE.md
├── main.py              # FastAPI electrical calc engine (deployed on Render)
├── render.yaml
├── requirements.txt
└── apps/
    └── electrical-calculator/   # Next.js app #1
        ├── .env.local           # NEXT_PUBLIC_N8N_WEBHOOK_URL (never commit)
        ├── app/                 # Next.js App Router
        └── ...
```

Each new workflow-to-app gets its own folder under `apps/`.

---

## Workflow for Every New App

### Phase 1 — Audit the n8n Workflow (use n8n MCP)

Before writing any frontend code, confirm:

1. **Webhook trigger** — accepts HTTP POST, has a defined request body shape
2. **Respond to Webhook node** — returns structured JSON synchronously (not fire-and-forget)
3. **Error shape** — consistent `{ error: string }` on failure so the frontend can display it
4. **Schema locked** — document exact request + response schemas before touching the frontend

### Phase 2 — Build the Frontend

1. `npx create-next-app@latest apps/<app-name>` — TypeScript, Tailwind, App Router
2. Add `NEXT_PUBLIC_N8N_WEBHOOK_URL` to `.env.local`
3. Build form → POST to webhook → render response
4. Test locally: `cd apps/<app-name> && npm run dev` → `http://localhost:3000`

### Phase 3 — Ship

1. Push to `main` on `adigodfather/zynapse` (use GitHub MCP)
2. Vercel auto-deploys — verify the deployment
3. Future changes: edit → push → Vercel updates automatically

---

## Key Rules

- **n8n is the brain** — no orchestration logic in the frontend or FastAPI
- **FastAPI is a calculator** — pure input → output, no AI calls, no file parsing
- **Never commit `.env.local`** — webhook URLs stay in Vercel env vars for production
- **Schemas first** — audit and document the n8n schema before writing any UI
- **Don't touch working apps** — when adding a new app, other apps in `apps/` are off-limits

---

## Available Tools

| Tool | Use for |
|------|---------|
| n8n MCP | Inspect workflows, check node configs, modify workflows |
| GitHub MCP | Push changes, create repos, manage branches |
| n8n skill | n8n-specific patterns and best practices |
| Frontend designer skill | UI/UX decisions for the Next.js apps |

---

## Environment Variables

Each app in `apps/` gets its own `.env.local`:

```
NEXT_PUBLIC_N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/xxx
```

In Vercel, set these per-project under Project Settings → Environment Variables.
