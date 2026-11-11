import { YesNoParser } from "./voice/YesNoParser";

export const Status = Object.freeze({
  IDLE: "idle",
  LISTENING: "listening",
  THINKING: "thinking",
  SPEAKING: "speaking",
});

// The conductor of one conversation on the phone:  listen -> ask backend -> speak -> repeat.
// It has no React and no native code in it, so it can be tested with fake parts.
export class VoiceAssistant {
  constructor({ api, recognizer, synthesizer, handsFree }) {
    this.api = api;
    this.recognizer = recognizer;
    this.synthesizer = synthesizer;
    this.listeners = new Set();

    // Every conversation run gets a number. Tapping stop (or starting again) bumps it,
    // and any older run notices it is out of date and quietly ends.
    this.runId = 0;

    this.state = {
      status: Status.IDLE,
      log: [],
      partial: "",
      awaitingConfirm: false,
      handsFree,
    };
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  update(changes) {
    this.state = { ...this.state, ...changes };
    this.listeners.forEach((listener) => listener(this.state));
  }

  addLine(who, text) {
    this.update({ log: [...this.state.log, { who, text }] });
  }

  setHandsFree(value) {
    this.update({ handsFree: value });
  }

  toggleMic() {
    if (this.state.status === Status.IDLE) {
      this.start();
      return;
    }
    this.stop();
  }

  answerConfirmation(isYes) {
    let word = "no";
    if (isYes) {
      word = "yes";
    }
    this.start(word);
  }

  // typedText is optional: pass it to skip the microphone (text box, buttons).
  start(typedText) {
    this.interrupt();
    this.converse(this.runId, typedText);
  }

  stop() {
    this.interrupt();
    this.update({ status: Status.IDLE, partial: "" });
  }

  interrupt() {
    this.runId += 1;
    this.recognizer.cancel();
    this.synthesizer.stop();
  }

  async converse(id, firstText) {
    let typed = firstText;
    let keepGoing = true;

    while (keepGoing && id === this.runId) {
      keepGoing = await this.turn(id, typed);
      typed = undefined;
    }

    if (id === this.runId) {
      this.update({ status: Status.IDLE, partial: "" });
    }
  }

  // One full exchange. Returns true if the loop should go round again.
  async turn(id, typed) {
    let text = typed;

    if (!text) {
      this.update({ status: Status.LISTENING, partial: "" });
      text = await this.recognizer.listen((partial) => this.update({ partial }));
    }
    if (id !== this.runId) {
      return false;
    }
    if (!text) {
      return false;
    }

    if (this.state.awaitingConfirm) {
      const verdict = YesNoParser.parse(text);
      if (verdict === null) {
        await this.say("Please say yes or no.");
        return true;
      }
      text = verdict;
    }

    this.addLine("You", text);
    this.update({ status: Status.THINKING, partial: "" });

    let data;
    try {
      data = await this.api.ask(text);
    } catch (error) {
      if (id !== this.runId) {
        return false;
      }
      const message = "I can't reach my brain. Is the server running?";
      this.addLine("JARVIS", message);
      await this.say(message);
      return false;
    }
    if (id !== this.runId) {
      return false;
    }

    this.addLine("JARVIS", data.reply);
    this.update({ awaitingConfirm: data.awaiting_confirmation });
    await this.say(data.reply);
    if (id !== this.runId) {
      return false;
    }

    // Keep listening if hands-free, or if JARVIS just asked "shall I go ahead?"
    return this.state.handsFree || this.state.awaitingConfirm;
  }

  async say(text) {
    this.update({ status: Status.SPEAKING });
    await this.synthesizer.speak(text);
  }
}
