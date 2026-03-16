# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install for development
uv tool install .

# Run all tests
uv run pytest -v

# Run a single test file
uv run pytest tests/test_cli.py -v

# Run the CLI
timecard --help
```

## Architecture

TimeCard is a Python CLI for 1099 contractors. The package lives in `timecard/` with tests in `tests/`.

**Module dependency order** (lower modules have no dependencies on higher ones):
1. `models.py` — dataclasses: `Entry`, `Invoice`, `ActiveSession`
2. `config.py` — loads `.env` via python-dotenv into a `Settings` dataclass; env vars `TIMECARD_CONFIG_PATH` and `TIMECARD_DB_PATH` override defaults
3. `db.py` — SQLite CRUD; `get_connection()` auto-initializes schema on first call with incremental migrations; three tables: `entries`, `invoices`, `active_session`
4. `timer.py` — start/stop/pause/resume/status using `active_session` table (enforces max 1 row)
5. `invoice.py` — PDF generation via WeasyPrint from `timecard/templates/invoice.html`; marks entries as invoiced in DB after generation
6. `sync.py` — Google Sheets upsert via gspread; `authenticate()` runs OAuth flow saving credentials locally
7. `cli.py` — Typer app wiring all commands; every command accepts `--json` flag for machine-readable output
8. `mcp_server.py` — MCP server exposing the same functions as thin wrappers (no business logic here)
9. `__main__.py` — entrypoint

**Key design decisions:**
- DB path defaults to `~/.local/share/timecard/timecard.db` (XDG data home); overridable via `TIMECARD_DB_PATH` env var for test isolation
- Config `.env` defaults to `~/.config/timecard/.env` (XDG config home); overridable via `TIMECARD_CONFIG_PATH`
- `active_session` table uses `CHECK (id = 1)` to enforce a single row; `paused_at` and `paused_duration_minutes` columns track pause state
- All CLI commands exit with code `0` (success), `1` (user error), or `2` (system/config error)
- MCP server is a pure wrapper — all business logic stays in the non-MCP modules

## Testing conventions

- Use `tmp_path` fixtures for filesystem/SQLite tests
- Mock Google API calls in `test_sync.py` (no real network requests)
- Mock WeasyPrint PDF rendering in `test_invoice.py` (test data pipeline, not renderer)
- CLI tests use Typer's `CliRunner` invoking the `timecard` app

## Configuration (.env)

```
HOURLY_RATE=150
CONTRACTOR_NAME="Jane Smith"
CONTRACTOR_ADDRESS="456 Elm St, Portland, OR"
CONTRACTOR_EMAIL="jane@example.com"
CLIENT_NAME="Acme Corp"
CLIENT_ADDRESS="123 Main St, Springfield"
INVOICE_OUTPUT_DIR=~/invoices
PAYMENT_INSTRUCTIONS="Please remit payment via ACH or check within 30 days."
GOOGLE_SHEET_ID=<optional>
TIMECARD_DB_PATH=~/.local/share/timecard/timecard.db
TIMECARD_CONFIG_PATH=<optional path to .env file>
```
