import { useEffect, useState } from "react";

// Thin bridge: re-renders a component whenever the VoiceAssistant's state changes.
export function useVoiceAssistant(assistant) {
  const [state, setState] = useState(assistant.state);

  useEffect(() => {
    const unsubscribe = assistant.subscribe(setState);
    setState(assistant.state);
    return () => {
      unsubscribe();
    };
  }, [assistant]);

  return state;
}
