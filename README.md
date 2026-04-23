# TimeCard

A Python CLI tool for 1099 contractors to track billable hours, manage time entries, and generate PDF invoices. Designed to be AI-native and agent-callable via both a CLI and an MCP server.

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
uv cache clean && uv tool install --reinstall .
```

Re-run the same command to pick up changes. The cache clear ensures uv doesn't serve a stale build.

## Updating

```bash
timecard update
```

Clears the uv cache for TimeCard and reinstalls the latest version from GitHub. Works from any directory.

## Configuration

Run the interactive setup wizard to configure TimeCard:

```bash
timecard setup
```

This creates a config file at `~/.config/timecard/.env` (or the path set by `TIMECARD_CONFIG_PATH`).

### Settings managed by `timecard setup`

| Variable | Description | Example |
|---|---|---|
| `CONTRACTOR_NAME` | Your name | `Jane Smith` |
| `CONTRACTOR_ADDRESS` | Your address | `456 Elm St, Portland, OR` |
| `CONTRACTOR_EMAIL` | Your email | `jane@example.com` |
| `CLIENT_NAME` | Client's name | `Acme Corp` |
| `CLIENT_ADDRESS` | Client's address | `123 Main St, Springfield` |
| `HOURLY_RATE` | Billing rate per hour | `150` |
| `INVOICE_OUTPUT_DIR` | Where to save PDFs | `~/invoices` |
| `PAYMENT_INSTRUCTIONS` | Text on invoices | `Please remit payment via ACH within 30 days.` |
| `INVOICE_NUMBER_START` | Offset added to auto-incremented invoice numbers (for migrating from a prior system) | `100` → first invoice is `INV-0101` |

### Advanced overrides (environment variables only)

These have sensible XDG-compliant defaults and do not need to be set for most users:

| Variable | Description | Default |
|---|---|---|
| `TIMECARD_CONFIG_PATH` | Override config file location | `~/.config/timecard/.env` |
| `TIMECARD_DB_PATH` | Override database location | `~/.local/share/timecard/timecard.db` |

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
$ timecard invoice generate --note "January backend work"
status: generated
invoice_number: INV-0001
total_hours: 3.01
total_amount: 451.5
pdf_path: /home/user/invoices/INV-0001.pdf
paid_at: None

$ timecard invoice generate --period month --output ./custom-invoice.pdf

# Override the invoice number for a single invocation
$ timecard invoice generate --number 42
invoice_number: INV-0042
```

When no `--period` is specified, all uninvoiced entries are included. Period options (`week`, `biweekly`, `month`) use calendar-aligned windows (e.g., last complete Mon–Sun week, last complete calendar month).

To start invoice numbering at a specific offset (e.g. when migrating from a prior system), set `INVOICE_NUMBER_START` in your `.env`. With `INVOICE_NUMBER_START=100`, the first invoice will be `INV-0101`.

### List invoices

```bash
$ timecard invoice list
ID    NUMBER      PERIOD                          HOURS   AMOUNT      PAID AT
----------------------------------------------------------------------------
1     INV-0001    2025-01-01 – 2025-01-15        3.01    $451.50     —
2     INV-0002    2025-01-16 – 2025-01-31        8.00    $1200.00    Jan 31, 2025

# Filter to outstanding or settled invoices
$ timecard invoice list --unpaid
$ timecard invoice list --paid --json
```

### Mark an invoice as paid

```bash
# By invoice number or ID — both work
$ timecard invoice paid INV-0001
$ timecard invoice paid 1

# Record a specific payment date
$ timecard invoice paid INV-0001 --date 2025-02-01

# Undo a payment (e.g. if marked paid by mistake)
$ timecard invoice unpaid INV-0001
```

### JSON output

All commands except `export` support `--json` for machine-readable output (`export` always outputs CSV):

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

## Multi-Machine Use

TimeCard stores all data in a single SQLite file. To share it across machines, set `TIMECARD_DB_PATH` to a location that is accessible from each machine — a synced folder (Google Drive, Proton Drive, Dropbox, Syncthing, etc.) or a network share both work well:

```bash
# In ~/.config/timecard/.env
TIMECARD_DB_PATH="~/Google Drive/My Drive/timecard/timecard.db"
```

> **Note:** Avoid running TimeCard on two machines simultaneously against the same database file. SQLite is not designed for concurrent multi-writer access, and file sync tools that hold files open during sync can cause locking conflicts. As long as only one machine is active at a time this approach is reliable.

