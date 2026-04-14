# Claude Instructions for MyX

## URLs
Always use `x.com` URLs, not `twitter.com`. X was rebranded and the scraper targets x.com.

## Subagent Tasks
Always ask the user before launching each new subagent implementation task. The user monitors Claude Code usage limits and wants control over when each task starts.

## Secrets
Never commit `config.yaml` — it contains the database password. Only `config.example.yaml` belongs in git.

## Tests
```bash
source .venv/bin/activate
pytest
```

## X API Quirks
`user_legacy.id_str` is absent from SearchTimeline responses in the current X API. Always use `user_result.rest_id` as the authoritative user ID — it's what `author_id` is derived from in `pipeline/parser.py`.

## Running the scraper manually
```bash
source .venv/bin/activate
python cli.py run
```

Chromium must be running with CDP debugging enabled first:
```bash
./launch-chromium.sh
```
