import * as THREE from 'three';

/** Where a presenter stands; the set is built around each one. */
export interface StudioSpot {
  personaId: string;
  x: number;
  headY: number;
  /** -1 when the screen edge is to the left of the presenter, +1 to the right. */
  outerSide: -1 | 1;
  /** Text on the wall sign of this half. */
  sign: { text: string; color: string; glow: string };
}

const WALL_Z = -1.4;
/** Desk top sits this far below the head bone, so it fits short and tall presenters. */
const DESK_BELOW_HEAD = 0.55;

/**
 * Procedural radio studio behind and in front of each presenter: wall with
 * acoustic foam, an illuminated sign, a desk with an LED strip and a boom
 * microphone. Built from primitives only (no external assets), so it is cheap
 * enough for a laptop GPU and carries no licensing questions.
 */
export class StudioSet {
  readonly group = new THREE.Group();
  private disposables: Array<{ dispose(): void }> = [];

  constructor(spots: StudioSpot[]) {
    this.group.name = 'StudioSet';
    this.buildWall();
    for (const spot of spots) this.buildSpot(spot);
  }

  dispose(): void {
    this.group.removeFromParent();
    for (const d of this.disposables) d.dispose();
  }

  private material(params: THREE.MeshStandardMaterialParameters): THREE.MeshStandardMaterial {
    const m = new THREE.MeshStandardMaterial(params);
    this.disposables.push(m);
    return m;
  }

  /** Neon-like emissive material that skips tone mapping so colors stay saturated. */
  private glow(color: number, map?: THREE.Texture): THREE.MeshBasicMaterial {
    const m = new THREE.MeshBasicMaterial({ color, map });
    m.toneMapped = false;
    this.disposables.push(m);
    return m;
  }

  private box(w: number, h: number, d: number, mat: THREE.Material, x: number, y: number, z: number): THREE.Mesh {
    const geo = new THREE.BoxGeometry(w, h, d);
    this.disposables.push(geo);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(x, y, z);
    this.group.add(mesh);
    return mesh;
  }

  private buildWall(): void {
    const wall = this.box(8, 4, 0.05, this.material({ color: 0x1d2130, roughness: 0.95 }), 0, 1.8, WALL_Z - 0.03);
    wall.receiveShadow = true;
    // Thin warm trim line along the wall
    this.box(8, 0.02, 0.02, this.glow(0xf59e0b), 0, 0.98, WALL_Z);
  }

  private buildSpot(spot: StudioSpot): void {
    const { x, headY, outerSide } = spot;
    const DESK_TOP_Y = headY - DESK_BELOW_HEAD;

    // Acoustic foam panels on the outer side of the presenter
    const foamA = this.material({ color: 0x2a3043, roughness: 1 });
    const foamB = this.material({ color: 0x343c54, roughness: 1 });
    const size = 0.26;
    const gap = 0.025;
    const cols = 3;
    const rows = 4;
    const startX = x + outerSide * 0.38;
    for (let c = 0; c < cols; c++) {
      for (let r = 0; r < rows; r++) {
        const px = startX + outerSide * c * (size + gap);
        const py = 1.05 + r * (size + gap);
        const tile = this.box(size, size, 0.05, (c + r) % 2 ? foamA : foamB, px, py, WALL_Z + 0.03);
        tile.receiveShadow = true;
      }
    }

    // Illuminated sign on the inner side, above head height
    const signMat = this.glow(0xffffff, this.signTexture(spot.sign));
    this.box(0.5, 0.16, 0.04, signMat, x - outerSide * 0.42, Math.min(headY + 0.45, 2.05), WALL_Z + 0.04);

    // Desk: top, front panel and a glowing LED strip
    const deskTop = this.box(1.3, 0.05, 0.7, this.material({ color: 0x2a221e, roughness: 0.6 }), x, DESK_TOP_Y, 0.6);
    deskTop.receiveShadow = true;
    deskTop.castShadow = true;
    this.box(1.3, 0.7, 0.04, this.material({ color: 0x12141b, roughness: 0.7 }), x, DESK_TOP_Y - 0.37, 0.95);
    this.box(1.3, 0.015, 0.01, this.glow(0x22d3ee), x, DESK_TOP_Y - 0.06, 0.975);

    this.buildMicrophone(spot);
  }

  /** Boom-arm microphone from the outer desk corner, stopping beside the mouth. */
  private buildMicrophone({ x, headY, outerSide }: StudioSpot): void {
    const DESK_TOP_Y = headY - DESK_BELOW_HEAD;
    const metal = this.material({ color: 0x1f2937, metalness: 0.8, roughness: 0.35 });
    const capsule = this.material({ color: 0x111827, metalness: 0.4, roughness: 0.5 });

    const base = new THREE.Vector3(x + outerSide * 0.5, DESK_TOP_Y, 0.55);
    const elbow = new THREE.Vector3(x + outerSide * 0.5, headY + 0.05, 0.45);
    const mic = new THREE.Vector3(x + outerSide * 0.16, headY - 0.16, 0.32);

    this.rod(base, elbow, 0.012, metal);
    this.rod(elbow, mic, 0.01, metal);

    const capGeo = new THREE.CylinderGeometry(0.032, 0.028, 0.15, 16);
    this.disposables.push(capGeo);
    const cap = new THREE.Mesh(capGeo, capsule);
    cap.position.copy(mic);
    // Point the capsule toward the mouth
    const mouth = new THREE.Vector3(x, headY - 0.12, 0.08);
    cap.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), mouth.clone().sub(mic).normalize());
    cap.castShadow = true;
    this.group.add(cap);
  }

  private rod(a: THREE.Vector3, b: THREE.Vector3, radius: number, mat: THREE.Material): void {
    const len = a.distanceTo(b);
    const geo = new THREE.CylinderGeometry(radius, radius, len, 8);
    this.disposables.push(geo);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(a).add(b).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    mesh.castShadow = true;
    this.group.add(mesh);
  }

  private signTexture({ text, color, glow }: StudioSpot['sign']): THREE.CanvasTexture {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 164;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = color;
    ctx.lineWidth = 10;
    ctx.strokeRect(12, 12, canvas.width - 24, canvas.height - 24);
    ctx.font = 'bold 84px Poppins, "Segoe UI", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = glow;
    ctx.shadowBlur = 24;
    ctx.fillStyle = color;
    ctx.fillText(text, canvas.width / 2, canvas.height / 2 + 4);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    this.disposables.push(tex);
    return tex;
  }
}
