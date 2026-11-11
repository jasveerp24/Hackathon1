# Family alerts kit (WhatsApp, any theme)

A ready-made kit that sends WhatsApp alerts to a person's family automatically. It is **not tied to any one idea**: a person says what they are doing and when they'll be back (a walk home, a hike, a day out at sea, an elderly parent's day, a cyclone shelter...). If they don't check in on time, their family gets a WhatsApp message. The theme is picked on the hackathon day by changing **one line** (see "Change the theme on the day" below).

| Event | When | Who triggers it |
|---|---|---|
| `trip_started` | Person starts a trip/activity | `TripCheckIn` form |
| `missed_checkin` | Due time + grace minutes passed, no check-in | **Backend timer (automatic, works even if the phone is off)** |
| `sos` | SOS button (sends GPS link) | `SosButton` |
| `hazard_warning` | Any danger your data finds (high waves, flood, heat, crime hotspot...) | Your data/AI agent calls `hazardWarning()` |
| `checked_in` | "I'm safe" button, **or the person replies `SAFE` on WhatsApp** | `TripCheckIn` / webhook |
| `custom` | Any short message your theme needs (medication reminder, scam alert...) | `customAlert()` / `POST /send` |

### Change the theme on the day (2 lines)
1. `frontend/src/whatsapp-alerts/theme.ts`: set `export const ACTIVE_THEME = PRESETS.general;` to one of `general`, `elderly`, `walkHome`, `cyclone`, `fishing`, or copy a preset and edit its words (app name, labels, placeholder, default hours, example alerts, EN + FR).
2. `backend/.env`: set `ALERTS_APP_NAME=` to the same app name (it appears in the custom WhatsApp message).

Nothing else changes: the WhatsApp templates are generic, so no new Meta approval is needed. The demo page has a theme picker so you can try all presets.

Messages go out in **English or French**, chosen per family member. If WhatsApp can't send, for example because the server is down or the key has expired, the app shows **wa.me and SMS buttons** with the message already filled in. That fallback is free, but someone has to tap Send.

```
backend/                     Python 3.11+ / FastAPI
  whatsapp_alerts/           <- the module (copy this folder)
    config.py  templates.py  client.py  store.py  service.py  router.py
  main.py                    standalone demo server
  tests/test_alerts.py       pytest, no keys/network needed
frontend/                    React + TypeScript + Vite
  src/whatsapp-alerts/       <- the module (copy this folder)
  src/App.tsx                demo page
```

---

## 1. Run it locally (works with NO keys, in demo mode)

**Backend** (Windows PowerShell):
```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # then edit .env (leave WA_ACCESS_TOKEN empty for demo mode; set ALERTS_API_KEY)
uvicorn main:app --reload --port 8000
```
Open http://localhost:8000/docs to try every endpoint. Run the tests with `pytest -q`.

**Frontend** (second terminal):
```powershell
cd frontend
npm install
copy .env.example .env        # set VITE_ALERTS_API_KEY to the same value as ALERTS_API_KEY
npm run dev
```
Open http://localhost:5173. To test on a phone on the same Wi-Fi, use `http://<laptop-ip>:5173`. Note that phones only share GPS over https or localhost, so the SOS location will be empty on a LAN IP. Use the deployed https URL for the demo.

With no token, the backend runs in **dry run** mode: messages are printed in the terminal and shown as "demo" in the log. The UI shows a banner saying so.

---

## 2. Meta WhatsApp Cloud API setup (do this before 13 Nov)

1. Go to https://developers.facebook.com, then **My Apps**, then **Create app**. Pick the WhatsApp use case ("Connect with customers through WhatsApp") and create or select a Business portfolio when asked.
2. Go to **WhatsApp > API Setup**. Meta gives you a free **test phone number**. Copy:
   - **Phone number ID** into `WA_PHONE_NUMBER_ID`
   - **Temporary access token** into `WA_ACCESS_TOKEN` (⚠ it **expires after about 24 h**, see step 4)
3. In the **To** field, choose **Manage phone number list** and add each family/demo phone, **up to 5 numbers**. Each phone receives a WhatsApp code to confirm. Press **Send message** once to receive Meta's `hello_world` test.
4. **Permanent token** (so the demo doesn't die overnight): go to https://business.facebook.com, then **Settings > Users > System users**, and add an Admin system user. Use **Assign assets** to give it the app with full control, then **Generate token** for the app with permissions `whatsapp_business_messaging` and `whatsapp_business_management` and expiry **Never**. Paste it into `WA_ACCESS_TOKEN`.
5. **Templates** (needed to message someone who hasn't written to the number in the last 24 h). In **WhatsApp Manager**, open **Message templates** and choose **Create template**. Use category **Utility** and create each of these with **both English (`en`) and French (`fr`)**. Copy the body text exactly from `backend/whatsapp_alerts/templates.py` and give sample values for each `{{n}}`.

   | Template name | Variables |
   |---|---|
   | `safety_trip_started` | 1 person, 2 plan, 3 due time |
   | `safety_missed_checkin` | 1 person, 2 plan, 3 due time, 4 emergency number |
   | `safety_sos` | 1 person, 2 location link, 3 emergency number |
   | `safety_hazard_warning` | 1 person, 2 plan, 3 warning |
   | `safety_checked_in` | 1 person, 2 time |
   | `safety_custom_alert` | 1 person, 2 message, 3 app name |

   Approval usually takes minutes but can take up to 24 h. When all are approved, set `WA_USE_TEMPLATES=true`. List the languages you got approved in `WA_TEMPLATE_LANGS` (default `en`; use `en,fr` if you also submit French). In template mode, a contact in a language that isn't listed gets the English template, so nothing fails.
6. **Optional webhook** (blue ticks in the log, and checking in by replying `SAFE`). Expose the backend with `cloudflared tunnel --url http://localhost:8000` (free) or ngrok. In **WhatsApp > Configuration > Webhook**, set the callback to `https://<your-tunnel>/api/alerts/webhook` and the verify token to your `WA_WEBHOOK_VERIFY_TOKEN`, then subscribe to the **messages** field. Also put the app secret in `WA_APP_SECRET` so fake webhook calls are rejected.

### ⚠ Using your own number
**Don't register your personal WhatsApp number as the sender.** A number moved to the Cloud API stops working in the normal WhatsApp app, and a real sender number also needs business verification. For the hackathon, **send from Meta's free test number** and add your number as one of the 5 recipients.

### Cost
- Meta charges per **template** message outside the 24 h window. A **utility** template costs a fraction of a US cent to a few cents depending on the country. Plain-text replies inside an open 24 h window are free.
- Meta can re-categorise a template as **Marketing**, which costs more. Keep the wording factual and safety-only (it already is).
- Check **WhatsApp Manager > Insights** and billing before the event. Don't add a payment method unless Meta asks for one, and tell the team first.

---

## 3. Demo-day reliability plan

1. **The night before:** from every demo phone, send "hi" to the test number. That opens the 24 h window, so plain-text mode (`WA_USE_TEMPLATES=false`) works even if templates are still pending.
2. Check the token with `GET /api/alerts/status`: `configured: true, dry_run: false`.
3. To show "missed check-in" live, start a trip with **Back by = now + 1 min**, grace **0**, then press **Run missed check-in check now** (or just wait: the timer checks every 30 s).
4. If the venue Wi-Fi or the API fails, the **wa.me / SMS buttons** appear automatically. Rehearse that path once so it looks intentional ("works even offline").
5. Use MongoDB Atlas for storage. If Mongo is unreachable, the backend logs an error and **falls back to memory**, so the demo still runs (data then resets on restart).
6. **Hackathon rules:** check whether pre-built code is allowed, and present this as reusable tooling/templates prepared before the event.

---

## 4. Merging into another idea

### Backend (FastAPI)
Copy `backend/whatsapp_alerts/` into your backend, add the requirements, and add **two lines**:
```python
from whatsapp_alerts import alerts_router, alerts_lifespan
app = FastAPI(lifespan=alerts_lifespan)   # if you already have a lifespan, call `async with alerts_lifespan(app):` inside it
app.include_router(alerts_router)         # routes under /api/alerts
```
Call it from Python, for example from whatever data/AI agent your theme uses:
```python
from whatsapp_alerts.service import hazard_warning, notify_contacts
from whatsapp_alerts import AlertEvent
await hazard_warning(owner_id, "Ravi", "Hike at Le Pouce", "Heavy rain warning this afternoon")
await notify_contacts(owner_id, AlertEvent.CUSTOM, {"person": "Mamie Lise", "message": "Missed the morning medication"})
await notify_contacts(owner_id, AlertEvent.SOS, {"person": "Ravi", "location": "https://maps.google.com/?q=-20.45,57.31"})
```

### Frontend (React)
Copy `frontend/src/whatsapp-alerts/` into your `src/`, and add the `/api` proxy from `vite.config.ts` (or set `VITE_ALERTS_API_URL`).
```tsx
import { WhatsAppAlertsProvider, WhatsAppAlertsPanel } from './whatsapp-alerts';

<WhatsAppAlertsProvider ownerId={user.id} lang="fr">   {/* theme={PRESETS.elderly} optional; default is ACTIVE_THEME */}
  <WhatsAppAlertsPanel defaultPlan={planFromVoice} />
</WhatsAppAlertsProvider>
```
You can also use the pieces separately (`FamilyContacts`, `TripCheckIn`, `SosButton`, `AlertLog`, `FallbackSheet`, `AlertsStatusBanner`, `PrivacyPanel`) or the hook:
```tsx
const { alerts } = useAlerts();          // inside the provider
alerts.hazardWarning('MMS: heavy rain warning');
alerts.customAlert('Missed the morning medication');
alerts.send('sos', { person: 'Ravi', location: 'Blue Bay' });
```
Plain JavaScript projects can import these `.tsx` files too, because Vite compiles TypeScript out of the box.

### REST API (all under `/api/alerts`)
`GET /status` · `GET/POST /contacts` · `DELETE /contacts/{id}?owner_id=` · `POST /trips` · `GET /trips?owner_id=` · `POST /trips/{id}/checkin` · `POST /trips/{id}/cancel` · `POST /sos` · `POST /hazard` · `POST /send` · `GET /log?owner_id=` · `POST /dev/run-overdue-check` · `GET/POST /webhook` · `GET /governance/policy` · `GET /governance/audit` · `GET /governance/audit/verify` · `POST /governance/run-retention` · `GET /privacy/export?owner_id=` · `DELETE /privacy/erase?owner_id=&confirm=true`

Adding a contact now needs `"consent": true` in the body.

## 5. Security

| Protection | How | Setting |
|---|---|---|
| Secret keys never reach the browser | Meta token + Mongo password only in `backend/.env` (git-ignored) | `WA_ACCESS_TOKEN`, `MONGODB_URI` |
| App key on every API call | Frontend sends header `X-Alerts-Key`; wrong/missing key gives 401 | `ALERTS_API_KEY` (backend) = `VITE_ALERTS_API_KEY` (frontend) |
| Rate limits | Max 10 actions/min per user, 60/min in total; extra calls get 429 | `ALERTS_RATE_LIMIT_*` |
| Demo button locked | `/dev/run-overdue-check` returns 404 unless switched on | `ALERTS_ENABLE_DEV_ROUTES=false` after the demo |
| Fake "SAFE" replies rejected | Webhook calls must carry Meta's signature; without `WA_APP_SECRET`, SAFE replies are ignored | `WA_APP_SECRET` |
| Input checks | Phone 8 to 15 digits, max 5 contacts, length limits on all text, fixed message wording | built in |
| CORS | Only your frontend's address may call the API from a browser | `FRONTEND_ORIGIN` |

Generate a key with `python -c "import secrets;print(secrets.token_urlsafe(24))"` and put it in **both** `.env` files.

**Be honest about the app key if judges ask.** It sits in the web app's JavaScript, so anyone who opens the app can read it. It stops strangers and bots who find the backend URL, but it is not a user login. For production you would add proper login and take `owner_id` from it.

**Personal data:** phone numbers and GPS links are personal data under Mauritius' Data Protection Act 2017. Ask for consent when adding a family contact, store only what's needed, and let users delete contacts (already supported).

## 6. Governance shell (ISO 27001 / 27701 / DPA 2017)

See **[GOVERNANCE.md](GOVERNANCE.md)** for the full control map, incident plan and demo lines. In short:

- **Consent:** each family contact must be ticked as "agreed" and the consent is stored with it.
- **Audit log:** every action is logged, append-only and hash-chained, with phone numbers masked. `GET /api/alerts/governance/audit` shows it and `GET /api/alerts/governance/audit/verify` checks nobody edited it.
- **Retention:** closed trips and alert logs are deleted after `ALERTS_RETENTION_DAYS` (default 30).
- **User rights:** "Download my data" (`GET /privacy/export`) and "Delete all my data" (`DELETE /privacy/erase?confirm=true`) are in the **Your data** card.
- **Policy:** `GET /api/alerts/governance/policy` returns what is kept, for how long, and the consent wording.

### Known limits (fine for a hackathon, say so if judges ask)
- There is no user login. `owner_id` is trusted from the client (behind the app key), so plug in real auth if the team adds one.
- Rate limits are kept in memory, so they reset when the backend restarts.
- There are at most 5 family contacts (the same as the test-number limit).
- If you change wording, keep `templates.py` and `frontend/src/whatsapp-alerts/messages.ts` in sync, and re-submit the Meta templates.
- The timer runs inside the FastAPI process, so run **one** backend instance (no multiple workers).
