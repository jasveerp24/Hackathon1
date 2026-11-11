// The only file that knows the backend exists. Replace this class to change transport.
export class JarvisApi {
  constructor(baseUrl, timeoutMs) {
    this.baseUrl = baseUrl;
    this.timeoutMs = timeoutMs;

    // One id per app launch, so the backend keeps this conversation's history
    // and its pending confirmation separate from other users.
    this.sessionId = Math.random().toString(36).slice(2);
  }

  // Returns { reply: string, awaiting_confirmation: boolean }
  async ask(text) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: this.sessionId, text }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }
}
