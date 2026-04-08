# Email Archive Analysis

- Source mbox: `/private/tmp/email-analysis-sample/Zaber_MRC_142360/Inbox/mbox`
- Messages analyzed: `2934`
- Date range: `2009-04-16` to `2025-08-16`
- Messages with external parties: `1342`

## What This Mailbox Is

- This inbox looks like buyer / merchandising / export-operations coordination rather than consumer customer support.
- Top workflow categories are development_program, other, shipment_logistics.
- Mixed internal-external traffic suggests the best automation target is human-reviewed draft generation, not full auto-send.
- External counterparties are concentrated in a small set of domains, led by gap.com, bureauveritas.com, standardargroup.com, panther-textiles.com.
- Internal-only traffic is still significant, so approval and status workflows should be triaged separately from buyer-facing replies.
- Keep mandatory review on: other, internal_approval.

## Dominant Categories

| Category | Count | Automation Fit |
| --- | ---: | --- |
| development_program | 723 | Draft with human review |
| other | 681 | Human review required |
| shipment_logistics | 612 | Draft with human review |
| inspection_quality | 277 | Draft with human review |
| documents_commercial | 239 | Draft with human review |
| production_status | 142 | Draft with human review |
| costing_pricing | 118 | Draft with human review |
| collaboration_misc | 104 | Triaged acknowledgement only |
| internal_approval | 38 | Human review required |

## Top External Domains

| Domain | Count |
| --- | ---: |
| gap.com | 1421 |
| bureauveritas.com | 574 |
| standardargroup.com | 496 |
| panther-textiles.com | 443 |
| bbmglobal.com | 383 |
| sgtgroup.net | 254 |
| elitestyle.com.hk | 217 |
| tatfung-tex.com | 211 |
| alluresourcing.com | 210 |
| arvind.in | 158 |

## Recommended Agent Scope

- Start with draft generation for `shipment_logistics`, `costing_pricing`, `inspection_quality`, and `documents_commercial`.
- Keep `internal_approval` and any message with numeric commitments or attachments in human review.
- Use category-specific prompts so the agent asks for missing data instead of inventing shipment dates, prices, or approvals.

## Representative Samples

### other

- `2025-06-07T05:50:15+00:00` | `external_to_internal` | `vianna@cyberneticcreations.com` | ``
- `2025-06-22T09:49:00+06:00` | `external_to_internal` | `zaber.a1991@gmail.com` | ``

### development_program

- `2025-07-07T08:58:15+00:00` | `external_to_internal` | `notification.us@bureauveritas.com` | `- Buyer: (GAP INC), Submitter: (THE CIVIL ENGINEERS WOVEN LIMITED), BV Lab: 68251850420, Style/ Reference/ Item/ Article#  Style Name: D78188`
- `2025-08-10T09:57:22+00:00` | `internal_to_external` | `rouf.a@standardmhgroup.com` | `2nd time poly booking for style # D62985 Fall-25`

### collaboration_misc

- `2025-07-23T06:13:55+00:00` | `external_to_internal` | `mentions@notification.miro.com` | `[EXTERNAL] A new comment in CIVIL ENG - GO TG`
- `2025-06-24T12:19:20+00:00` | `internal_to_external` | `masud.r3@standardmhgroup.com` | `[External]A new comment in CIVIL ENG - GO TG`

### documents_commercial

- `2025-07-23T06:07:17+00:00` | `external_to_internal` | `salla.praveenkumar@ril.com` | `[EXTERNAL] RE: [External]RE: THE CIVIL ENGINEERS WOVEN LIMITED- HO'25 GAP ORDER VALIDATION - LOT-1`
- `2025-07-29T06:05:48+00:00` | `internal_to_external` | `masud.r3@standardmhgroup.com` | `[External]D68660	791573	PO UNI PLEATED WOV SKORT-- BOM803932`

### costing_pricing

- `2025-07-01T21:55:54+00:00` | `internal_to_external` | `saroar_a@standardmhgroup.com` | `[External]Cost ( profit )  Update in TS`
- `2025-07-01T13:30:54+00:00` | `internal_to_external` | `masud.r3@standardmhgroup.com` | `[External]Cost ( profit )  Update in TS`

### shipment_logistics

- `2025-08-12T07:12:51+00:00` | `internal_to_external` | `masud.r3@standardmhgroup.com` | `Arvind ------Fabric booking------- GO toddler Girls  woven D78422/1172382 /1172384 &D59696/873434 -WVN PO SHORT SP26 CHM---RD # 168388---------Sp-26`
- `2025-07-31T07:15:16+00:00` | `internal_to_external` | `masud.r3@standardmhgroup.com` | `Arvind Fabric booking -------- Gap kids girls-D68660-791573 PO UNI PLEATED WOV SKORT-- BOM803932 ------------RD1031737- Sp-26`

### inspection_quality

- `2025-07-30T03:41:26+00:00` | `external_to_internal` | `purbasa_shee@gap.com` | `Automatic reply: [External]PASS, 844985, HOL25, GAP/GO, BABY, TRIM, WOVEN, OTHERS, TRM-0001984724_68251720032R1`
- `2025-06-06T10:23:17+00:00` | `external_to_internal` | `sultan@elitestyle.com.hk` | `FW: [GAP] TCEL-2025-012B- inspection  - USD12878.00 -(GAP2502)`

### production_status

- `2025-07-11T04:06:36+00:00` | `external_only` | `gap_inc_plm@gap.com` | `Centric PLM - Issues Status Update 7/10/2025`
- `2025-06-02T02:56:13+00:00` | `internal_to_external` | `shafiqul.i8@standardmhgroup.com` | `Daily Production Report (DPR) J-Crew Status TCE-Woven Limited`

### internal_approval

- `2025-07-30T06:02:08+00:00` | `external_to_internal` | `mosabbirul_monsur@gap.com` | `REG: Action Required – Incorrect Sample Due Dates in SMS for GAP SP’26 - URGENT  - ACTION REQUIRED`
- `2025-08-12T05:09:58+00:00` | `external_to_internal` | `mosabbirul_monsur@gap.com` | `REG: Updates to Ship To - HO25 Franchise Marketing Ad Samples - Vendor Communication  - Action Required`

## Playbook Notes

- `costing_pricing`: Buyer or merchandising requests about cost sheets, pricing, target costs, or non-e-bid commercial discussions. Review mode: Draft with human review.
- `shipment_logistics`: Shipment updates, AWB details, pickup confirmations, delivery timing, and freight coordination. Review mode: Draft with human review.
- `inspection_quality`: Final inspection planning, pass/fail status, quality findings, and compliance follow-up. Review mode: Draft with human review.
- `internal_approval`: ERP, PO, and internal approval requests that require internal ownership or authorization. Review mode: Human review required.
- `production_status`: Daily production, shipment pending, wash balance, and execution-status reporting. Review mode: Draft with human review.
- `development_program`: Style, season, BOM, sample, and program-development coordination. Review mode: Draft with human review.
- `documents_commercial`: Invoices, POs, LC topics, reports, and commercial document exchange. Review mode: Draft with human review.
- `collaboration_misc`: Comments, notifications, and collaboration artifacts that usually need routing more than drafting. Review mode: Triaged acknowledgement only.
