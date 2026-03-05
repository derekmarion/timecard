# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] - 2026-03-04

### Added
- Timer commands: `timecard start`, `timecard stop`, `timecard status`
- Manual time entry: `timecard add --date YYYY-MM-DD --hours N`
- Entry management: `timecard log`, `timecard edit`, `timecard delete`
- PDF invoice generation: `timecard invoice` with HTML/CSS template via WeasyPrint
- Calendar-aligned billing periods: `--period week|biweekly|month`
- Google Sheets sync: `timecard sync` with OAuth via `timecard auth`
- MCP server: `timecard mcp` exposes all tools for AI agent integration
- JSON output mode: `--json` flag on all commands
- SQLite local storage with auto-initialized schema
- Configuration via `.env` file or environment variables
- Cross-platform install scripts (`install.sh`, `install.ps1`)
