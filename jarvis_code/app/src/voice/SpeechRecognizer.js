import { PermissionsAndroid, Platform } from "react-native";
import Voice from "@react-native-voice/voice";

// Speech-to-text. Turns one spoken utterance into one string.
// To switch to a cloud recogniser later, keep the same two methods: listen() and cancel().
export class SpeechRecognizer {
  constructor(locale, timeoutMs) {
    this.locale = locale;
    this.timeoutMs = timeoutMs;
    this.session = null;
  }

  async hasPermission() {
    if (Platform.OS !== "android") {
      return true;
    }
    const result = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.RECORD_AUDIO
    );
    return result === PermissionsAndroid.RESULTS.GRANTED;
  }

  // Resolves with the final transcript, or "" if nothing was heard.
  // onPartial(text) fires while the user is still talking (for live captions).
  listen(onPartial) {
    this.cancel();

    return new Promise((resolve) => {
      let lastHeard = "";
      const session = {};

      // Every way a session can end (result, error, timeout, cancel) goes through here.
      // The session check makes sure an OLD session can never close a NEW one.
      session.finish = (text) => {
        if (this.session !== session) {
          return;
        }
        this.session = null;
        clearTimeout(session.timer);
        Voice.onSpeechPartialResults = undefined;
        Voice.onSpeechResults = undefined;
        Voice.onSpeechError = undefined;
        Voice.cancel().catch(() => {});
        resolve(text);
      };

      this.session = session;
      session.timer = setTimeout(() => session.finish(lastHeard), this.timeoutMs);

      Voice.onSpeechPartialResults = (event) => {
        lastHeard = event.value?.[0] ?? lastHeard;
        if (onPartial) {
          onPartial(lastHeard);
        }
      };
      Voice.onSpeechResults = (event) => session.finish(event.value?.[0] ?? "");
      // Errors such as "no speech detected" are normal, so end quietly with what we have.
      Voice.onSpeechError = () => session.finish(lastHeard);

      this.start(session);
    });
  }

  async start(session) {
    const allowed = await this.hasPermission();
    if (!allowed) {
      session.finish("");
      return;
    }
    try {
      await Voice.start(this.locale);
    } catch (error) {
      session.finish("");
    }
  }

  cancel() {
    if (this.session) {
      this.session.finish("");
    }
  }
}
