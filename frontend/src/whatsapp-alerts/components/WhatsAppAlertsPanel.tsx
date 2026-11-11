import { useAlerts } from '../context';
import { AlertLog } from './AlertLog';
import { FallbackSheet } from './FallbackSheet';
import { FamilyContacts } from './FamilyContacts';
import { PrivacyPanel } from './PrivacyPanel';
import { SosButton } from './SosButton';
import { TripCheckIn } from './TripCheckIn';

/** Mode banner: tells the demo team which path messages are taking. */
export function AlertsStatusBanner() {
  const { alerts, t } = useAlerts();
  if (alerts.offline) return <div className="wa-banner wa-banner-warn">{t.offline}</div>;
  if (!alerts.status) return null;
  if (alerts.status.dry_run) return <div className="wa-banner">{t.dryRun}</div>;
  if (!alerts.status.use_templates) return <div className="wa-banner">{t.textMode}</div>;
  return null;
}

export function ErrorLine() {
  const { alerts } = useAlerts();
  return alerts.error ? <div className="wa-banner wa-banner-warn">{alerts.error}</div> : null;
}

/** Everything in one drop-in panel. Use the pieces separately if you need a custom layout. */
export function WhatsAppAlertsPanel(props: { defaultPlan?: string; defaultName?: string; defaultPhone?: string }) {
  return (
    <div className="wa-alerts">
      <AlertsStatusBanner />
      <ErrorLine />
      <TripCheckIn {...props} />
      <div className="wa-sos-wrap">
        <SosButton />
      </div>
      <FamilyContacts />
      <AlertLog />
      <PrivacyPanel />
      <FallbackSheet />
    </div>
  );
}
