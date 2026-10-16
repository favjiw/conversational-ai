import * as THREE from 'three';
import { ARKIT_BLENDSHAPES, type BlendshapeWeights } from './arkit';

interface MorphBinding {
  mesh: THREE.Mesh;
  index: number;
}

/**
 * Drives ARKit-named blendshapes on a loaded GLB character.
 *
 * A face is usually split over several meshes (head, teeth, tongue, eyelashes)
 * that share morph target names, so one name may bind to many meshes. Weights
 * are written straight to `morphTargetInfluences` of every bound mesh.
 */
export class FaceDriver {
  /** ARKit names the model provides. */
  readonly available: string[];
  /** ARKit names the model lacks (animating them is a no-op). */
  readonly missing: string[];
  /** When true, animators leave the face alone (debug sliders own it). */
  manualOverride = false;

  private bindings = new Map<string, MorphBinding[]>();
  private weights = new Map<string, number>();

  constructor(root: THREE.Object3D) {
    root.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh || !mesh.morphTargetDictionary || !mesh.morphTargetInfluences) return;
      for (const [name, index] of Object.entries(mesh.morphTargetDictionary)) {
        const list = this.bindings.get(name) ?? [];
        list.push({ mesh, index });
        this.bindings.set(name, list);
      }
    });

    this.available = ARKIT_BLENDSHAPES.filter((n) => this.bindings.has(n));
    this.missing = ARKIT_BLENDSHAPES.filter((n) => !this.bindings.has(n));
  }

  /** True when the model has at least one ARKit blendshape. */
  get hasArkit(): boolean {
    return this.available.length > 0;
  }

  /** True when any mesh has a morph target with this exact name (ARKit or not). */
  has(name: string): boolean {
    return this.bindings.has(name);
  }

  get(name: string): number {
    return this.weights.get(name) ?? 0;
  }

  /** Set one blendshape (clamped to 0..1). Unknown names are ignored. */
  set(name: string, weight: number): void {
    const list = this.bindings.get(name);
    if (!list) return;
    const w = Math.max(0, Math.min(1, weight));
    this.weights.set(name, w);
    for (const { mesh, index } of list) {
      mesh.morphTargetInfluences![index] = w;
    }
  }

  /** Set several blendshapes at once; names not given keep their weight. */
  setWeights(weights: BlendshapeWeights): void {
    for (const [name, w] of Object.entries(weights)) {
      if (w !== undefined) this.set(name, w);
    }
  }

  /** Return every ARKit blendshape to 0. */
  reset(): void {
    for (const name of this.available) this.set(name, 0);
  }

  /** One-line summary for the load log. */
  describe(): string {
    return `${this.available.length}/${ARKIT_BLENDSHAPES.length} ARKit blendshapes` +
      (this.missing.length ? ` (missing: ${this.missing.join(', ')})` : '');
  }
}
