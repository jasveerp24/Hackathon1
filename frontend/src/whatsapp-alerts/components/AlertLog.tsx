import { useAlerts } from '../context';
import { fmtTime } from '../messages';

const ICON: Record<string, string> = {
  trip_started: '▶️',
  missed_checkin: '⚠️',
  sos: '🆘',
  hazard_warning: '🌊',
  checked_in: '✅',
  custom: '📣',
};

const TICK: Record<string, string> = { sent: '✓', delivered: '✓✓', read: '✓✓ read', failed: '✗' };

export function AlertLog({ max = 10 }: { max?: number }) {
  const { alerts, t } = useAlerts();
  return (
    <section className="wa-card">
      <h3>{t.log}</h3>
      {alerts.log.length === 0 && <p className="wa-muted">{t.noLog}</p>}
      <ul className="wa-list">
        {alerts.log.slice(0, max).map((e) => (
          <li key={e.id} className="wa-log">
            <div>
              {ICON[e.event] ?? '•'} <strong>{e.event.split('_').join(' ')}</strong>{' '}
              <span className="wa-muted">{fmtTime(e.created_at)}</span>
            </div>
            {e.results.map((r, i) => (
              <div key={i} className={`wa-result ${r.ok ? 'ok' : 'fail'}`} title={r.text}>
                {r.contact_name} · {r.ok ? (r.mode === 'dry_run' ? 'demo' : TICK[r.delivery ?? 'sent']) : `✗ ${r.hint || r.error}`}
              </div>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
