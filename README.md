# Telegram Media-to-Admin Relay Bot

The simplest possible version of the bot: anyone sends the bot a photo
or video, it checks whether it's a duplicate, and — if not — relays it
to a single admin user, one item every 2 seconds.

No commands. No captions. No queues to manage. The sender doesn't type
anything at all, just sends the media.

## How it works

1. Someone sends a photo or video to the bot.
2. The bot checks Telegram's `file_unique_id` for that item against
   everything it's relayed before.
   - **Duplicate** → silently dropped, nothing happens.
   - **New** → added to an internal relay queue.
3. A background worker drains that queue and sends items to `ADMIN_ID`
   one at a time, waiting `RELAY_DELAY_SECONDS` (default 2s) between
   each send — so a burst of incoming media doesn't hit Telegram's
   rate limits and arrives as a readable stream.

That's the entire bot. Anything sent that isn't a photo or video
(text, documents, stickers, etc.) is ignored.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env: set BOT_TOKEN (from @BotFather) and ADMIN_ID (your own
# Telegram user id — get it from a bot like @userinfobot)
python bot.py
```

**Important:** the admin must have started a DM with the bot at least
once (e.g. sent it `/start` or any message) before the bot can send
messages to them — this is a Telegram restriction, not a bot bug.

State (the list of already-seen media, for duplicate detection)
persists to `data.json` next to the script, so restarting the bot
doesn't forget what it's already relayed — **except on Railway and
similar platforms, see below.**

## Deploying on Railway

1. Push this folder to a GitHub repo. **Do not commit `.env`** — it's
   in `.gitignore`. Set `BOT_TOKEN` and `ADMIN_ID` as environment
   variables in the Railway dashboard instead (Variables tab).
2. Railway will detect Python via `requirements.txt` and use the
   `Procfile` (`worker: python bot.py`) to start it as a background
   worker — it does **not** need a public port, since `run_polling()`
   isn't an HTTP server. If Railway shows a "no open port detected"
   warning, ignore it or set the service type to "Worker" explicitly
   in settings.
3. **Attach a Volume** if you want duplicate-detection memory to
   survive redeploys. Railway's container filesystem resets on every
   redeploy — without a volume, `data.json` disappears each time you
   push, and the bot will treat previously-relayed media as new again.
   In Railway: your service → Settings → Volumes → add one, mount it
   at e.g. `/data`, then set `DATA_FILE=/data/data.json` as an
   environment variable. If you don't care about that edge case (e.g.
   you rarely redeploy), you can skip this.
4. Deploy. Check the Railway logs for `🤖 Bot running...` — if the
   token or admin id is wrong you'll see the error there immediately.

## Files

- `config.py` — loads `.env` / environment variables
- `storage.py` — tiny JSON persistence of seen `file_unique_id`s, for
  duplicate detection
- `bot.py` — the entire bot: media handler + relay worker + entrypoint

## Known limitations

- Duplicate detection is based on Telegram's `file_unique_id` — it
  won't catch a pixel-identical image re-uploaded as a genuinely new
  file (e.g. re-saved/re-compressed), since Telegram assigns that a
  different id.
- `ADMIN_ID` is a single fixed user — there's no way to relay to
  multiple admins or a channel without code changes.
- The relay queue lives in memory only; if the bot restarts with
  unsent items still queued, those specific items are lost (though
  they were already recorded as "seen," so they won't be re-queued if
  re-sent — resending them if that happens is easiest).
- Not live-tested against Telegram's servers. Please run it against
  your real bot token and watch the console/logs for errors.
