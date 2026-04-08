#!/usr/bin/env python3
"""Mailbox analysis and response-drafting toolkit for Outlook exports."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.parser import BytesHeaderParser, BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Iterable

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional dependency
    BeautifulSoup = None


INTERNAL_DOMAINS = {
    "standardmhgroup.com",
    "standard-group.com",
}


CATEGORY_RULES: list[tuple[str, list[str]]] = [
    (
        "shipment_logistics",
        [
            r"\bshipment\b",
            r"\bshipping\b",
            r"\bawb\b",
            r"\bdhl\b",
            r"\bpickup\b",
            r"\bdelivery\b",
            r"\bvessel\b",
            r"\bbooking\b",
            r"\beta\b",
            r"\bport\b",
            r"\bair port\b",
        ],
    ),
    (
        "inspection_quality",
        [
            r"\binspection\b",
            r"\bfinal inspection\b",
            r"\bpass(?:ed)?\b",
            r"\bfailed\b",
            r"\bquality\b",
            r"\baudit\b",
            r"\bdefect\b",
        ],
    ),
    (
        "costing_pricing",
        [
            r"\bcost(?:ing)?\b",
            r"\btarget cost\b",
            r"\bprice\b",
            r"\bpricing\b",
            r"\bnon-e-bid\b",
            r"\bmou\b",
        ],
    ),
    (
        "internal_approval",
        [
            r"\berp\b",
            r"\bapprove\b",
            r"\bapproval\b",
            r"\bpo approve\b",
            r"\baction required\b",
        ],
    ),
    (
        "production_status",
        [
            r"\bdaily production\b",
            r"\bdpr\b",
            r"\bstatus\b",
            r"\bline input\b",
            r"\bwash balance\b",
            r"\bshipment pending\b",
        ],
    ),
    (
        "development_program",
        [
            r"\bstyle\b",
            r"\bbom\b",
            r"\bsample\b",
            r"\bproto\b",
            r"\bfit\b",
            r"\blab dip\b",
            r"\bsp[- ]?\d+\b",
            r"\bhol['-]?\d+\b",
            r"\bfall['-]?\d+\b",
            r"\bsum[- ]?\d+\b",
            r"\bla\b",
        ],
    ),
    (
        "documents_commercial",
        [
            r"\binvoice\b",
            r"\blc\b",
            r"\bpo\b",
            r"\border\b",
            r"\breport\b",
            r"\bpi\b",
            r"\bawb confirmation\b",
        ],
    ),
    (
        "collaboration_misc",
        [
            r"\bcomment\b",
            r"\bbrand approved\b",
            r"\bmiro\b",
            r"\bnotification\b",
        ],
    ),
]


REPLY_PREFIX_RE = re.compile(r"^(?:RE|FW|FWD)\s*:\s*", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class MessageSummary:
    subject: str
    normalized_subject: str
    sender: str
    sender_domain: str
    to: list[str]
    cc: list[str]
    date: str | None
    direction: str
    category: str
    snippet: str
    attachment_count: int
    is_external: bool


def normalize_subject(subject: str) -> str:
    current = (subject or "").strip()
    while True:
        updated = REPLY_PREFIX_RE.sub("", current)
        if updated == current:
            return current
        current = updated.strip()


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    lines = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            continue
        if line.lower().startswith(("from:", "sent:", "to:", "cc:", "subject:")):
            break
        lines.append(line)
    return WHITESPACE_RE.sub(" ", " ".join(lines)).strip()


def html_to_text(html: str) -> str:
    if BeautifulSoup is not None:
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return html


def iter_mbox_messages(mbox_path: Path) -> Iterable[bytes]:
    current: list[bytes] = []
    with mbox_path.open("rb") as handle:
        for line in handle:
            if line.startswith(b"From "):
                if current:
                    yield _strip_mbox_separator(current)
                current = [line]
            else:
                current.append(line)
        if current:
            yield _strip_mbox_separator(current)


def _strip_mbox_separator(lines: list[bytes]) -> bytes:
    if lines and lines[0].startswith(b"From "):
        return b"".join(lines[1:])
    return b"".join(lines)


def parse_email(raw_message: bytes):
    return BytesParser(policy=policy.default).parsebytes(raw_message)


def addresses(value: str | None) -> list[str]:
    pairs = getaddresses([value or ""])
    emails = []
    for _, email in pairs:
        email = email.strip().lower()
        if email:
            emails.append(email)
    return emails


def sender_domain(sender_email: str) -> str:
    if "@" not in sender_email:
        return ""
    return sender_email.rsplit("@", 1)[-1].lower()


def direction_of(sender_email: str, recipients: list[str]) -> str:
    sender_internal = sender_domain(sender_email) in INTERNAL_DOMAINS
    recipient_domains = {sender_domain(addr) for addr in recipients}
    has_external_recipient = any(domain and domain not in INTERNAL_DOMAINS for domain in recipient_domains)
    if sender_internal and has_external_recipient:
        return "internal_to_external"
    if not sender_internal and any(domain in INTERNAL_DOMAINS for domain in recipient_domains):
        return "external_to_internal"
    if sender_internal:
        return "internal_only"
    return "external_only"


def extract_text_parts(message) -> tuple[str, str]:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            disposition = (part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            ctype = part.get_content_type()
            if ctype not in {"text/plain", "text/html"}:
                continue
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="replace")
            if ctype == "text/plain":
                plain_parts.append(content)
            else:
                html_parts.append(content)
    else:
        ctype = message.get_content_type()
        try:
            content = message.get_content()
        except Exception:
            payload = message.get_payload(decode=True) or b""
            charset = message.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
        if ctype == "text/plain":
            plain_parts.append(content)
        elif ctype == "text/html":
            html_parts.append(content)

    plain_text = clean_text(" ".join(plain_parts))
    if plain_text:
        return plain_text, "text/plain"

    html_text = clean_text(html_to_text(" ".join(html_parts)))
    return html_text, "text/html"


def attachment_count(message) -> int:
    count = 0
    for part in message.walk():
        disposition = (part.get_content_disposition() or "").lower()
        if disposition == "attachment" or part.get_filename():
            count += 1
    return count


def classify_message(subject: str, body: str) -> str:
    normalized_subject = normalize_subject(subject)
    score = Counter()
    for category, patterns in CATEGORY_RULES:
        for pattern in patterns:
            regex = re.compile(pattern, re.IGNORECASE)
            if regex.search(normalized_subject):
                score[category] += 3
            if body and regex.search(body):
                score[category] += 1
    if not score:
        return "other"
    return score.most_common(1)[0][0]


def summarize_message(message) -> MessageSummary:
    sender_candidates = addresses(message.get("from"))
    sender = sender_candidates[0] if sender_candidates else ""
    to_addrs = addresses(message.get("to"))
    cc_addrs = addresses(message.get("cc"))
    body_text, _ = extract_text_parts(message)
    category = classify_message(message.get("subject", ""), body_text)
    direction = direction_of(sender, to_addrs + cc_addrs)
    external = direction in {"internal_to_external", "external_to_internal", "external_only"}
    date_header = message.get("date")
    parsed_date = None
    if date_header:
        try:
            parsed_date = parsedate_to_datetime(date_header).isoformat()
        except Exception:
            parsed_date = date_header

    return MessageSummary(
        subject=message.get("subject", "").strip(),
        normalized_subject=normalize_subject(message.get("subject", "")),
        sender=sender,
        sender_domain=sender_domain(sender),
        to=to_addrs,
        cc=cc_addrs,
        date=parsed_date,
        direction=direction,
        category=category,
        snippet=body_text[:400],
        attachment_count=attachment_count(message),
        is_external=external,
    )
}


def summarize_headers(message) -> MessageSummary:
    sender_candidates = addresses(message.get("from"))
    sender = sender_candidates[0] if sender_candidates else ""
    to_addrs = addresses(message.get("to"))
    cc_addrs = addresses(message.get("cc"))
    category = classify_message(message.get("subject", ""), "")
    direction = direction_of(sender, to_addrs + cc_addrs)
    external = direction in {"internal_to_external", "external_to_internal", "external_only"}
    date_header = message.get("date")
    parsed_date = None
    if date_header:
        try:
            parsed_date = parsedate_to_datetime(date_header).isoformat()
        except Exception:
            parsed_date = date_header

    has_attach_header = str(message.get("x-ms-has-attach", "")).strip().lower()
    attachment_hint = 1 if has_attach_header in {"yes", "true"} else 0

    return MessageSummary(
        subject=message.get("subject", "").strip(),
        normalized_subject=normalize_subject(message.get("subject", "")),
        sender=sender,
        sender_domain=sender_domain(sender),
        to=to_addrs,
        cc=cc_addrs,
        date=parsed_date,
        direction=direction,
        category=category,
        snippet="",
        attachment_count=attachment_hint,
        is_external=external,
    )
}


def load_playbooks(playbook_path: Path) -> dict[str, dict]:
    with playbook_path.open() as handle:
        return json.load(handle)


def build_analysis(mbox_path: Path, playbook_path: Path, sample_limit: int) -> dict:
    playbooks = load_playbooks(playbook_path)
    messages: list[MessageSummary] = []
    date_values: list[datetime] = []
    sample_counts: Counter = Counter()

    for raw_message in iter_mbox_messages(mbox_path):
        headers = BytesHeaderParser(policy=policy.default).parsebytes(raw_message)
        summary = summarize_headers(headers)

        if sample_counts[summary.category] < sample_limit:
            message = parse_email(raw_message)
            full_summary = summarize_message(message)
            summary = MessageSummary(
                subject=summary.subject,
                normalized_subject=summary.normalized_subject,
                sender=summary.sender,
                sender_domain=summary.sender_domain,
                to=summary.to,
                cc=summary.cc,
                date=summary.date,
                direction=summary.direction,
                category=summary.category,
                snippet=full_summary.snippet,
                attachment_count=max(summary.attachment_count, full_summary.attachment_count),
                is_external=summary.is_external,
            )
            sample_counts[summary.category] += 1
        messages.append(summary)
        if summary.date:
            try:
                date_values.append(datetime.fromisoformat(summary.date))
            except Exception:
                pass

    category_counts = Counter(item.category for item in messages)
    direction_counts = Counter(item.direction for item in messages)
    sender_counts = Counter(item.sender for item in messages if item.sender)
    domain_counts = Counter(item.sender_domain for item in messages if item.sender_domain)
    subject_counts = Counter(item.normalized_subject for item in messages)

    external_messages = [item for item in messages if item.is_external]
    external_domains = Counter()
    for item in messages:
        participants = [item.sender, *item.to, *item.cc]
        for address in participants:
            domain = sender_domain(address)
            if domain and domain not in INTERNAL_DOMAINS:
                external_domains[domain] += 1

    samples_by_category: dict[str, list[dict]] = defaultdict(list)
    for item in sorted(messages, key=lambda current: (not current.is_external, current.subject.lower())):
        bucket = samples_by_category[item.category]
        if len(bucket) >= sample_limit:
            continue
        bucket.append(
            {
                "subject": item.subject,
                "sender": item.sender,
                "date": item.date,
                "direction": item.direction,
                "attachment_count": item.attachment_count,
                "snippet": item.snippet,
            }
        )

    start_date = min(date_values).date().isoformat() if date_values else None
    end_date = max(date_values).date().isoformat() if date_values else None

    return {
        "source_mbox": str(mbox_path),
        "playbook_file": str(playbook_path),
        "message_count": len(messages),
        "date_range": {"start": start_date, "end": end_date},
        "external_message_count": len(external_messages),
        "direction_counts": dict(direction_counts.most_common()),
        "category_counts": dict(category_counts.most_common()),
        "top_senders": _pairs(sender_counts, 15),
        "top_sender_domains": _pairs(domain_counts, 15),
        "top_external_domains": _pairs(external_domains, 15),
        "top_subjects": _pairs(subject_counts, 20),
        "automation_candidates": _automation_candidates(category_counts, playbooks),
        "samples_by_category": dict(samples_by_category),
        "observations": build_observations(category_counts, direction_counts, external_domains, playbooks),
    }


def _pairs(counter: Counter, limit: int) -> list[dict[str, object]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def _automation_candidates(category_counts: Counter, playbooks: dict[str, dict]) -> list[dict]:
    results = []
    for category, count in category_counts.most_common():
        playbook = playbooks.get(category, playbooks["other"])
        results.append(
            {
                "category": category,
                "count": count,
                "automation_fit": playbook["automation_fit"],
                "description": playbook["description"],
            }
        )
    return results


def build_observations(
    category_counts: Counter,
    direction_counts: Counter,
    external_domains: Counter,
    playbooks: dict[str, dict],
) -> list[str]:
    dominant = [category for category, _ in category_counts.most_common(3)]
    dominant_text = ", ".join(dominant) if dominant else "other"
    observations = [
        "This inbox looks like buyer / merchandising / export-operations coordination rather than consumer customer support.",
        f"Top workflow categories are {dominant_text}.",
        "Mixed internal-external traffic suggests the best automation target is human-reviewed draft generation, not full auto-send.",
    ]
    if external_domains:
        observations.append(
            "External counterparties are concentrated in a small set of domains, led by "
            + ", ".join(domain for domain, _ in external_domains.most_common(4))
            + "."
        )
    if direction_counts.get("internal_only", 0):
        observations.append(
            "Internal-only traffic is still significant, so approval and status workflows should be triaged separately from buyer-facing replies."
        )
    review_heavy = [
        category
        for category, _ in category_counts.most_common()
        if playbooks.get(category, playbooks["other"])["automation_fit"] == "Human review required"
    ]
    if review_heavy:
        observations.append(
            "Keep mandatory review on: " + ", ".join(review_heavy[:4]) + "."
        )
    return observations


def render_report(analysis: dict, playbooks: dict[str, dict]) -> str:
    lines = [
        "# Email Archive Analysis",
        "",
        f"- Source mbox: `{analysis['source_mbox']}`",
        f"- Messages analyzed: `{analysis['message_count']}`",
        f"- Date range: `{analysis['date_range']['start']}` to `{analysis['date_range']['end']}`",
        f"- Messages with external parties: `{analysis['external_message_count']}`",
        "",
        "## What This Mailbox Is",
        "",
    ]
    for observation in analysis["observations"]:
        lines.append(f"- {observation}")

    lines.extend(
        [
            "",
            "## Dominant Categories",
            "",
            "| Category | Count | Automation Fit |",
            "| --- | ---: | --- |",
        ]
    )
    for item in analysis["automation_candidates"]:
        lines.append(f"| {item['category']} | {item['count']} | {item['automation_fit']} |")

    lines.extend(
        [
            "",
            "## Top External Domains",
            "",
            "| Domain | Count |",
            "| --- | ---: |",
        ]
    )
    for item in analysis["top_external_domains"][:10]:
        lines.append(f"| {item['value']} | {item['count']} |")

    lines.extend(
        [
            "",
            "## Recommended Agent Scope",
            "",
            "- Start with draft generation for `shipment_logistics`, `costing_pricing`, `inspection_quality`, and `documents_commercial`.",
            "- Keep `internal_approval` and any message with numeric commitments or attachments in human review.",
            "- Use category-specific prompts so the agent asks for missing data instead of inventing shipment dates, prices, or approvals.",
            "",
            "## Representative Samples",
            "",
        ]
    )

    for category, samples in analysis["samples_by_category"].items():
        if not samples:
            continue
        lines.append(f"### {category}")
        lines.append("")
        for sample in samples:
            lines.append(
                f"- `{sample['date']}` | `{sample['direction']}` | `{sample['sender']}` | `{sample['subject']}`"
            )
            if sample["snippet"]:
                lines.append(f"  Snippet: {sample['snippet']}")
        lines.append("")

    lines.extend(["## Playbook Notes", ""])
    for category, config in playbooks.items():
      if category == "other":
        continue
      lines.append(f"- `{category}`: {config['description']} Review mode: {config['automation_fit']}.")

    return "\n".join(lines).strip() + "\n"


def select_message(
    *,
    email_file: Path | None,
    mbox_path: Path | None,
    subject_contains: str | None,
    match_index: int,
) -> tuple[MessageSummary, str]:
    if email_file is not None:
        raw_message = email_file.read_bytes()
        message = parse_email(raw_message)
        summary = summarize_message(message)
        body_text, _ = extract_text_parts(message)
        return summary, body_text

    if mbox_path is None or not subject_contains:
        raise ValueError("Provide either --email-file or both --mbox and --subject-contains.")

    match_number = 0
    needle = subject_contains.lower()
    for raw_message in iter_mbox_messages(mbox_path):
        message = parse_email(raw_message)
        subject = message.get("subject", "")
        if needle not in subject.lower():
            continue
        if match_number == match_index:
            summary = summarize_message(message)
            body_text, _ = extract_text_parts(message)
            return summary, body_text
        match_number += 1

    raise FileNotFoundError(f"No matching message found for subject filter: {subject_contains!r}")


def build_prompt(summary: MessageSummary, body_text: str, playbook: dict) -> tuple[str, str]:
    instructions = (
        "You draft professional email replies for a garment manufacturing / merchandising team. "
        "Be concise, factual, and operationally clear. Never invent prices, approvals, dates, quantities, shipment details, or inspection outcomes. "
        "If a required fact is missing, say so and ask for the minimum follow-up needed. "
        "Assume every draft must be human-reviewed before sending."
    )
    user_prompt = f"""
Category: {summary.category}
Automation fit: {playbook["automation_fit"]}
Category description: {playbook["description"]}
Drafting guidance: {playbook["response_style"]}
Must not assume: {", ".join(playbook["must_not_assume"])}

Message metadata
- Subject: {summary.subject}
- Sender: {summary.sender}
- To: {", ".join(summary.to) or "(none)"}
- Cc: {", ".join(summary.cc) or "(none)"}
- Date: {summary.date or "(unknown)"}
- Direction: {summary.direction}
- Attachments: {summary.attachment_count}

Body
{body_text[:12000] or "(no usable body text extracted)"}

Return valid JSON with exactly these keys:
- category
- intent_summary
- draft_response
- missing_information
- human_review_flags
""".strip()
    return instructions, user_prompt


def draft_response(
    *,
    summary: MessageSummary,
    body_text: str,
    playbook_path: Path,
    model: str,
    output_path: Path | None,
    dry_run: bool,
) -> dict:
    playbooks = load_playbooks(playbook_path)
    playbook = playbooks.get(summary.category, playbooks["other"])
    instructions, user_prompt = build_prompt(summary, body_text, playbook)

    result = {
        "category": summary.category,
        "automation_fit": playbook["automation_fit"],
        "subject": summary.subject,
        "sender": summary.sender,
        "direction": summary.direction,
        "attachment_count": summary.attachment_count,
        "prompt_preview": {
            "instructions": instructions,
            "user_prompt": user_prompt,
        },
    }
    if dry_run:
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(result, indent=2))
        return result

    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=user_prompt,
    )
    output_text = getattr(response, "output_text", "")
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        parsed = {"raw_response": output_text}
    result["response"] = parsed
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2))
    return result


def ensure_parent(path: Path | None) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)


def run_extract_pst(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "readpst",
        "-e",
        "-r",
        "-b",
        "-j",
        str(args.jobs),
        "-o",
        str(output_dir),
        str(Path(args.pst).resolve()),
    ]
    print("Running:", " ".join(cmd), file=sys.stderr)
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def run_analyze(args: argparse.Namespace) -> int:
    playbook_path = Path(args.playbooks).resolve()
    mbox_path = Path(args.mbox).resolve()
    analysis = build_analysis(mbox_path, playbook_path, args.sample_limit)
    playbooks = load_playbooks(playbook_path)
    report_text = render_report(analysis, playbooks)

    if args.report:
        report_path = Path(args.report).resolve()
        ensure_parent(report_path)
        report_path.write_text(report_text)
    if args.json:
        json_path = Path(args.json).resolve()
        ensure_parent(json_path)
        json_path.write_text(json.dumps(analysis, indent=2))

    print(report_text)
    return 0


def run_draft(args: argparse.Namespace) -> int:
    playbook_path = Path(args.playbooks).resolve()
    summary, body_text = select_message(
        email_file=Path(args.email_file).resolve() if args.email_file else None,
        mbox_path=Path(args.mbox).resolve() if args.mbox else None,
        subject_contains=args.subject_contains,
        match_index=args.match_index,
    )
    output_path = Path(args.output).resolve() if args.output else None
    result = draft_response(
        summary=summary,
        body_text=body_text,
        playbook_path=playbook_path,
        model=args.model,
        output_path=output_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract-pst", help="Extract a PST into mbox output with readpst.")
    extract_parser.add_argument("pst", help="Path to the Outlook PST archive.")
    extract_parser.add_argument("--output-dir", default="extracted", help="Directory for readpst output.")
    extract_parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    extract_parser.set_defaults(func=run_extract_pst)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze an extracted mbox file.")
    analyze_parser.add_argument("mbox", help="Path to the mbox file to analyze.")
    analyze_parser.add_argument("--playbooks", default="config/response_playbooks.json", help="Path to response playbook JSON.")
    analyze_parser.add_argument("--sample-limit", type=int, default=3)
    analyze_parser.add_argument("--report", help="Write a Markdown report to this path.")
    analyze_parser.add_argument("--json", help="Write structured JSON output to this path.")
    analyze_parser.set_defaults(func=run_analyze)

    draft_parser = subparsers.add_parser("draft", help="Draft a response for one message.")
    draft_parser.add_argument("--email-file", help="Path to a raw .eml file.")
    draftParser = draft_parser
    draftParser.add_argument("--mbox", help="Path to an mbox file.")
    draftParser.add_argument("--subject-contains", help="Case-insensitive subject filter when using --mbox.")
    draftParser.add_argument("--match-index", type=int, default=0, help="Zero-based match index for subject filter.")
    draftParser.add_argument("--playbooks", default="config/response_playbooks.json", help="Path to response playbook JSON.")
    draftParser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5"))
    draftParser.add_argument("--output", help="Write JSON output to this path.")
    draftParser.add_argument("--dry-run", action="store_true", help="Print the assembled prompt instead of calling the API.")
    draftParser.set_defaults(func=run_draft)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
