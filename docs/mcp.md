# TimeCard MCP Server

The Model Context Protocol (MCP) is a standard for exposing tools that AI agents can call. It allows agents like Claude to interact with external systems through a structured tool interface, rather than relying on screen scraping or unstructured text.

TimeCard's MCP server wraps the same business logic as the CLI, so agents can start timers, log hours, and generate invoices through natural language.

## Starting the Server

```bash
timecard mcp
```

This starts a stdio-based MCP server. Configure it in your agent client (e.g., Claude Desktop):

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

## Exposed Tools

| Tool | Arguments | Description |
|---|---|---|
| `start_timer` | *(none)* | Start a timer session |
| `stop_timer` | *(none)* | Stop current session and log the entry |
| `pause_timer` | *(none)* | Pause the current timer session |
| `resume_timer` | *(none)* | Resume a paused timer session |
| `get_status` | *(none)* | Check if a timer is running/paused and for how long |
| `add_entry_tool` | `date: str`, `hours: float`, `note?: str` | Manually log a time entry |
| `get_log` | `period?: str` | Return entries as a list (optional period filter) |
| `edit_entry` | `id: int`, `hours?: float`, `note?: str` | Update an existing entry |
| `delete_entry_tool` | `id: int` | Delete an entry |
| `generate_invoice` | `period?: str`, `note?: str` | Generate a PDF invoice |
| `sync_to_sheets` | *(none)* | Push all entries to Google Sheets |

## Example Agent Interaction

**User prompt:** "I just finished 2 hours of frontend work. Log it for today and then generate an invoice for all my uninvoiced time."

**Agent tool calls:**

1. `add_entry_tool(date="2026-03-04", hours=2.0, note="Frontend work")`
   ```json
   {"status": "added", "entry_id": 5}
   ```

2. `generate_invoice(note="March development work")`
   ```json
   {
     "status": "generated",
     "invoice_number": "INV-0003",
     "total_hours": 12.5,
     "total_amount": 1875.00,
     "pdf_path": "/home/user/invoices/INV-0003.pdf"
   }
   ```

**Agent response:** "Done! I logged 2 hours of frontend work for today and generated invoice INV-0003 covering 12.5 hours ($1,875.00). The PDF is saved at ~/invoices/INV-0003.pdf."
