import { useEffect, useState, type FormEvent } from 'react';
import { useAlerts } from '../context';
import { fmtTime } from '../messages';

function toLocalInput(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function duration(ms: number) {
  const m = Math.max(0, Math.round(Math.abs(ms) / 60000));
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;
}

function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

/**
 * Trip form + active trip card. Props let a host idea prefill fields
 * (e.g. the voice assistant fills `plan` from what the user said).
 * Words come from the active theme (theme.ts).
 */
export function TripCheckIn({
  defaultName = '',
  defaultPhone = '',
  defaultPlan = '',
  defaultHours,
  extra,
}: {
  defaultName?: string;
  defaultPhone?: string;
  defaultPlan?: string;
  defaultHours?: number;
  extra?: Record<string, unknown>;
}) {
  const { alerts, t, theme } = useAlerts();
  const hours = defaultHours ?? theme.defaultHours;
  const now = useNow();
  const [name, setName] = useState(defaultName);
  const [phone, setPhone] = useState(defaultPhone);
  const [plan, setPlan] = useState(defaultPlan);
  const [due, setDue] = useState(() => toLocalInput(new Date(Date.now() + hours * 3600_000)));
  const [grace, setGrace] = useState<number>(theme.defaultGraceMinutes);

  useEffect(() => setPlan(defaultPlan), [defaultPlan]);

  const trip = alerts.activeTrip;

  if (trip) {
    const dueMs = new Date(trip.due_at).getTime() - now;
    const alerted = trip.status === 'overdue_alerted' || trip.status === 'sos';
    return (
      <section className={`wa-card ${dueMs < 0 ? 'wa-late' : ''}`}>
        <h3>{t.active}</h3>
        <p>
          <strong>{trip.person_name}</strong> · {trip.plan}
        </p>
        <p className="wa-big">
          {dueMs >= 0 ? `${t.dueIn} ${duration(dueMs)}` : `${t.overdueBy} ${duration(dueMs)}`}
        </p>
        <p className="wa-muted">
          {alerted ? `⚠ ${t.familyAlerted}` : `${t.familyAlertedAt} ${fmtTime(trip.alert_at)}`}
        </p>
        <div className="wa-row">
          <button type="button" className="wa-primary" disabled={alerts.busy} onClick={() => alerts.checkIn()}>
            ✓ {t.imBack}
          </button>
          <button type="button" className="wa-link-btn" disabled={alerts.busy} onClick={() => alerts.cancelTrip()}>
            {t.cancel}
          </button>
        </div>
      </section>
    );
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !plan.trim() || !due) return;
    alerts.startTrip({
      personName: name.trim(),
      personPhone: phone.trim() || undefined,
      plan: plan.trim(),
      dueAt: new Date(due), // datetime-local is the device's local time
      graceMinutes: grace,
      extra,
    });
  };

  return (
    <section className="wa-card">
      <h3>{t.startTitle}</h3>
      <form className="wa-form" onSubmit={submit}>
        <label>
          {t.yourName}
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          {t.yourPhone}
          <input value={phone} inputMode="tel" placeholder="+230 5xxx xxxx" onChange={(e) => setPhone(e.target.value)} />
        </label>
        <label>
          {t.plan}
          <textarea value={plan} placeholder={t.planPh} rows={2} onChange={(e) => setPlan(e.target.value)} required />
        </label>
        <div className="wa-row">
          <label>
            {t.backBy}
            <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} required />
          </label>
          <label>
            {t.grace}
            <input type="number" min={0} max={600} value={grace} onChange={(e) => setGrace(Number(e.target.value))} />
          </label>
        </div>
        <button type="submit" className="wa-primary" disabled={alerts.busy || alerts.contacts.length === 0}>
          {alerts.busy ? t.sending : t.start}
        </button>
        {alerts.contacts.length === 0 && <p className="wa-muted">{t.noContacts}</p>}
      </form>
    </section>
  );
}
