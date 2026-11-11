// Demo page for the WhatsApp family alerts kit.
// In the team app you only need <WhatsAppAlertsProvider> + the components you want.
// The day's theme is set in src/whatsapp-alerts/theme.ts (ACTIVE_THEME).
import { useState } from 'react';
import {
  ACTIVE_THEME,
  PRESETS,
  WhatsAppAlertsPanel,
  WhatsAppAlertsProvider,
  useAlerts,
  type Lang,
} from './whatsapp-alerts';

// Replace with your real logged-in user id when merging.
const OWNER_ID = 'demo-user-1';

function DemoControls() {
  const { alerts, theme, lang } = useAlerts();
  return (
    <section className="wa-card">
      <h3>Demo controls (remove for production)</h3>
      <div className="wa-row">
        <button type="button" disabled={!alerts.activeTrip} onClick={() => alerts.hazardWarning(theme.hazardExample[lang])}>
          ⚠️ Simulate hazard: "{theme.hazardExample[lang]}"
        </button>
        <button type="button" disabled={alerts.contacts.length === 0} onClick={() => alerts.customAlert(theme.customExample[lang])}>
          📣 Send custom alert: "{theme.customExample[lang]}"
        </button>
        <button type="button" disabled={!alerts.status?.dev_routes} onClick={() => alerts.runOverdueCheckNow()}>
          ⏱ Run missed check-in check now
        </button>
      </div>
      <p className="wa-muted wa-small">
        Tip: start with the check-in time one minute from now and grace 0, then press "Run missed check-in check now".
      </p>
    </section>
  );
}

export default function App() {
  const [lang, setLang] = useState<Lang>('en');
  // The preset picker is only for trying themes in the demo; in the real app ACTIVE_THEME is used.
  const [themeId, setThemeId] = useState(ACTIVE_THEME.id);
  const theme = PRESETS[themeId] ?? ACTIVE_THEME;
  return (
    <main style={{ padding: 16 }}>
      <header style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'space-between', maxWidth: 640, margin: '0 auto 12px' }}>
        <h2 style={{ margin: 0 }}>{theme.appName}</h2>
        <span style={{ display: 'flex', gap: 8 }}>
          <select value={themeId} onChange={(e) => setThemeId(e.target.value)} aria-label="Theme preset">
            {Object.values(PRESETS).map((p) => (
              <option key={p.id} value={p.id}>
                {p.appName}
              </option>
            ))}
          </select>
          <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label="Language">
            <option value="en">English</option>
            <option value="fr">Français</option>
          </select>
        </span>
      </header>
      <WhatsAppAlertsProvider key={themeId} ownerId={OWNER_ID} lang={lang} theme={theme}>
        <WhatsAppAlertsPanel />
        <div className="wa-alerts" style={{ marginTop: 12 }}>
          <DemoControls />
        </div>
      </WhatsAppAlertsProvider>
    </main>
  );
}
