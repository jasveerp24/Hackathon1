import type { AlertEvent, AlertLogEntry, AlertsStatus, Contact, GovernancePolicy, Lang, Trip } from './types';

// Empty = same origin (Vite dev proxy forwards /api to FastAPI). Set VITE_ALERTS_API_URL
// if the backend runs elsewhere, e.g. https://my-backend.onrender.com
const BASE = (import.meta.env.VITE_ALERTS_API_URL ?? '').replace(/\/$/, '');
// Shared app key (same as ALERTS_API_KEY on the backend). It is visible in the browser,
// so it only keeps out strangers who find the URL; it is not a user login.
const APP_KEY: string = import.meta.env.VITE_ALERTS_API_KEY ?? '';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init: RequestInit = {}, timeoutMs = 12000): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}/api/alerts${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(APP_KEY ? { 'X-Alerts-Key': APP_KEY } : {}),
        ...(init.headers ?? {}),
      },
    });
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j);
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, msg);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

const post = <T>(path: string, body?: unknown) =>
  req<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

export const alertsApi = {
  status: () => req<AlertsStatus>('/status'),

  listContacts: (ownerId: string) => req<Contact[]>(`/contacts?owner_id=${encodeURIComponent(ownerId)}`),
  addContact: (ownerId: string, name: string, phone: string, lang: Lang, consent: boolean) =>
    post<Contact>('/contacts', { owner_id: ownerId, name, phone, lang, consent }),
  removeContact: (ownerId: string, id: string) =>
    req<{ ok: boolean }>(`/contacts/${id}?owner_id=${encodeURIComponent(ownerId)}`, { method: 'DELETE' }),

  startTrip: (body: {
    owner_id: string;
    person_name: string;
    plan: string;
    due_at: string;
    person_phone?: string;
    grace_minutes?: number;
    notify_start?: boolean;
    extra?: Record<string, unknown>;
  }) => post<{ trip: Trip; alert: AlertLogEntry | null }>('/trips', body),
  listTrips: (ownerId: string) => req<Trip[]>(`/trips?owner_id=${encodeURIComponent(ownerId)}`),
  checkIn: (tripId: string) => post<{ trip: Trip; alert: AlertLogEntry | null }>(`/trips/${tripId}/checkin`),
  cancelTrip: (tripId: string) => post<{ ok: boolean }>(`/trips/${tripId}/cancel`),

  sos: (body: {
    owner_id: string;
    person_name: string;
    lat?: number;
    lng?: number;
    location_text?: string;
    trip_id?: string;
  }) => post<AlertLogEntry>('/sos', body),
  hazard: (body: { owner_id: string; person_name: string; plan: string; warning: string; trip_id?: string }) =>
    post<AlertLogEntry>('/hazard', body),
  send: (ownerId: string, event: AlertEvent, values: Record<string, string>, tripId?: string) =>
    post<AlertLogEntry>('/send', { owner_id: ownerId, event, values, trip_id: tripId }),

  log: (ownerId: string) => req<AlertLogEntry[]>(`/log?owner_id=${encodeURIComponent(ownerId)}`),
  runOverdueCheckNow: () => post<{ alerted_trips: number }>('/dev/run-overdue-check'),

  // governance & privacy
  policy: () => req<GovernancePolicy>('/governance/policy'),
  exportData: (ownerId: string) => req<Record<string, unknown>>(`/privacy/export?owner_id=${encodeURIComponent(ownerId)}`),
  eraseData: (ownerId: string) =>
    req<{ erased: Record<string, number> }>(`/privacy/erase?owner_id=${encodeURIComponent(ownerId)}&confirm=true`, {
      method: 'DELETE',
    }),
};
