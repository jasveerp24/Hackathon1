import { useEffect, useState } from 'react';
import { alertsApi } from '../api';
import { useAlerts } from '../context';
import type { GovernancePolicy } from '../types';

/** Shows the retention/consent policy and gives the user access + erasure rights. */
export function PrivacyPanel() {
  const { alerts, t } = useAlerts();
  const [policy, setPolicy] = useState<GovernancePolicy | null>(null);

  useEffect(() => {
    alertsApi.policy().then(setPolicy).catch(() => setPolicy(null));
  }, []);

  const erase = () => {
    if (window.confirm(t.eraseConfirm)) alerts.eraseMyData();
  };

  return (
    <section className="wa-card">
      <h3>{t.privacy}</h3>
      {policy && <p className="wa-muted wa-small">{t.privacyInfo.replace('{days}', String(policy.retention_days))}</p>}
      <div className="wa-row">
        <button type="button" disabled={alerts.busy} onClick={() => alerts.downloadMyData()}>
          {t.download}
        </button>
        <button type="button" className="wa-link-btn" disabled={alerts.busy} onClick={erase}>
          {t.erase}
        </button>
      </div>
    </section>
  );
}
