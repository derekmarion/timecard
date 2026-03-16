# TimeCard

A Python CLI tool for 1099 contractors to track billable hours, manage time entries, generate PDF invoices, and optionally back up data to Google Sheets. Designed to be AI-native and agent-callable via both a CLI and an MCP server.

## Prerequisites

- **Python 3.11+**
- **WeasyPrint system dependencies** (varies by platform — see installation below)

## Installation

### Mac / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/derekmarion/timecard/main/install.sh | bash
```

Or clone the repo and run:

```bash
./install.sh
```

This installs `uv` (if absent), WeasyPrint system deps, and the `timecard` CLI from the GitHub repository.

### Windows

```powershell
.\install.ps1
```

Installs `uv` and prompts you to install the [GTK3 runtime](https://github.com/nickvdyck/WeasyPrint-Installer/releases) if not present.

### Developer install (from source)

```bash
uv tool install .
```

## Updating

```bash
timecard update
```

Clears the uv cache for TimeCard and reinstalls the latest version from GitHub. Works from any directory.

## Configuration

Create a `.env` file in your working directory or set environment variables:

| Variable | Description | Example |
|---|---|---|
| `HOURLY_RATE` | Billing rate per hour | `150` |
| `CONTRACTOR_NAME` | Your name | `Jane Smith` |
| `CONTRACTOR_ADDRESS` | Your address | `456 Elm St, Portland, OR` |
| `CONTRACTOR_EMAIL` | Your email | `jane@example.com` |
| `CLIENT_NAME` | Client's name | `Acme Corp` |
| `CLIENT_ADDRESS` | Client's address | `123 Main St, Springfield` |
| `INVOICE_OUTPUT_DIR` | Where to save PDFs | `~/invoices` |
| `PAYMENT_INSTRUCTIONS` | Text on invoices | `Please remit payment via ACH within 30 days.` |
| `GOOGLE_SHEET_ID` | Google Sheet ID for sync (optional) | `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Og...` |
| `TIMECARD_DB_PATH` | Override database location | `~/.timecard/timecard.db` |
| `TIMECARD_CONFIG_PATH` | Override .env file location | `/path/to/.env` |

> **Security note:** Do not include bank account or routing numbers in your config or invoice templates. Provide banking details to your client once via their secure vendor onboarding process.

## Usage

### Start/stop a timer

```bash
$ timecard start
status: started
started_at: 2025-01-15T09:00:00+00:00

$ timecard pause
status: paused
paused_at: 2025-01-15T10:30:00+00:00

$ timecard resume
status: resumed
resumed_at: 2025-01-15T11:00:00+00:00

$ timecard stop
status: stopped
entry_id: 1
duration_minutes: 150.5
hours: 2.51

$ timecard status
running: False
```

### Add a manual entry

```bash
$ timecard add --date 2025-01-15 --hours 3.5 --note "API design work"
status: added
entry_id: 2
date: 2025-01-15
hours: 3.5
```

### View entries

```bash
$ timecard log
ID    Date          Hours     Note                          Invoiced
----------------------------------------------------------------------
1     2025-01-15    3.01      —                             No
2     2025-01-15    3.5       API design work               No

$ timecard log --period week --json
[{"id": 1, "date": "2025-01-15", "hours": 3.01, "note": null, "invoiced": false}]
```

### Edit an entry

```bash
$ timecard edit 2 --hours 4.0 --note "Updated API design"
status: updated
entry_id: 2
```

### Delete an entry

```bash
$ timecard delete 2
Delete entry 2? [y/N]: y
status: deleted
entry_id: 2
```

### Generate an invoice

```bash
$ timecard invoice --note "January backend work"
status: generated
invoice_number: INV-0001
total_hours: 3.01
total_amount: 451.5
pdf_path: /home/user/invoices/INV-0001.pdf

$ timecard invoice --period month --output ./custom-invoice.pdf
```

When no `--period` is specified, all uninvoiced entries are included. Period options (`week`, `biweekly`, `month`) use calendar-aligned windows (e.g., last complete Mon–Sun week, last complete calendar month).

### Sync to Google Sheets

```bash
$ timecard auth    # one-time OAuth setup
$ timecard sync
status: synced
entries_synced: 5
```

### JSON output

All commands support `--json` for machine-readable output:

```bash
$ timecard status --json
{"running": false}
```

## MCP Server Setup

TimeCard exposes an MCP server for AI agent integration. Add it to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "timecard": {
      "command": "timecard",
      "args": ["mcp"]
    }
  }
}
```

See [docs/mcp.md](docs/mcp.md) for the full list of exposed tools.

## Google Sheets Setup

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google Sheets API
3. Create OAuth 2.0 credentials (Desktop application type)
4. Download the client secrets JSON and save it to `~/.timecard/client_secrets.json`
5. Run `timecard auth` — this opens a browser for OAuth consent
6. The tool requests read/write access to Google Sheets only
