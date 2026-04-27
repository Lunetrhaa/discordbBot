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

- Code:
  - `bot/bot.py` — main bot, general + Truth or Dare, admin `/say` announcement
  - `bot/music.py` — music cog (`m/` prefix)
  - `bot/games.py` — minigames cog (trivia, tictactoe, reactiontest, scramble, math, numberguess, higherlower, etc.)
  - `bot/quiz.py` — tebak-tebakan cog + `/stats` + `/leaderboard`
  - `bot/quiz_data.py` — question banks (FLAGS, KPOP, WORDS, CAPITALS, ANIMALS, GREETINGS, COLORS, EMOJI_PUZZLES, YEARS, CHARACTERS, LYRICS)
  - `bot/stats.py` — points/wins/losses persistence (JSON at `bot/data/stats.json`)
  - `bot/ai_cog.py` — `/imagine` via Replit OpenAI integration
- Stack: Python 3.11, `discord.py`, `yt-dlp`, `PyNaCl`, `davey`, system `ffmpeg`
- Workflow: `Discord Bot` — runs `python -u bot/bot.py`
- Token secret: `DISCORD_BOT_TOKEN`
- Slash commands (per-guild sync, ~43 cmds): general `/help /ping /hello /roll /flip /choose /avatar /userinfo /serverinfo /clear /tod`, admin `/say`, AI `/imagine`, games `/trivia /8ball /rps /numberguess /wouldyourather /tictactoe /reactiontest /scramble /math /higherlower /russianroulette ...`, quiz `/tebakbendera /tebakkpop /tebakkata /tebakkota /tebakhewan /tebakbahasa /tebakwarna /tebakemoji /tebaktahun /tebakkarakter /tebaklagu /quizlist`, stats `/stats /leaderboard`
- Music prefix commands (`m/` to avoid clashing with Jockie Music):
  `m/play`, `m/skip`, `m/stop`, `m/pause`, `m/resume`, `m/queue`, `m/nowplaying`,
  `m/volume`, `m/loop`, `m/clear`, `m/leave`, `m/help`
- Points: each won game awards points (5–15) tracked per-guild in `bot/data/stats.json`. View with `/stats [user]`, ranking via `/leaderboard`.
- Requires "Message Content Intent" enabled in the Discord Developer Portal.
