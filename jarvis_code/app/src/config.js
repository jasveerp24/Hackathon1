// Every setting you may need to change lives here. Nothing else hardcodes these.
export const CONFIG = {
  // Your laptop's LAN IP on a physical phone. Android emulator: http://10.0.2.2:8000
  apiUrl: "http://192.168.1.10:8000",

  // Language the recogniser listens for (e.g. "fr-FR"). Test which one your team is understood in.
  sttLocale: "en-US",

  // Language/voice the phone speaks the reply in. Keep it matching sttLocale.
  ttsLanguage: "en-US",
  ttsRate: 1.0,

  // How long to wait for the user to speak before giving up.
  listenTimeoutMs: 8000,

  // How long to wait for the backend before telling the user it is unreachable.
  requestTimeoutMs: 20000,

  // true = after JARVIS speaks, the mic reopens by itself (continuous conversation).
  handsFree: false,
};
