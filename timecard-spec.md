# TimeCard CLI — Project Specification

## Overview
A Python CLI tool for 1099 contractors to track billable hours, manage time entries, generate PDF invoices, and optionally back up data to Google Sheets. Designed to be AI-native and agent-callable via both a CLI and an MCP server.

---

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | WeasyPrint & gspread are Python-native; best-in-class for this use case |
| Packaging | [uv](https://github.com/astral-sh/uv) + `pyproject.toml` | Single-command installs, manages Python version + venv automatically |
| CLI framework | [Typer](https://typer.tiangolo.com/) | Modern, type-annotated, auto-generates `--help` |
| Local storage | SQLite via `sqlite3` (stdlib) | Zero-dependency, reliable, queryable |
| PDF generation | [WeasyPrint](https://weasyprint.org/) | HTML/CSS template → PDF; supports custom templates in future |
| Google integration | [gspread](https://gspread.readthedocs.io/) + `google-auth` | Sheets backup |
| MCP server | [mcp](https://github.com/modelcontextprotocol/python-sdk) (Anthropic Python SDK) | Exposes tracker as agent-callable tools |
| Config management | [python-dotenv](https://pypi.org/project/python-dotenv/) | Store rate, name, client info |
| Date/time | `datetime` (stdlib) | Timer state |

---

## Distribution & Installation

### Developer install (from source)
```bash
uv tool install .
```

### End-user install scripts
- `install.sh` — Mac/Linux: installs `uv` if absent, installs WeasyPrint system deps via `brew` or `apt`, installs the tool
- `install.ps1` — Windows: installs `uv`, handles WeasyPrint dependencies, installs the tool

### Future
- Publish to PyPI so `uv tool install timetracker` works without pointing at the repo
- Optional Homebrew formula for Mac users

---

## Configuration (`.env` or config file)

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
```

> **Note:** Do not include bank account or routing numbers in config or invoice templates. Provide banking details to your client once via their secure vendor onboarding process.

---

## Features & Commands

### 1. Timer — `tracker start` / `tracker stop`
- `timecard start` — records a session start timestamp in SQLite; errors if a session is already running
- `timecard stop` — records end timestamp, calculates duration, writes completed entry to DB
- `timecard status` — shows whether a timer is running and for how long

### 2. Manual Entry — `timecard add`
- `timecard add --date 2025-01-15 --hours 3.5 --note "API design work"`
- Inserts a completed entry directly without using the timer
- `--note` is optional but stored for invoice line items

### 3. Entry Management — `timecard log` / `timecard edit` / `timecard delete`
- `timecard log [--period biweekly|week|month]` — tabular view of entries with IDs, dates, hours, notes
- `timecard edit <id> --hours 2.0 --note "updated note"` — update any field on an entry
- `timecard delete <id>` — remove an entry (with confirmation prompt)

### 4. Invoice Generation — `timecard invoice`
- `timecard invoice [--period biweekly] [--output path/to/file.pdf] [--note "Q1 backend development"]`
- Aggregates all uninvoiced entries in the period
- Renders a professional PDF from an HTML/CSS template with: contractor info, client info, invoice number, line items (date + hours + note), subtotal hours, rate, total due, and payment instructions
- Marks entries as invoiced in DB so they aren't double-counted
- Invoice number auto-increments

### 5. Cloud Backup — `timecard sync`
- `timecard sync` — pushes all entries to a configured Google Sheet (upserts by entry ID)
- Requires one-time OAuth setup via `timecard auth`
- `timecard auth` — runs Google OAuth flow, saves credentials locally

### 6. MCP Server — `timecard mcp`
- `timecard mcp` — starts a local MCP server that exposes tracker functionality as agent-callable tools
- Thin wrapper over existing CLI functions; no duplicated business logic
- Configured as a local MCP server in the agent client's config (e.g. `claude_desktop_config.json`)

**Exposed MCP tools:**

| Tool | Arguments | Description |
|---|---|---|
| `start_timer` | none | Start a timer session |
| `stop_timer` | none | Stop current session, log entry |
| `get_status` | none | Is a timer running? How long? |
| `add_entry` | date, hours, note? | Manually log time |
| `get_log` | period? | Return entries as JSON |
| `edit_entry` | id, hours?, note? | Update an entry |
| `delete_entry` | id | Delete an entry |
| `generate_invoice` | period?, note? | Generate PDF invoice |
| `sync_to_sheets` | none | Push entries to Google Sheets |

---

## Data Model (SQLite)

### `entries` table
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | auto-increment |
| started_at | TEXT | ISO 8601 |
| ended_at | TEXT | ISO 8601, nullable (in-progress) |
| duration_minutes | REAL | computed on stop |
| note | TEXT | optional |
| invoiced | INTEGER | 0 or 1, default 0 |
| invoice_id | INTEGER | FK to invoices, nullable |

### `invoices` table
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | auto-increment |
| invoice_number | TEXT | e.g. INV-0042 |
| period_start | TEXT | ISO 8601 date |
| period_end | TEXT | ISO 8601 date |
| total_hours | REAL | |
| total_amount | REAL | hours × rate |
| created_at | TEXT | |
| pdf_path | TEXT | local path to generated PDF |
| note | TEXT | optional project/work description |

### `active_session` table
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | always 1 row max |
| started_at | TEXT | ISO 8601 |

---

## Dependency Graph

```
pyproject.toml / uv
└── tracker/
    ├── __main__.py               # entrypoint
    ├── cli.py                    # Typer app, all commands
    │   ├── depends on: db.py
    │   ├── depends on: timer.py
    │   ├── depends on: invoice.py
    │   └── depends on: sync.py
    │
    ├── mcp_server.py             # MCP server, exposes tools to agents
    │   ├── depends on: timer.py
    │   ├── depends on: db.py
    │   ├── depends on: invoice.py
    │   └── depends on: sync.py
    │
    ├── db.py                     # SQLite init, CRUD operations
    │   └── depends on: models.py
    │
    ├── models.py                 # Dataclasses: Entry, Invoice, Session
    │   └── no dependencies
    │
    ├── timer.py                  # start/stop/status logic
    │   └── depends on: db.py
    │
    ├── invoice.py                # PDF generation, invoice numbering
    │   ├── depends on: db.py
    │   ├── depends on: config.py
    │   └── depends on: templates/invoice.html
    │
    ├── sync.py                   # Google Sheets integration
    │   ├── depends on: db.py
    │   └── depends on: config.py
    │
    ├── config.py                 # Load .env, expose settings
    │   └── depends on: python-dotenv
    │
    └── templates/
        └── invoice.html          # WeasyPrint HTML/CSS invoice template
```

---

## Build Order for Claude Code

Build in this sequence to respect dependencies:

1. **`models.py`** — dataclasses, no deps
2. **`config.py`** — env loading
3. **`db.py`** — SQLite schema + CRUD
4. **`timer.py`** — start/stop/status
5. **`templates/invoice.html`** — HTML/CSS invoice layout
6. **`invoice.py`** — PDF generation
7. **`sync.py`** — Google Sheets backup
8. **`cli.py`** — all Typer commands wired together
9. **`mcp_server.py`** — MCP tool wrappers over existing modules
10. **`__main__.py`** — entrypoint
11. **`install.sh` / `install.ps1`** — cross-platform install scripts

---

## Non-Functional Requirements

- All CLI commands return **machine-readable JSON** when called with `--json` flag
- Exit codes: `0` success, `1` user error, `2` system/config error
- DB path and config path overridable via env vars (`TRACKER_DB_PATH`, `TRACKER_CONFIG_PATH`) for testability
- First run auto-initializes SQLite schema if DB doesn't exist
- Google sync and MCP server are optional — tool works fully offline without them configured
- MCP server contains no business logic — it is a pure wrapper over the same functions used by the CLI

---

## Instructions for Claude Code

### General approach
- Build exactly one module at a time, strictly following the build order above
- Do not begin a new module until the current one has passing tests
- After completing all modules, verify the full integration test suite passes before considering the project done
- If you encounter an ambiguity not covered by this spec, make the conservative choice and leave a `# TODO:` comment explaining the decision

### Per-module workflow
For each module, follow this sequence:
1. Write the module implementation
2. Write the corresponding test file (`tests/test_<module>.py`)
3. Run the tests with `uv run pytest tests/test_<module>.py -v`
4. Fix any failures before proceeding
5. Confirm all previously passing tests still pass (`uv run pytest -v`)

### Test requirements
- Use `pytest` for all tests
- Use `tmp_path` fixtures for any tests that touch the filesystem or SQLite
- Mock Google API calls in `test_sync.py` — do not make real network requests
- Mock WeasyPrint's PDF rendering in `test_invoice.py` — test the data pipeline, not the renderer
- Every CLI command must have at least one test via Typer's `CliRunner` using the `timecard` command name
- Every MCP tool must have at least one unit test confirming it returns the expected structure
- Aim for coverage of both happy path and common error cases (e.g. stopping a timer that isn't running, editing a nonexistent entry)

### Integration test
After all modules are complete, write `tests/test_integration.py` that exercises a complete end-to-end workflow:
1. Start a timer
2. Stop the timer
3. Add a manual entry
4. Edit that entry
5. Generate an invoice
6. Verify the invoice PDF file exists on disk
7. Verify the entries are marked as invoiced in the DB

---

## Documentation Requirements

### `README.md`
Must include:
- Project overview (one paragraph)
- Prerequisites (Python version, WeasyPrint system deps by platform)
- Installation instructions for Mac, Linux, and Windows using the install scripts
- Configuration: full list of `.env` variables with descriptions and example values
- Usage: one example per CLI command with sample output
- MCP setup: how to add the server to `claude_desktop_config.json`
- Google Sheets setup: how to run `tracker auth` and what permissions are requested
- A note on invoice security (no banking details in invoices)

### Inline code documentation
- Every public function must have a docstring describing what it does, its parameters, and return value
- Every module must have a module-level docstring explaining its responsibility in one or two sentences
- Complex logic (e.g. biweekly period calculation, invoice number generation) must have inline comments

### `CHANGELOG.md`
- Initialized with a `[1.0.0]` entry listing all v1 features
- Follow [Keep a Changelog](https://keepachangelog.com/) format

### `docs/mcp.md`
- Explain what MCP is in 2-3 sentences for users unfamiliar with it
- List every exposed tool with its arguments, types, and a one-line description
- Provide a sample agent interaction showing a natural language prompt and the resulting tool calls

---

## Out of Scope (v1)

- Multiple clients or rates
- Custom invoice templates (HTML template is hardcoded in v1; template path made configurable in v2)
- Web UI or TUI dashboard
- Time rounding rules (e.g. bill in 15-min increments)
- Automated invoice emailing
- PyPI publish / Homebrew formula
