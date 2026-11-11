// ONE place to adapt the kit to the theme revealed on the day.
// Pick a preset in ACTIVE_THEME below (or copy one and edit the words).
// Only screen words change here; the WhatsApp message templates stay the same,
// so nothing needs re-approval by Meta.
import type { UIStrings } from './messages';
import type { Lang } from './types';

type ThemeWords = Pick<
  UIStrings,
  'startTitle' | 'plan' | 'planPh' | 'backBy' | 'start' | 'active' | 'imBack' | 'cancel'
>;

export interface ThemePreset {
  id: string;
  appName: string;
  /** Default hours until check-in is due when the form opens. */
  defaultHours: number;
  /** Minutes late before the family is alerted. */
  defaultGraceMinutes: number;
  /** Example hazard for the demo button, e.g. what a weather/data agent might detect. */
  hazardExample: Record<Lang, string>;
  /** Example free-text alert for the "custom alert" demo button. */
  customExample: Record<Lang, string>;
  words: Record<Lang, ThemeWords>;
}

export const PRESETS: Record<string, ThemePreset> = {
  general: {
    id: 'general',
    appName: 'Safe Check-in',
    defaultHours: 2,
    defaultGraceMinutes: 30,
    hazardExample: {
      en: 'Heavy rain and flash flood warning in the area',
      fr: "Avis de fortes pluies et risque d'inondation dans la zone",
    },
    customExample: {
      en: 'Phone battery at 5%, may go offline soon',
      fr: 'Batterie du téléphone à 5 %, risque de coupure bientôt',
    },
    words: {
      en: {
        startTitle: 'Before you go',
        plan: 'What are you doing, and where?',
        planPh: 'e.g. Hiking Le Pouce trail, back at the car park',
        backBy: 'Check in by',
        start: 'Start & tell family',
        active: 'Check-in running',
        imBack: "I'm safe",
        cancel: 'Cancel',
      },
      fr: {
        startTitle: 'Avant de partir',
        plan: 'Que faites-vous, et où ?',
        planPh: 'ex. Randonnée au Pouce, retour au parking',
        backBy: 'Confirmer avant',
        start: 'Démarrer et prévenir la famille',
        active: 'Suivi en cours',
        imBack: 'Je suis en sécurité',
        cancel: 'Annuler',
      },
    },
  },

  elderly: {
    id: 'elderly',
    appName: 'Granmoun Check-in',
    defaultHours: 12,
    defaultGraceMinutes: 60,
    hazardExample: {
      en: 'Heatwave today, 34°C expected: please check they are drinking water',
      fr: "Canicule aujourd'hui, 34 °C prévus : vérifiez qu'il/elle boit de l'eau",
    },
    customExample: {
      en: 'Missed the morning medication reminder',
      fr: 'Rappel de médicament du matin non confirmé',
    },
    words: {
      en: {
        startTitle: "Today's check-in",
        plan: "Today's plan",
        planPh: 'e.g. At home today, market in the morning',
        backBy: 'Next check-in by',
        start: 'Start check-in & tell family',
        active: 'Waiting for check-in',
        imBack: "I'm OK",
        cancel: 'Cancel',
      },
      fr: {
        startTitle: 'Suivi du jour',
        plan: 'Programme du jour',
        planPh: 'ex. À la maison, marché le matin',
        backBy: 'Prochain contrôle avant',
        start: 'Démarrer et prévenir la famille',
        active: 'En attente de confirmation',
        imBack: 'Je vais bien',
        cancel: 'Annuler',
      },
    },
  },

  walkHome: {
    id: 'walkHome',
    appName: 'Walk Home Safe',
    defaultHours: 1,
    defaultGraceMinutes: 15,
    hazardExample: {
      en: 'Street lights reported out on this route',
      fr: 'Éclairage public signalé en panne sur ce trajet',
    },
    customExample: {
      en: 'Feeling unsafe, someone is following me',
      fr: "Je ne me sens pas en sécurité, quelqu'un me suit",
    },
    words: {
      en: {
        startTitle: 'Before you walk',
        plan: 'From where to where?',
        planPh: 'e.g. MDX campus to Flic en Flac bus stop',
        backBy: 'Arrive by',
        start: 'Start walk & tell family',
        active: 'Walk in progress',
        imBack: "I've arrived",
        cancel: 'Cancel walk',
      },
      fr: {
        startTitle: 'Avant de partir',
        plan: "D'où vers où ?",
        planPh: 'ex. Campus MDX vers arrêt de bus de Flic en Flac',
        backBy: 'Arrivée avant',
        start: 'Partir et prévenir la famille',
        active: 'Trajet en cours',
        imBack: 'Je suis arrivé(e)',
        cancel: 'Annuler le trajet',
      },
    },
  },

  cyclone: {
    id: 'cyclone',
    appName: 'Cyclone Safe',
    defaultHours: 3,
    defaultGraceMinutes: 30,
    hazardExample: {
      en: 'Cyclone warning class 3 in force, flooding reported nearby',
      fr: 'Avis de cyclone classe 3 en vigueur, inondations signalées à proximité',
    },
    customExample: {
      en: 'Moved to the refuge centre, phone signal is weak',
      fr: 'Parti(e) au centre de refuge, réseau faible',
    },
    words: {
      en: {
        startTitle: 'Tell family where you are',
        plan: 'Where are you sheltering?',
        planPh: 'e.g. At home in Port Louis, may go to the refuge centre',
        backBy: 'Check in again by',
        start: 'Share & tell family',
        active: 'Sheltering',
        imBack: "I'm safe",
        cancel: 'Cancel',
      },
      fr: {
        startTitle: 'Dites à la famille où vous êtes',
        plan: 'Où êtes-vous à l’abri ?',
        planPh: 'ex. À la maison à Port-Louis, peut-être au centre de refuge',
        backBy: 'Prochain contrôle avant',
        start: 'Partager et prévenir la famille',
        active: "À l'abri",
        imBack: 'Je suis en sécurité',
        cancel: 'Annuler',
      },
    },
  },

  fishing: {
    id: 'fishing',
    appName: 'Pêcheur Buddy',
    defaultHours: 4,
    defaultGraceMinutes: 30,
    hazardExample: {
      en: 'High-wave warning, swells up to 3.5 m off the south coast',
      fr: "Avis de fortes houles, jusqu'à 3,5 m au large de la côte sud",
    },
    customExample: {
      en: 'Engine trouble, drifting slowly towards the reef',
      fr: 'Panne de moteur, dérive lente vers le récif',
    },
    words: {
      en: {
        startTitle: 'Before you go to sea',
        plan: 'Where are you going?',
        planPh: 'e.g. Fishing off Le Morne, 2 km out, boat "Ti Lamer"',
        backBy: 'Back by',
        start: 'Start trip & tell family',
        active: 'Trip in progress',
        imBack: "I'm back safe",
        cancel: 'Cancel trip',
      },
      fr: {
        startTitle: 'Avant de partir en mer',
        plan: 'Où allez-vous ?',
        planPh: 'ex. Pêche au large du Morne, 2 km, bateau « Ti Lamer »',
        backBy: 'Retour avant',
        start: 'Partir et prévenir la famille',
        active: 'Sortie en cours',
        imBack: 'Je suis rentré(e)',
        cancel: 'Annuler la sortie',
      },
    },
  },
};

// 👇 On the day: change this one line (general | elderly | walkHome | cyclone | fishing)
export const ACTIVE_THEME: ThemePreset = PRESETS.general;
