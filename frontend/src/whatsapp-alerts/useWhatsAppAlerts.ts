import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, alertsApi } from './api';
import { fallbackForContacts, fallbackFromResults, type FallbackItem } from './fallback';
import { fmtTime, renderMessage } from './messages';
import type { AlertEvent, AlertLogEntry, AlertsStatus, Contact, Lang, Trip } from './types';

const OPEN: Trip['status'][] = ['active', 'overdue_alerted', 'sos'];
const cacheKey = (ownerId: string) => `wa-alerts-contacts:${ownerId}`;

function readCache(ownerId: string): Contact[] {
  try {
    return JSON.parse(localStorage.getItem(cacheKey(ownerId)) ?? '[]');
  } catch {
    return [];
  }
}
function writeCache(ownerId: string, contacts: Contact[]) {
  try {
    localStorage.setItem(cacheKey(ownerId), JSON.stringify(contacts));
  } catch {
    /* private mode etc. */
  }
}

function getPosition(timeoutMs = 6000): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (!('geolocation' in navigator)) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60000 },
    );
  });
}

export interface StartTripInput {
  personName: string;
  plan: string;
  dueAt: Date;
  personPhone?: string;
  graceMinutes?: number;
  notifyStart?: boolean;
  extra?: Record<string, unknown>;
}

export function useWhatsAppAlerts(ownerId: string, appName = 'Safe Check-in', pollMs = 15000) {
  const [status, setStatus] = useState<AlertsStatus | null>(null);
  const [contacts, setContacts] = useState<Contact[]>(() => readCache(ownerId));
  const [trips, setTrips] = useState<Trip[]>([]);
  const [log, setLog] = useState<AlertLogEntry[]>([]);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fallback, setFallback] = useState<FallbackItem[] | null>(null);
  const contactsRef = useRef(contacts);
  contactsRef.current = contacts;

  const activeTrip = useMemo(() => trips.find((t) => OPEN.includes(t.status)) ?? null, [trips]);

  const refresh = useCallback(async () => {
    try {
      const [s, c, t, l] = await Promise.all([
        alertsApi.status(),
        alertsApi.listContacts(ownerId),
        alertsApi.listTrips(ownerId),
        alertsApi.log(ownerId),
      ]);
      setStatus(s);
      setContacts(c);
      writeCache(ownerId, c);
      setTrips(t);
      setLog(l);
      setOffline(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setOffline(false);
        setError('App key missing or wrong: check VITE_ALERTS_API_KEY matches ALERTS_API_KEY.');
      } else {
        setOffline(true);
      }
    }
  }, [ownerId]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  /** Show wa.me buttons for anything the API could not deliver. */
  const handleEntry = useCallback((entry: AlertLogEntry | null | undefined) => {
    if (entry && entry.failed > 0) setFallback(fallbackFromResults(entry.results));
    return entry ?? null;
  }, []);

  /** Backend unreachable: build the same messages locally and offer wa.me links. */
  const offlineFallback = useCallback((event: AlertEvent, values: Record<string, string>) => {
    setOffline(true);
    const v = { emergency_number: status?.emergency_number ?? '999', ...values };
    setFallback(fallbackForContacts(contactsRef.current, (c) => renderMessage(event, c.lang, v)));
  }, [status]);

  const run = useCallback(
    async <T,>(fn: () => Promise<T>, onNetworkFail?: () => void): Promise<T | null> => {
      setBusy(true);
      setError(null);
      try {
        const r = await fn();
        return r;
      } catch (e) {
        // Network error, timeout, or server error (5xx, incl. dev proxy "backend down"):
        // the family still needs the message, so offer the wa.me fallback.
        const status = e instanceof ApiError ? e.status : 0;
        if ((status === 0 || status >= 500) && onNetworkFail) onNetworkFail();
        else setError(e instanceof Error ? e.message : String(e));
        return null;
      } finally {
        setBusy(false);
        refresh();
      }
    },
    [refresh],
  );

  // ---------- actions ----------
  const addContact = (name: string, phone: string, lang: Lang, consent: boolean) =>
    run(() => alertsApi.addContact(ownerId, name, phone, lang, consent));

  const removeContact = (id: string) => run(() => alertsApi.removeContact(ownerId, id));

  const startTrip = (i: StartTripInput) =>
    run(
      async () => {
        const r = await alertsApi.startTrip({
          owner_id: ownerId,
          person_name: i.personName,
          plan: i.plan,
          due_at: i.dueAt.toISOString(),
          person_phone: i.personPhone,
          grace_minutes: i.graceMinutes,
          notify_start: i.notifyStart ?? true,
          extra: i.extra,
        });
        handleEntry(r.alert);
        return r.trip;
      },
      () => offlineFallback('trip_started', { person: i.personName, plan: i.plan, due_time: fmtTime(i.dueAt) }),
    );

  const checkIn = () => {
    const t = activeTrip;
    if (!t) return Promise.resolve(null);
    return run(
      async () => handleEntry((await alertsApi.checkIn(t.id)).alert),
      () => offlineFallback('checked_in', { person: t.person_name, time: fmtTime(new Date()) }),
    );
  };

  const cancelTrip = () => {
    const t = activeTrip;
    return t ? run(() => alertsApi.cancelTrip(t.id)) : Promise.resolve(null);
  };

  const sos = async (personName: string, locationText = '') => {
    const pos = await getPosition();
    // No GPS? Use the trip plan as the best known location.
    const lastPlan = activeTrip?.plan ?? trips[0]?.plan ?? '';
    const where = pos
      ? `https://maps.google.com/?q=${pos.lat.toFixed(5)},${pos.lng.toFixed(5)}`
      : locationText || lastPlan;
    return run(
      async () =>
        handleEntry(
          await alertsApi.sos({
            owner_id: ownerId,
            person_name: personName,
            lat: pos?.lat,
            lng: pos?.lng,
            location_text: locationText || lastPlan,
            trip_id: activeTrip?.id,
          }),
        ),
      () => offlineFallback('sos', { person: personName, location: where || 'unknown' }),
    );
  };

  /** For the marine/weather agent: warn the family about a hazard on the current trip. */
  const hazardWarning = (warning: string, personName?: string, plan?: string) => {
    const person = personName ?? activeTrip?.person_name ?? '';
    const p = plan ?? activeTrip?.plan ?? '';
    return run(
      async () =>
        handleEntry(
          await alertsApi.hazard({ owner_id: ownerId, person_name: person, plan: p, warning, trip_id: activeTrip?.id }),
        ),
      () => offlineFallback('hazard_warning', { person, plan: p, warning }),
    );
  };

  /** Any theme: send your own short alert text (uses the "custom" template). */
  const customAlert = (message: string, personName?: string) =>
    send('custom', {
      person: personName ?? activeTrip?.person_name ?? trips[0]?.person_name ?? '',
      message,
      app_name: appName,
    });

  /** Generic send for other ideas (see messages.ts for the value keys per event). */
  const send = (event: AlertEvent, values: Record<string, string>) =>
    run(
      async () => handleEntry(await alertsApi.send(ownerId, event, values, activeTrip?.id)),
      () => offlineFallback(event, values),
    );

  /** Privacy: download everything stored about this user as a JSON file. */
  const downloadMyData = () =>
    run(async () => {
      const data = await alertsApi.exportData(ownerId);
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `my-safety-data-${ownerId}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return true;
    });

  /** Privacy: erase all contacts, trips and alerts for this user. */
  const eraseMyData = () =>
    run(async () => {
      const r = await alertsApi.eraseData(ownerId);
      writeCache(ownerId, []);
      setContacts([]);
      return r;
    });

  /** Demo: fire the missed check-in check now instead of waiting for the scheduler. */
  const runOverdueCheckNow = () => run(() => alertsApi.runOverdueCheckNow());

  return {
    ownerId,
    status,
    contacts,
    trips,
    activeTrip,
    log,
    offline,
    busy,
    error,
    fallback,
    clearFallback: () => setFallback(null),
    refresh,
    addContact,
    removeContact,
    startTrip,
    checkIn,
    cancelTrip,
    sos,
    hazardWarning,
    send,
    runOverdueCheckNow,
    customAlert,
    downloadMyData,
    eraseMyData,
  };
}

export type WhatsAppAlerts = ReturnType<typeof useWhatsAppAlerts>;
