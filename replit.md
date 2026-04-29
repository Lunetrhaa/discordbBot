# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.

## Discord Bot

- Code (each file in `bot/`):
  - `bot.py` — main entrypoint, Truth or Dare, admin `/say`
  - `music.py` — music cog (`m/` prefix, anti-collision with Jockie)
  - `games.py` — 16 minigames + point rewards
  - `quiz.py` — 11 tebak-tebakan + `/stats` + `/leaderboard`
  - `quiz_data.py` — quiz question banks
  - `stats.py` — JSON persistence: points, wins, **xp/level/messages/voice_seconds, daily streak**
  - `config.py` — per-guild config storage at `bot/data/config.json` (shared with admin panel)
  - `ai_cog.py` — `/imagine` (image gen) + `/chat` (AI conversation)
  - `levels.py` — XP system (chat 15-25 XP / 60s cooldown, voice 10 XP/min when 2+ non-deaf members), `/level`, `/rank`, level-up announce
  - `social.py` — `/love`, `/dailyclaim`, `/calc`, `/robux`, `/confess`, `/setconfess`
  - `downloader.py` — `/vt` (TikTok), `/yt` (YouTube), `/dl` (universal) via yt-dlp
  - `sholat.py` — pengingat sholat 5 waktu WIB ke #truth-or-dare (auto-detect) atau channel terpilih, + `/jadwalsholat` `/setsholat`
  - `welcome.py` — embed welcome/goodbye dengan avatar + custom bg image, `/setwelcome` `/setgoodbye` `/testwelcome`
  - `voicemaster.py` — auto-create voice channel saat user join "✗》Create voice", control panel button (lock/unlock/hide/show/rename/limit/claim/disconnect), `/setvoicemaster` `/createvoice`
- Stack: Python 3.11, `discord.py`, `yt-dlp`, `PyNaCl`, system `ffmpeg`, `openai` (via Replit AI integration)
- Workflow: `Discord Bot` — runs `python -u bot/bot.py`
- Required intents: `members`, `message_content`, `voice_states`
- Token secret: `DISCORD_BOT_TOKEN`
- Slash commands: 62 total (per-guild sync). Music prefix: `m/play m/skip m/stop m/pause m/resume m/queue m/nowplaying m/volume m/loop m/clear m/leave m/help`.
- Special `/love` rules: pasangan yang nama-nya mengandung `jaa` AND `fey` → 100% 💕; salah satu special → 90-100%; lainnya → deterministik dari ID + alphabet-distance + jitter. Nama dengan font khusus (𝐅𝐀𝐍𝐂𝐘) dinormalisasi via NFKD.
- Special `/robux` rules: pajak Roblox 30% (dev terima 70%), opsional rate Rupiah/Robux (default Rp 130).

## Admin Web Panel

- Code: `artifacts/api-server/src/routes/admin.ts`
- URL: `https://<your-domain>/api/admin` (preview: `localhost:80/api/admin`)
- Auth: HTTP Basic — username `admin`, password = `SESSION_SECRET` env var
- Endpoints:
  - `GET /api/admin` — single-page HTML config UI
  - `GET /api/admin/config/:guildId` — fetch per-guild config JSON
  - `PUT /api/admin/config/:guildId` — update per-guild config
  - `GET /api/admin/stats` — global summary (users / total xp / total points per guild)
- Storage: writes to absolute path `/home/runner/workspace/bot/data/config.json` shared with the bot. Bot reads on every event so changes apply instantly without restart.
- Configurable per-guild: welcome/goodbye channel + bg image + text + warna, level-up channel/toggle, sholat channel/toggle, voicemaster create-channel + category, confess channel.
