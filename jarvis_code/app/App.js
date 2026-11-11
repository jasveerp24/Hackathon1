import React, { useState } from "react";
import { Button, ScrollView, Switch, Text, TextInput, View } from "react-native";

import { CONFIG } from "./src/config";
import { JarvisApi } from "./src/api/JarvisApi";
import { SpeechRecognizer } from "./src/voice/SpeechRecognizer";
import { SpeechSynthesizer } from "./src/voice/SpeechSynthesizer";
import { VoiceAssistant, Status } from "./src/VoiceAssistant";
import { useVoiceAssistant } from "./src/useVoiceAssistant";
import { styles } from "./src/styles";

// Built once, outside React, so re-renders never create a second assistant.
const assistant = new VoiceAssistant({
  api: new JarvisApi(CONFIG.apiUrl, CONFIG.requestTimeoutMs),
  recognizer: new SpeechRecognizer(CONFIG.sttLocale, CONFIG.listenTimeoutMs),
  synthesizer: new SpeechSynthesizer(CONFIG.ttsLanguage, CONFIG.ttsRate),
  handsFree: CONFIG.handsFree,
});

const STATUS_TEXT = {
  [Status.IDLE]: "Ready",
  [Status.LISTENING]: "Listening...",
  [Status.THINKING]: "Thinking...",
  [Status.SPEAKING]: "Speaking...",
};

const BUTTON_TEXT = {
  [Status.IDLE]: "Talk to JARVIS",
  [Status.LISTENING]: "Stop",
  [Status.THINKING]: "Cancel",
  [Status.SPEAKING]: "Interrupt",
};

function LogLine({ line }) {
  let lineStyle = styles.lineYou;
  if (line.who === "JARVIS") {
    lineStyle = styles.lineBot;
  }
  return (
    <Text style={lineStyle}>
      {line.who}: {line.text}
    </Text>
  );
}

export default function App() {
  const state = useVoiceAssistant(assistant);
  const [typed, setTyped] = useState("");

  // The text box is the backup plan if the venue is too noisy for speech recognition.
  const sendTyped = () => {
    if (typed.trim() === "") {
      return;
    }
    assistant.start(typed.trim());
    setTyped("");
  };

  return (
    <View style={styles.container}>
      <Text style={styles.status}>{STATUS_TEXT[state.status]}</Text>
      <Text style={styles.partial}>{state.partial}</Text>

      <ScrollView style={styles.log}>
        {state.log.map((line, index) => (
          <LogLine key={index} line={line} />
        ))}
      </ScrollView>

      {state.awaitingConfirm && (
        <View style={styles.row}>
          <Button title="Yes" onPress={() => assistant.answerConfirmation(true)} />
          <Button title="No" onPress={() => assistant.answerConfirmation(false)} />
        </View>
      )}

      <View style={styles.switchRow}>
        <Text>Hands-free conversation</Text>
        <Switch value={state.handsFree} onValueChange={(value) => assistant.setHandsFree(value)} />
      </View>

      <TextInput
        style={styles.input}
        value={typed}
        onChangeText={setTyped}
        onSubmitEditing={sendTyped}
        placeholder="Or type here..."
      />

      <Button title={BUTTON_TEXT[state.status]} onPress={() => assistant.toggleMic()} />
    </View>
  );
}
