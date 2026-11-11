import { useState, type FormEvent } from 'react';
import { useAlerts } from '../context';
import type { Lang } from '../types';

export function FamilyContacts() {
  const { alerts, t } = useAlerts();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [lang, setLang] = useState<Lang>('en');
  const [consent, setConsent] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || phone.replace(/\D/g, '').length < 7 || !consent) return;
    const r = await alerts.addContact(name.trim(), phone.trim(), lang, consent);
    if (r) {
      setName('');
      setPhone('');
      setConsent(false);
    }
  };

  return (
    <section className="wa-card">
      <h3>{t.family}</h3>
      {alerts.contacts.length === 0 && <p className="wa-muted">{t.noContacts}</p>}
      <ul className="wa-list">
        {alerts.contacts.map((c) => (
          <li key={c.id}>
            <span>
              <strong>{c.name}</strong> <span className="wa-muted">+{c.phone} · {c.lang.toUpperCase()}</span>
            </span>
            <button type="button" className="wa-link-btn" onClick={() => alerts.removeContact(c.id)}>
              {t.remove}
            </button>
          </li>
        ))}
      </ul>
      {alerts.contacts.length < 5 && (
        <form className="wa-row" onSubmit={submit}>
          <input aria-label={t.name} placeholder={t.name} value={name} onChange={(e) => setName(e.target.value)} />
          <input
            aria-label={t.phone}
            placeholder="+230 5xxx xxxx"
            inputMode="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <select aria-label={t.language} value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
            <option value="en">EN</option>
            <option value="fr">FR</option>
          </select>
          <button type="submit" disabled={alerts.busy || !consent}>
            {t.add}
          </button>
          <label className="wa-consent">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>{t.consentLabel}</span>
          </label>
        </form>
      )}
    </section>
  );
}
