# Governance shell: WhatsApp family alerts

**What this is.** This page maps the module's controls to ISO/IEC 27001:2022 (information security), ISO/IEC 27701 (privacy) and the Mauritius Data Protection Act 2017. It shows we designed for good practice from day one.

**What this is not.** It is not a certification. Certification needs an audited management system with policies, a risk assessment and internal audits, not just code. Say this plainly if judges ask.

## Control map

| Area | What the module does | Where in the code | ISO/IEC 27001:2022 Annex A | ISO/IEC 27701 / DPA 2017 |
|---|---|---|---|---|
| Consent | A contact can only be added after ticking "This person agreed…". The consent time, wording and version are saved with the contact. | `router.py` `post_contact`, `governance.py` `CONSENT_*`, `FamilyContacts.tsx` | 5.34 Privacy and protection of PII | Obtaining and recording consent · DPA: lawful processing based on consent |
| Data minimisation | Only name, phone, language, trip plan and due time are stored. GPS is sent to family on SOS but **not** copied into the audit log. Max 5 contacts. | `service.py`, `router.py` `post_sos` | 5.34 | Limit collection to what is needed |
| Retention | Closed trips and alert logs are deleted after `ALERTS_RETENTION_DAYS` (default 30), checked hourly. | `governance.py` `run_retention`, `service.py` `scheduler_loop` | 8.10 Information deletion | Retention and disposal · DPA: keep no longer than needed |
| Right of access / portability | "Download my data" exports everything stored about the user as JSON. | `GET /privacy/export`, `PrivacyPanel.tsx` | 5.34 | Provide a copy of PII · DPA: right of access |
| Right to erasure | "Delete all my data" removes contacts, trips and alerts. The audit log keeps only the fact of the erasure. | `DELETE /privacy/erase?confirm=true` | 8.10 | Erasure · DPA: right to erasure |
| Audit trail | Every action is logged: contact added or removed, trip, check-in, SOS, hazard, missed check-in, export, erase, purge, failed login. Logs are append-only, and each entry stores the SHA-256 hash of the previous one, so editing or deleting any past entry is detected. | `governance.py` `audit`, `verify_chain`; `GET /governance/audit`, `/governance/audit/verify` | 8.15 Logging · 5.33 Protection of records | Records of processing |
| Masking | Phone numbers appear as `2305****456` in the audit log and server logs. Message text is not logged. | `governance.py` `mask_phone`, `client.py` | 8.11 Data masking | De-identification |
| Monitoring | Failed app-key attempts are logged as `auth_failed` with the caller's IP. | `security.py` `require_app_key` | 8.16 Monitoring activities | — |
| Access control | An app key is needed on every API call, and data is scoped per `owner_id`. | `security.py` | 5.15 Access control · 8.5 Secure authentication | — |
| Secrets | The Meta token, Mongo password, app key and app secret live only in `.env`, which git ignores. A permanent token is held by a system user with the 2 permissions it needs. | `config.py`, `.gitignore` | 5.17 Authentication information · 8.2 Privileged access rights | — |
| Cryptography | Webhook calls are verified with HMAC-SHA256 (Meta app secret). The audit chain uses SHA-256, and HTTPS is used to Meta. | `security.py` `valid_meta_signature` | 8.24 Use of cryptography | — |
| Abuse and capacity | There are rate limits of 10 actions per minute per user and 60 in total. | `security.py` `check_rate` | 8.6 Capacity management | — |
| Cloud suppliers | Meta WhatsApp Cloud API (sending) and MongoDB Atlas (storage) are the only processors. | `client.py`, `store.py` | 5.23 Cloud services · 5.19 Supplier relationships | DPA: processors and transfers abroad |
| Secure development | Inputs are validated (phone 8 to 15 digits, text length limits), wording is fixed by templates, and 14 automated tests cover security and governance. | `router.py` models, `tests/` | 8.28 Secure coding · 8.29 Security testing | Privacy by design |
| Configuration | Every setting is in `.env.example`, and demo-only routes are switched off with `ALERTS_ENABLE_DEV_ROUTES=false`. | `.env.example` | 8.9 Configuration management | — |

ISO/IEC 42001 (AI management) doesn't apply to this module, because it makes no AI decisions. It applies to the team's voice assistant and agents.

## Incident plan (5 steps)

1. **Token or key leaked:** revoke the token in Meta Business > System users, generate a new one, and update `.env`. Change `ALERTS_API_KEY` in both `.env` files.
2. **Spam alerts sent:** set `WA_DRY_RUN=true` and restart. That stops all sending immediately.
3. **Find out what happened:** check `GET /governance/audit` and `/governance/audit/verify`.
4. **Personal data exposed:** under the DPA 2017, notify the Data Protection Office within **72 hours** and tell affected users.
5. **Write down** what happened, the fix, and how to prevent it next time.

## Known gaps (fine for a hackathon, honest for judges)

- There is no real user login. The app key is visible in the browser, so it keeps strangers out but isn't per-user. Next step: proper login, with `owner_id` taken from it.
- Rate limits and the audit lock live in memory, so run a single backend process.
- Data isn't encrypted at field level. MongoDB Atlas encrypts at rest by default.
- A real launch would need: registration with the Mauritius Data Protection Office as a controller, a privacy notice, a formal risk assessment and ISMS policies.

## Demo lines for judges

- "Every family contact consents first, and we store when and to what wording."
- "Our audit log is hash-chained. Change one past entry and `/audit/verify` shows exactly where." Show it live.
- "Users can download or delete all their data in one tap, and old trips delete themselves after 30 days."
