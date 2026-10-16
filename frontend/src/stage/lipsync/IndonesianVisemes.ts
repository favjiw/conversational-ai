/**
 * Indonesian text -> Oculus viseme timeline.
 *
 * Indonesian spelling is close to phonemic, so a handful of letter rules give
 * usable mouth shapes without a pronunciation dictionary. With TTS word
 * timings (Edge WordBoundary) each word's visemes fill that word's time
 * window; without them the whole line is spread over the audio duration.
 */

/** Oculus/OVR viseme set (15), the order Rocketbox models use. */
export const OCULUS_VISEMES = ['sil', 'PP', 'FF', 'TH', 'DD', 'kk', 'CH', 'SS', 'nn', 'RR', 'aa', 'E', 'I', 'O', 'U'] as const;
export type Viseme = (typeof OCULUS_VISEMES)[number];

export interface WordTiming {
  offset_ms: number;
  duration_ms: number;
  text: string;
}

export interface VisemeSegment {
  start: number; // seconds from audio start
  end: number;
  viseme: Viseme;
}

interface Phone {
  viseme: Viseme;
  /** Relative duration inside the word. */
  weight: number;
}

const DIGITS = ['nol', 'satu', 'dua', 'tiga', 'empat', 'lima', 'enam', 'tujuh', 'delapan', 'sembilan'];

const DIGRAPHS: Record<string, Phone> = {
  ng: { viseme: 'nn', weight: 0.7 },
  ny: { viseme: 'nn', weight: 0.7 },
  sy: { viseme: 'CH', weight: 0.7 },
  kh: { viseme: 'kk', weight: 0.6 },
  th: { viseme: 'TH', weight: 0.6 },
};

const LETTERS: Record<string, Phone> = {
  a: { viseme: 'aa', weight: 1 },
  e: { viseme: 'E', weight: 0.9 },
  i: { viseme: 'I', weight: 0.9 },
  o: { viseme: 'O', weight: 1 },
  u: { viseme: 'U', weight: 0.9 },
  b: { viseme: 'PP', weight: 0.55 },
  p: { viseme: 'PP', weight: 0.55 },
  m: { viseme: 'PP', weight: 0.6 },
  f: { viseme: 'FF', weight: 0.65 },
  v: { viseme: 'FF', weight: 0.65 },
  t: { viseme: 'DD', weight: 0.5 },
  d: { viseme: 'DD', weight: 0.5 },
  k: { viseme: 'kk', weight: 0.5 },
  g: { viseme: 'kk', weight: 0.5 },
  q: { viseme: 'kk', weight: 0.5 },
  c: { viseme: 'CH', weight: 0.6 },
  j: { viseme: 'CH', weight: 0.6 },
  s: { viseme: 'SS', weight: 0.7 },
  z: { viseme: 'SS', weight: 0.65 },
  x: { viseme: 'SS', weight: 0.7 },
  n: { viseme: 'nn', weight: 0.55 },
  l: { viseme: 'nn', weight: 0.55 },
  r: { viseme: 'RR', weight: 0.6 },
  y: { viseme: 'I', weight: 0.45 },
  w: { viseme: 'U', weight: 0.45 },
  h: { viseme: 'sil', weight: 0.3 },
};

/** Normalize a word: lowercase, strip accents, spell out digits, keep letters only. */
function normalizeWord(word: string): string {
  return word
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/\d/g, (d) => DIGITS[Number(d)] + ' ')
    .replace(/[^a-z ]/g, '');
}

/** Letters of one word -> visemes with relative durations (repeats merged). */
export function wordToPhones(word: string): Phone[] {
  const s = normalizeWord(word);
  const phones: Phone[] = [];
  for (let i = 0; i < s.length; ) {
    if (s[i] === ' ') {
      i++;
      continue;
    }
    const pair = DIGRAPHS[s.slice(i, i + 2)];
    const phone = pair ?? LETTERS[s[i]];
    i += pair ? 2 : 1;
    if (!phone) continue;
    const last = phones[phones.length - 1];
    if (last && last.viseme === phone.viseme) {
      last.weight += phone.weight * 0.5;
    } else {
      phones.push({ ...phone });
    }
  }
  return phones;
}

/** Spread phones over [start, end] proportionally to their weights. */
function fill(segments: VisemeSegment[], phones: Phone[], start: number, end: number): void {
  const total = phones.reduce((sum, p) => sum + p.weight, 0);
  if (total <= 0 || end <= start) return;
  let t = start;
  for (const p of phones) {
    const d = ((end - start) * p.weight) / total;
    segments.push({ start: t, end: t + d, viseme: p.viseme });
    t += d;
  }
}

/** Remove pause markers, bracketed cues and written laughter before estimating. */
function spokenWords(text: string): string[] {
  return text
    .replace(/\[.*?\]|\(.*?\)/g, ' ')
    .replace(/\b(?:ha){2,}h?\b|\b(?:he){2,}h?\b|\bwk(?:wk)*\b/gi, ' ')
    .split(/\s+/)
    .filter((w) => /[\p{L}\d]/u.test(w));
}

/**
 * Build the viseme timeline for one spoken line.
 * @param timings Per-word timings from TTS, or null to estimate.
 * @param durationSec Audio length, needed when estimating.
 */
export function buildVisemeTimeline(text: string, timings: WordTiming[] | null, durationSec?: number): VisemeSegment[] {
  const segments: VisemeSegment[] = [];

  if (timings && timings.length) {
    for (const w of timings) {
      const start = w.offset_ms / 1000;
      fill(segments, wordToPhones(w.text), start, start + w.duration_ms / 1000);
    }
    return segments;
  }

  if (!durationSec || durationSec <= 0) return segments;

  // Estimate: words share the audio by phone weight; punctuation adds a pause.
  const words = spokenWords(text).map((w) => ({
    phones: wordToPhones(w),
    pause: /[.,!?;:]$/.test(w) ? (/[.!?]$/.test(w) ? 1.6 : 0.8) : 0.15,
  }));
  const totalWeight = words.reduce((s, w) => s + w.phones.reduce((a, p) => a + p.weight, 0) + w.pause, 0);
  if (totalWeight <= 0) return segments;
  const lead = 0.05;
  const scale = (durationSec * 0.95 - lead) / totalWeight;
  let t = lead;
  for (const w of words) {
    const len = w.phones.reduce((a, p) => a + p.weight, 0) * scale;
    fill(segments, w.phones, t, t + len);
    t += len + w.pause * scale;
  }
  return segments;
}
