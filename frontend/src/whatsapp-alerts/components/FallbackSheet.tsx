import { useAlerts } from '../context';

/** Pops up only when automatic sending failed: one wa.me + SMS button per family member. */
export function FallbackSheet() {
  const { alerts, t } = useAlerts();
  const items = alerts.fallback;
  if (!items || items.length === 0) return null;

  return (
    <div className="wa-overlay" role="dialog" aria-modal="true" aria-label={t.fallbackTitle}>
      <div className="wa-sheet">
        <h3>{t.fallbackTitle}</h3>
        <p className="wa-muted">{t.fallbackHelp}</p>
        <ul className="wa-list">
          {items.map((it) => (
            <li key={it.phone}>
              <span>
                <strong>{it.name}</strong>
                {it.reason && <span className="wa-muted wa-small"> · {it.reason}</span>}
              </span>
              <span className="wa-row">
                <a className="wa-btn-wa" href={it.wa} target="_blank" rel="noreferrer">
                  WhatsApp
                </a>
                <a className="wa-link-btn" href={it.sms}>
                  SMS
                </a>
              </span>
            </li>
          ))}
        </ul>
        <button type="button" onClick={alerts.clearFallback}>
          {t.close}
        </button>
      </div>
    </div>
  );
}
