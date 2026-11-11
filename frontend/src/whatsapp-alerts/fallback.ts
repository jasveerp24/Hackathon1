// Free, no-API fallback: wa.me "click to chat" links with the message pre-filled.
// Not automatic (someone must tap Send), but works with zero setup and zero cost.
import type { Contact, SendResult } from './types';

export function waLink(phoneDigits: string, text: string): string {
  return `https://wa.me/${phoneDigits.replace(/\D/g, '')}?text=${encodeURIComponent(text)}`;
}

/** Plain SMS fallback (works with no data connection on the phone). */
export function smsLink(phoneDigits: string, text: string): string {
  return `sms:+${phoneDigits.replace(/\D/g, '')}?body=${encodeURIComponent(text)}`;
}

export interface FallbackItem {
  name: string;
  phone: string;
  text: string;
  wa: string;
  sms: string;
  reason?: string;
}

export function fallbackFromResults(results: SendResult[]): FallbackItem[] {
  return results
    .filter((r) => !r.ok && r.to)
    .map((r) => ({
      name: r.contact_name ?? `+${r.to}`,
      phone: r.to,
      text: r.text,
      wa: waLink(r.to, r.text),
      sms: smsLink(r.to, r.text),
      reason: r.hint || r.error,
    }));
}

export function fallbackForContacts(contacts: Contact[], textFor: (c: Contact) => string): FallbackItem[] {
  return contacts.map((c) => {
    const text = textFor(c);
    return { name: c.name, phone: c.phone, text, wa: waLink(c.phone, text), sms: smsLink(c.phone, text) };
  });
}
