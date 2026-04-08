# Email Analysis Toolkit

This workspace now has a small local CLI for turning an Outlook archive into something you can analyze and use for response drafting.

## What The Inbox Looks Like

From the initial sample of the extracted inbox, this is not end-customer support. It looks like merchandising / export-operations traffic for apparel sourcing, with dominant topics like:

- costing and non-e-bid commercial discussions
- shipment, AWB, pickup, and delivery coordination
- final inspection and quality-status updates
- ERP / PO approval requests
- style, BOM, and seasonal program coordination

That means the right automation is a draft-assistant with human review, not full auto-send.

## Files

- `scripts/mailbox_agent.py`: extract PSTs, analyze mbox files, and draft responses
- `config/response_playbooks.json`: category-specific drafting rules
- `requirements.txt`: optional dependencies for better HTML parsing and OpenAI API access
- `docs/`: static GitHub Pages-ready dashboard with analysis charts and GPT-5 draft generation via Straive LLM Foundry

## Static Demo Dashboard

The static dashboard entrypoint is:

```bash
docs/index.html
```

It is built to be hosted directly from GitHub Pages without a backend. The analysis view is driven by static JSON under `docs/data/`, and the draft generator calls Straive LLM Foundry from the browser using the OpenAI-compatible API shape.

## 1. Extract The PST

If `readpst` is not installed already:

```bash
brew install libpst
```

Then extract the archive:

```bash
python3 scripts/mailbox_agent.py extract-pst Zaber_MRC_142360.pst --output-dir extracted
```

`readpst` will create one or more `mbox` files inside `extracted/`.

## 2. Analyze A Mailbox

Example:

```bash
python3 scripts/mailbox_agent.py analyze extracted/Zaber_MRC_142360/Inbox/mbox \
  --report reports/inbox_analysis.md \
  --json reports/inbox_summary.json
```

That produces:

- a Markdown report with mailbox characterization and category counts
- a JSON summary you can feed into other tooling

## 3. Generate A Draft Reply

Install Python dependencies if you want API-backed drafting:

```bash
python3 -m pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here
```

Draft from a message inside an mbox:

```bash
python3 scripts/mailbox_agent.py draft \
  --mbox extracted/Zaber_MRC_142360/Inbox/mbox \
  --subject-contains "Shipment pending"
```

Or inspect the assembled prompt without making an API call:

```bash
python3 scripts/mailbox_agent.py draft \
  --mbox extracted/Zaber_MRC_142360/Inbox/mbox \
  --subject-contains "Shipment pending" \
  --dry-run
```

## Operating Model

Use the agent for:

- first-pass buyer-facing replies
- shipment and document acknowledgements
- inspection follow-up drafts
- requests that mainly need a structured summary and a clean response template

Keep mandatory human review for:

- approvals and ERP actions
- any pricing or date commitment not explicit in the source email
- messages with important attachments that must be checked manually
- escalations or sensitive commercial negotiation
