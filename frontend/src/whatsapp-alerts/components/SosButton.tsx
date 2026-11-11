import { useAlerts } from '../context';

export function SosButton({ personName, confirm = true }: { personName?: string; confirm?: boolean }) {
  const { alerts, t } = useAlerts();
  // Fall back to the most recent trip's name if no trip is running.
  const name = personName ?? alerts.activeTrip?.person_name ?? alerts.trips[0]?.person_name ?? '';

  const onClick = () => {
    if (confirm && !window.confirm(t.sosConfirm)) return;
    alerts.sos(name || 'Unknown');
  };

  return (
    <button type="button" className="wa-sos" disabled={alerts.busy || alerts.contacts.length === 0} onClick={onClick}>
      {alerts.busy ? t.sending : t.sos}
    </button>
  );
}
