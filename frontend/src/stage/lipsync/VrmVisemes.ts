import type { VRM } from '@pixiv/three-vrm';
import type { Viseme } from './IndonesianVisemes';

const VRM_VOWELS = ['aa', 'ih', 'ou', 'ee', 'oh'] as const;
type VrmVowel = (typeof VRM_VOWELS)[number];

/**
 * Oculus viseme -> VRM's five vowel mouth shapes. Consonants become a small,
 * partly closed version of the nearest vowel shape; bilabials (PP) close.
 */
const VISEME_TO_VRM: Record<Exclude<Viseme, 'sil'>, Partial<Record<VrmVowel, number>>> = {
  aa: { aa: 1 },
  E: { ee: 0.9 },
  I: { ih: 0.9 },
  O: { oh: 1 },
  U: { ou: 1 },
  PP: {},
  FF: { ih: 0.25 },
  TH: { ih: 0.3, aa: 0.1 },
  DD: { ih: 0.35, aa: 0.1 },
  kk: { aa: 0.3, ih: 0.1 },
  CH: { ou: 0.45, ih: 0.15 },
  SS: { ih: 0.4 },
  nn: { ih: 0.25, aa: 0.1 },
  RR: { oh: 0.35, aa: 0.1 },
};

/**
 * Drive a VRM's vowel shapes from viseme weights (anime style presenters).
 * Pass null to release the shapes the amplitude lip-sync does not own
 * (ih/ou/ee), so switching methods never leaves a mouth stuck open.
 */
export function applyVrmVisemes(vrm: VRM, visemes: Map<Viseme, number> | null): void {
  const manager = vrm.expressionManager;
  if (!manager) return;
  const out: Record<VrmVowel, number> = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
  if (visemes) {
    for (const [v, w] of visemes) {
      if (v === 'sil' || w < 1e-3) continue;
      for (const [vowel, k] of Object.entries(VISEME_TO_VRM[v])) {
        out[vowel as VrmVowel] += (k ?? 0) * w;
      }
    }
  }
  for (const vowel of VRM_VOWELS) {
    // aa/oh belong to the amplitude lip-sync when visemes are off
    if (!visemes && (vowel === 'aa' || vowel === 'oh')) continue;
    if (manager.getExpression(vowel)) manager.setValue(vowel, Math.min(1, out[vowel]));
  }
}
