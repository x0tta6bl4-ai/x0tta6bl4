# Public URL Snapshot Buyer Kit

## What This Is

This kit helps an agent safely buy or run a public URL snapshot before spending more tokens on research.

Use it when an agent needs:

- Page title
- Meta description
- H1/H2/H3 headings
- Public links
- Short text preview
- HTTP status
- Redirect signal

## Safe Input

```json
{
  "url": "https://example.com",
  "max_links": 12,
  "max_text_chars": 1200
}
```

## Reject These Targets

- `localhost`
- `127.0.0.1`
- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`
- Link-local addresses
- URLs containing usernames or passwords
- Non-HTTP schemes

## Output Contract

```json
{
  "schema": "paid_url_snapshot_report.v1",
  "verdict": "ok|review|reject",
  "url": "https://example.com",
  "http_status": 200,
  "content_type": "text/html",
  "signals": {
    "public_url": true,
    "fetched": true,
    "html_like": true,
    "redirect_seen": false
  },
  "page": {
    "title": "...",
    "meta_description": "...",
    "headings": [],
    "links": [],
    "text_preview": "..."
  }
}
```

## Agent Prompt

Before deep research, snapshot the target page. If the result is `reject`, do not pay for deeper analysis. If the result is `review`, inspect the risks first. If the result is `ok`, use the title, headings, and links to decide the next paid call.

## Cost Control

This workflow saves tokens because the agent can inspect a compact page summary before loading a full page into a model.
