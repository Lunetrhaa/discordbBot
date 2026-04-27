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

- Code: `bot/bot.py` (general + Truth or Dare), `bot/music.py` (music cog)
- Stack: Python 3.11, `discord.py`, `yt-dlp`, `PyNaCl`, system `ffmpeg`
- Workflow: `Discord Bot` — runs `python -u bot/bot.py`
- Token secret: `DISCORD_BOT_TOKEN`
- Slash commands (Indonesian): `/help`, `/ping`, `/hello`, `/say`, `/roll`, `/flip`, `/choose`, `/avatar`, `/userinfo`, `/serverinfo`, `/clear`, `/tod`
- Music prefix commands (`m/` to avoid clashing with Jockie Music):
  `m/play`, `m/skip`, `m/stop`, `m/pause`, `m/resume`, `m/queue`, `m/nowplaying`,
  `m/volume`, `m/loop`, `m/clear`, `m/leave`, `m/help`
- Requires "Message Content Intent" enabled in the Discord Developer Portal.
