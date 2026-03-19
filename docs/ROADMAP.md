# TimeCard Product Roadmap

## v1.0.0 (Current)
- Timer-based and manual time entry
- Entry management (log, edit, delete)
- PDF invoice generation with calendar-aligned billing periods
- CSV export for data portability
- MCP server for AI agent integration
- JSON output mode on all commands (except `export`, which outputs CSV)
- Cross-platform install scripts

## v1.1 — Quality of Life
- [x] CSV export (`timecard export`) for frictionless data portability
- [x] Command autocomplete installed automatically during install (`install.sh` / `install.ps1`)
- [x] Interactive setup wizard — prompt for contractor/client info during install to generate `.env`
- [x] Update script that clears the uv cache before reinstalling to guarantee new changes are picked up (`timecard update` or a shell script)
- [x] `timecard pause` / `timecard resume` commands to pause an active session without losing the entry

## v1.2 — Invoice Number Control
- [x] Configurable invoice number start offset via `INVOICE_NUMBER_START` in `.env` — for users migrating from a prior invoicing system
- [x] `--number` flag on `timecard invoice` to override the auto-incremented number for a single invocation

## v1.3 — Invoice Lifecycle
- [ ] `timecard invoice list` command to view past invoices (number, date, total hours, amount, PDF path)
- [ ] `timecard invoice paid <invoice-number>` command to mark an invoice as paid, recording the payment date
- [ ] `--paid` / `--unpaid` filter flags on `timecard invoice list` to view outstanding or settled invoices
- [ ] Python version check in `install.sh` / `install.ps1` — fail with a clear message if the system Python is below the minimum required version, and optionally guide users to install a compatible version

## v1.4 — Multi-Machine Support
- [x] Document `TIMECARD_DB_PATH` as the recommended approach for sharing data across machines via a synced folder (Google Drive, Proton Drive, Syncthing, etc.)

## v2.0 — Multi-Client Support
- [ ] Multiple clients with per-client rates
- [ ] Client management commands (`timecard client add/list/edit`)
- [ ] Per-client invoice generation and entry filtering

## v2.1 — Custom Invoice Templates
- [ ] Configurable invoice template path
- [ ] User-provided HTML/CSS templates with documented template variables
- [ ] Bundled alternative templates (minimal, detailed, etc.)

## v3.0 — Distribution & Automation
- [ ] Publish to PyPI (`pip install timecard` / `uv tool install timecard`)
- [ ] Homebrew formula for Mac users
- [ ] Automated invoice emailing (SMTP or SendGrid integration)

---

*Priorities may shift based on user feedback. Open an issue to suggest features or vote on existing ones.*
