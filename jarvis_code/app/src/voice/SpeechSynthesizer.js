import * as Speech from "expo-speech";

// Text-to-speech. speak() resolves only when the phone has FINISHED talking,
// which is what lets the assistant avoid listening to its own voice.
export class SpeechSynthesizer {
  constructor(language, rate) {
    this.language = language;
    this.rate = rate;
  }

  // Replies are written for the eyes; strip what sounds silly when read aloud.
  clean(text) {
    return text
      .replace(/https?:\/\/\S+/g, "")
      .replace(/[*_#`>]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  speak(text) {
    const spoken = this.clean(text);
    if (spoken === "") {
      return Promise.resolve();
    }

    return new Promise((resolve) => {
      Speech.stop();
      // Done, stopped or failed: in every case the wait is over.
      Speech.speak(spoken, {
        language: this.language,
        rate: this.rate,
        onDone: resolve,
        onStopped: resolve,
        onError: resolve,
      });
    });
  }

  stop() {
    Speech.stop();
  }
}
