import { createContext, useContext, type ReactNode } from 'react';
import { UI, type UIStrings } from './messages';
import { ACTIVE_THEME, type ThemePreset } from './theme';
import type { Lang } from './types';
import { useWhatsAppAlerts, type WhatsAppAlerts } from './useWhatsAppAlerts';

interface Ctx {
  alerts: WhatsAppAlerts;
  t: UIStrings;
  lang: Lang;
  theme: ThemePreset;
}

const AlertsContext = createContext<Ctx | null>(null);

/**
 * Wrap the part of your app that uses the WhatsApp components.
 * ownerId = your logged-in user id (any stable string).
 * lang = language of the UI (each family member's message language is set per contact).
 * theme = screen words for the day's theme (defaults to ACTIVE_THEME in theme.ts).
 */
export function WhatsAppAlertsProvider({
  ownerId,
  lang = 'en',
  theme = ACTIVE_THEME,
  children,
}: {
  ownerId: string;
  lang?: Lang;
  theme?: ThemePreset;
  children: ReactNode;
}) {
  const alerts = useWhatsAppAlerts(ownerId, theme.appName);
  const t: UIStrings = { ...UI[lang], ...theme.words[lang] };
  return <AlertsContext.Provider value={{ alerts, t, lang, theme }}>{children}</AlertsContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAlerts(): Ctx {
  const c = useContext(AlertsContext);
  if (!c) throw new Error('Wrap your component in <WhatsAppAlertsProvider ownerId="...">');
  return c;
}
