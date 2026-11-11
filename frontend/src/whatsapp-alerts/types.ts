export type Lang = 'en' | 'fr';

export type AlertEvent =
  | 'trip_started'
  | 'missed_checkin'
  | 'sos'
  | 'hazard_warning'
  | 'checked_in'
  | 'custom';

export interface Contact {
  id: string;
  owner_id: string;
  name: string;
  phone: string; // digits, international, e.g. 23057123456
  lang: Lang;
}

export type TripStatus = 'active' | 'overdue_alerted' | 'sos' | 'checked_in' | 'cancelled';

export interface Trip {
  id: string;
  owner_id: string;
  person_name: string;
  person_phone: string;
  plan: string;
  due_at: string; // ISO
  alert_at: string; // ISO, due_at + grace
  grace_minutes: number;
  status: TripStatus;
  created_at: string;
  checked_in_at?: string;
  extra?: Record<string, unknown>;
}

export interface SendResult {
  ok: boolean;
  to: string;
  event: AlertEvent;
  lang: Lang;
  text: string;
  mode: 'dry_run' | 'template' | 'text' | 'invalid' | 'offline';
  contact_name?: string;
  message_id?: string | null;
  error?: string;
  error_code?: number;
  hint?: string;
  delivery?: 'sent' | 'delivered' | 'read' | 'failed';
}

export interface AlertLogEntry {
  id: string;
  owner_id: string;
  trip_id: string | null;
  event: AlertEvent;
  results: SendResult[];
  sent: number;
  failed: number;
  created_at: string;
}

export interface GovernancePolicy {
  retention_days: number;
  consent_version: string;
  consent_text: string;
  audit: string;
  max_contacts: number;
  data_location: string;
}

export interface AlertsStatus {
  configured: boolean;
  dry_run: boolean;
  use_templates: boolean;
  store: 'memory' | 'mongodb';
  grace_minutes: number;
  emergency_number: string;
  dev_routes: boolean;
}
