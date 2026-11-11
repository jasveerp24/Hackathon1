// Same wording as backend/whatsapp_alerts/templates.py, so the free wa.me
// fallback still works when the backend is unreachable. Keep both in sync.
import type { AlertEvent, Lang } from './types';

type Values = Record<string, string>;

const ORDER: Record<AlertEvent, string[]> = {
  trip_started: ['person', 'plan', 'due_time'],
  missed_checkin: ['person', 'plan', 'due_time', 'emergency_number'],
  sos: ['person', 'location', 'emergency_number'],
  hazard_warning: ['person', 'plan', 'warning'],
  checked_in: ['person', 'time'],
  custom: ['person', 'message', 'app_name'],
};

const BODIES: Record<AlertEvent, Record<Lang, string>> = {
  trip_started: {
    en: 'Safety alert: {{1}} has started: {{2}}. Expected back by {{3}}. You will get a WhatsApp alert if they do not check in on time.',
    fr: "Alerte sécurité : {{1}} est parti(e) : {{2}}. Retour prévu avant {{3}}. Vous recevrez une alerte WhatsApp si le retour n'est pas confirmé à temps.",
  },
  missed_checkin: {
    en: 'URGENT: {{1}} has not checked in. Plan: {{2}}. They were due back by {{3}}. Please call them now. If you cannot reach them, call {{4}} for help.',
    fr: "URGENT : {{1}} n'a pas confirmé son retour. Prévu : {{2}}. Retour prévu avant {{3}}. Appelez-le/la maintenant. Si vous n'arrivez pas à le/la joindre, appelez le {{4}} pour obtenir de l'aide.",
  },
  sos: {
    en: 'SOS: {{1}} pressed the emergency button. Last location: {{2}}. Call them now and call {{3}} if needed.',
    fr: "SOS : {{1}} a appuyé sur le bouton d'urgence. Dernière position : {{2}}. Appelez-le/la maintenant et appelez le {{3}} si nécessaire.",
  },
  hazard_warning: {
    en: 'Safety warning for {{1}} ({{2}}): {{3}}. Please check on them.',
    fr: 'Avertissement sécurité pour {{1}} ({{2}}) : {{3}}. Merci de prendre de ses nouvelles.',
  },
  checked_in: {
    en: 'Good news: {{1}} checked in safely at {{2}}. No action needed.',
    fr: 'Bonne nouvelle : {{1}} a confirmé son retour à {{2}}. Aucune action nécessaire.',
  },
  custom: {
    en: 'Safety alert about {{1}}: {{2}}. Sent by the {{3}} app. Please contact them if you are worried.',
    fr: "Alerte sécurité concernant {{1}} : {{2}}. Envoyé par l'application {{3}}. Contactez-le/la si vous êtes inquiet.",
  },
};

export function renderMessage(event: AlertEvent, lang: Lang, values: Values): string {
  let text = BODIES[event][lang] ?? BODIES[event].en;
  ORDER[event].forEach((key, i) => {
    const v = (values[key] ?? '').toString().split(/\s+/).join(' ').trim() || '-';
    text = text.split(`{{${i + 1}}}`).join(v);
  });
  return text;
}

/** '14:30, 03/11' in Mauritius time, same as the backend. */
export function fmtTime(d: Date | string): string {
  const date = typeof d === 'string' ? new Date(d) : d;
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Indian/Mauritius',
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  return `${get('hour')}:${get('minute')}, ${get('day')}/${get('month')}`;
}

// ---- UI strings ----
export const UI = {
  en: {
    family: 'Family to alert on WhatsApp',
    name: 'Name',
    phone: 'WhatsApp number',
    language: 'Message language',
    add: 'Add',
    remove: 'Remove',
    noContacts: 'Add at least one family member before starting.',
    startTitle: 'Before you go',
    yourName: 'Your name',
    yourPhone: 'Your WhatsApp (to check in by replying SAFE)',
    plan: 'What are you doing, and where?',
    planPh: 'e.g. Hiking Le Pouce trail, back at the car park',
    backBy: 'Check in by',
    grace: 'Alert family after (minutes late)',
    start: 'Start & tell family',
    active: 'Check-in running',
    dueIn: 'Due back in',
    overdueBy: 'Overdue by',
    familyAlertedAt: 'Family will be alerted at',
    familyAlerted: 'Family has been alerted',
    imBack: "I'm safe",
    cancel: 'Cancel',
    sos: 'SOS',
    sosConfirm: 'Send SOS with your location to all family contacts?',
    sending: 'Sending…',
    log: 'Alerts sent',
    noLog: 'No alerts yet.',
    fallbackTitle: 'WhatsApp could not be sent automatically',
    fallbackHelp: 'Tap each name to open WhatsApp with the message ready, then press Send.',
    close: 'Close',
    dryRun: 'Demo mode: messages are logged, not sent (no API key).',
    textMode: 'Plain-text mode: family must have messaged the number in the last 24 h.',
    offline: 'Server unreachable. Using offline fallback.',
    consentLabel: 'This person agreed to get WhatsApp safety alerts about me, including my location if I press SOS.',
    privacy: 'Your data',
    privacyInfo: 'We keep trips and alerts for {days} days, then delete them. Every action is recorded in an audit log where any later change can be detected.',
    download: 'Download my data',
    erase: 'Delete all my data',
    eraseConfirm: 'Delete all your family contacts, trips and alerts? This cannot be undone.',
  },
  fr: {
    family: 'Famille à prévenir sur WhatsApp',
    name: 'Nom',
    phone: 'Numéro WhatsApp',
    language: 'Langue du message',
    add: 'Ajouter',
    remove: 'Retirer',
    noContacts: 'Ajoutez au moins un membre de la famille avant de partir.',
    startTitle: 'Avant de partir',
    yourName: 'Votre nom',
    yourPhone: 'Votre WhatsApp (pour confirmer en répondant SAFE)',
    plan: 'Que faites-vous, et où ?',
    planPh: 'ex. Randonnée au Pouce, retour au parking',
    backBy: 'Confirmer avant',
    grace: 'Prévenir la famille après (minutes de retard)',
    start: 'Démarrer et prévenir la famille',
    active: 'Suivi en cours',
    dueIn: 'Retour prévu dans',
    overdueBy: 'En retard de',
    familyAlertedAt: 'La famille sera prévenue à',
    familyAlerted: 'La famille a été prévenue',
    imBack: 'Je suis en sécurité',
    cancel: 'Annuler',
    sos: 'SOS',
    sosConfirm: 'Envoyer un SOS avec votre position à toute la famille ?',
    sending: 'Envoi…',
    log: 'Alertes envoyées',
    noLog: 'Aucune alerte.',
    fallbackTitle: "WhatsApp n'a pas pu être envoyé automatiquement",
    fallbackHelp: 'Touchez chaque nom pour ouvrir WhatsApp avec le message prêt, puis appuyez sur Envoyer.',
    close: 'Fermer',
    dryRun: 'Mode démo : messages enregistrés, non envoyés (pas de clé API).',
    textMode: 'Mode texte : la famille doit avoir écrit au numéro dans les dernières 24 h.',
    offline: 'Serveur injoignable. Mode secours hors ligne.',
    consentLabel: "Cette personne accepte de recevoir des alertes de sécurité WhatsApp à mon sujet, y compris ma position si j'appuie sur SOS.",
    privacy: 'Vos données',
    privacyInfo: 'Les sorties et alertes sont gardées {days} jours, puis supprimées. Chaque action est enregistrée dans un journal où toute modification est détectable.',
    download: 'Télécharger mes données',
    erase: 'Supprimer toutes mes données',
    eraseConfirm: 'Supprimer tous vos contacts, sorties et alertes ? Action irréversible.',
  },
} as const;

export type UIStrings = { [K in keyof typeof UI.en]: string };
