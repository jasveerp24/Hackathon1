// Turns whatever the user said into exactly "yes", "no" or null (unclear).
// The backend only accepts a few exact words, so we normalise here first.
const NO_WORDS = /\b(no|nope|nah|cancel|stop|don't|do not|non)\b/i;
const YES_WORDS = /\b(yes|yeah|yep|yup|sure|ok|okay|confirm|go ahead|do it|oui|d'accord)\b/i;

export class YesNoParser {
  static parse(text) {
    // "No" is checked first, so "yes... no wait" is treated as a refusal, the safer outcome.
    if (NO_WORDS.test(text)) {
      return "no";
    }
    if (YES_WORDS.test(text)) {
      return "yes";
    }
    return null;
  }
}
