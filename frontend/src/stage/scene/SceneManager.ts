import * as THREE from 'three';
import { VRM, VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { FaceDriver } from '../face/FaceDriver';
import { StudioSet, type StudioSpot } from './StudioSet';
import { applyGlbRestPose, ROCKETBOX_BONES, type GlbBoneMap } from '../face/GlbRig';

/** Which model to load for a presenter (from avatar.config.json "characters"). */
export interface CharacterSpec {
  name: string;
  /** "vrm" (anime VRM, expression manager) or "glb" (realistic, ARKit morph targets). */
  kind: 'vrm' | 'glb';
  url: string;
  /** Uniform scale for GLB files authored in other units (e.g. 0.01 for centimetres). */
  scale?: number;
  /** Extra Y rotation (rad) for models that do not face +Z. */
  rotationY?: number;
  /** Name of the head bone/node, when auto-detection picks the wrong one. */
  headBone?: string;
  /** GLB rig bone names for the rest pose and idle (defaults: Rocketbox Biped). */
  bones?: Partial<GlbBoneMap>;
  /** How far below the head bone the camera aims (m); smaller = more headroom. */
  framingDrop?: number;
}

export interface AvatarCharacter {
  kind: 'vrm' | 'glb';
  /** Scene root of the model. */
  root: THREE.Object3D;
  /** Set for VRM characters only. */
  vrm: VRM | null;
  /** Set for GLB characters that carry ARKit blendshapes. */
  face: FaceDriver | null;
  /** Plays the model's idle clip, if the GLB has one. */
  mixer: THREE.AnimationMixer | null;
  /** Rig bone names (GLB only). */
  bones: GlbBoneMap | null;
  framingDrop: number;
  analyserNode: AnalyserNode | null;
  name: string;
  /** Head height in world units, measured once at load (rest pose). */
  headY: number;
}

/**
 * Split-screen framing: one camera per character, persona_a in the left
 * half and persona_b in the right half (top/bottom when the frame is portrait).
 */
const SPLIT_ORDER = ['persona_a', 'persona_b'] as const;
const SPLIT_FRAMING = {
  fov: 30,
  /** Camera distance in front of the character (m). */
  distance: 2.3,
  /** How far below the head the camera aims, so the shot is chest-up (m). */
  targetDrop: 0.2,
  /** Distance between the two characters in the shared scene (m). */
  spacing: 1.6,
  /** Inward turn so the two halves read as facing each other (rad). */
  inwardYaw: Math.PI / 12,
  fallbackHeadY: 1.35,
};
const STUDIO_BACKGROUND = 0x151821;
const STUDIO_SIGNS: Record<string, StudioSpot['sign']> = {
  persona_a: { text: 'ON AIR', color: '#ef4444', glow: '#f87171' },
  persona_b: { text: '103.9 HITS', color: '#f59e0b', glow: '#fbbf24' },
};
const RIM_COLORS: Record<string, number> = {
  persona_a: 0x2dd4bf,
  persona_b: 0xf472b6,
};

/** Render layer of a presenter: each camera draws the studio (layer 0) plus its own presenter only. */
const layerOf = (personaId: string) => SPLIT_ORDER.indexOf(personaId as (typeof SPLIT_ORDER)[number]) + 1;

export class SceneManager {
  scene: THREE.Scene;
  cameras: Map<string, THREE.PerspectiveCamera>;
  renderer: THREE.WebGLRenderer;
  clock: THREE.Clock;
  characters: Map<string, AvatarCharacter>;
  private studio: StudioSet | null = null;
  private environment: THREE.Texture | null = null;
  private keyLight!: THREE.DirectionalLight;

  constructor(container: HTMLElement) {
    this.scene = new THREE.Scene();
    this.cameras = new Map(
      SPLIT_ORDER.map((id) => {
        const camera = new THREE.PerspectiveCamera(SPLIT_FRAMING.fov, 1, 0.1, 100);
        camera.layers.enable(layerOf(id));
        return [id, camera];
      })
    );

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true
    });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    // Filmic response keeps skin highlights from clipping on PBR characters
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;

    container.appendChild(this.renderer.domElement);

    this.clock = new THREE.Clock();
    this.characters = new Map();

    this.setupEnvironment();
    this.setupLights();
    this.scene.background = new THREE.Color(STUDIO_BACKGROUND);
    this.updateLayout(container);

    this.onWindowResize = () => this.updateLayout(container);
    window.addEventListener('resize', this.onWindowResize);
  }

  private onWindowResize: () => void;

  /** Image-based lighting for PBR materials (skin, metal, fabric). */
  private setupEnvironment() {
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const room = new RoomEnvironment();
    this.environment = pmrem.fromScene(room, 0.04).texture;
    room.dispose();
    pmrem.dispose();
    this.scene.environment = this.environment;
    this.scene.environmentIntensity = 0.55;
  }

  setupLights() {
    // Warm key light from the front, the only shadow caster
    const keyLight = new THREE.DirectionalLight(0xfff1e0, 1.6);
    keyLight.position.set(0.8, 2.8, 2.6);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 1024;
    keyLight.shadow.mapSize.height = 1024;
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 10;
    keyLight.shadow.camera.left = -2.5;
    keyLight.shadow.camera.right = 2.5;
    keyLight.shadow.camera.top = 2.5;
    keyLight.shadow.camera.bottom = -1;
    keyLight.shadow.bias = -0.0005;
    // Presenters live on their own layers; the shadow pass must still see them
    keyLight.shadow.camera.layers.enableAll();
    this.scene.add(keyLight);
    this.keyLight = keyLight;

    // Soft cool fill from the other side
    const fillLight = new THREE.DirectionalLight(0xdbeafe, 0.5);
    fillLight.position.set(-2, 1.5, 1.8);
    this.scene.add(fillLight);

    // Low ambient: the studio is darker than the old light background
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.25));
  }

  /** Whether the frame is split left/right (landscape) or top/bottom (portrait). */
  private isPortrait(): boolean {
    const size = this.renderer.getSize(new THREE.Vector2());
    return size.x < size.y;
  }

  private presenterX(personaId: string): number {
    return (layerOf(personaId) === 1 ? -1 : 1) * SPLIT_FRAMING.spacing / 2;
  }

  updateLayout(container?: HTMLElement) {
    const parent = container || (this.renderer.domElement.parentElement as HTMLElement | null);
    const width = parent?.clientWidth || window.innerWidth;
    const height = parent?.clientHeight || window.innerHeight;
    this.renderer.setSize(width, height);

    const portrait = width < height;
    const halfAspect = portrait ? width / (height / 2) : (width / 2) / height;

    SPLIT_ORDER.forEach((personaId) => {
      const x = this.presenterX(personaId);
      const char = this.characters.get(personaId);
      const headY = char?.headY ?? SPLIT_FRAMING.fallbackHeadY;
      if (char) char.root.position.x = x;

      const camera = this.cameras.get(personaId)!;
      const targetY = headY - (char?.framingDrop ?? SPLIT_FRAMING.targetDrop);
      camera.fov = SPLIT_FRAMING.fov;
      camera.aspect = halfAspect;
      camera.position.set(x, targetY + 0.03, SPLIT_FRAMING.distance);
      camera.lookAt(x, targetY, 0);
      camera.updateProjectionMatrix();
    });
  }

  /**
   * Build the radio studio around the loaded presenters. Call once after
   * loadCharacter() so desks and microphones match each head height.
   */
  buildStudio() {
    this.studio?.dispose();
    const spots: StudioSpot[] = SPLIT_ORDER.map((personaId) => ({
      personaId,
      x: this.presenterX(personaId),
      headY: this.characters.get(personaId)?.headY ?? SPLIT_FRAMING.fallbackHeadY,
      outerSide: layerOf(personaId) === 1 ? -1 : 1,
      sign: STUDIO_SIGNS[personaId],
    }));
    this.studio = new StudioSet(spots);
    for (const spot of spots) {
      // Colored rim light behind each presenter for separation from the wall
      const rim = new THREE.PointLight(RIM_COLORS[spot.personaId], 1.4, 2.0, 2);
      rim.position.set(spot.x - spot.outerSide * 0.5, spot.headY + 0.35, -0.7);
      this.studio.group.add(rim);
    }
    this.scene.add(this.studio.group);
  }

  async loadCharacter(personaId: string, spec: CharacterSpec): Promise<void> {
    const loader = new GLTFLoader();
    if (spec.kind === 'vrm') loader.register((parser) => new VRMLoaderPlugin(parser));

    const gltf = await new Promise<any>((resolve, reject) => {
      loader.load(
        spec.url,
        resolve,
        (progress) => {
          if (progress.total) console.log(`Loading ${spec.name}: ${(progress.loaded / progress.total * 100).toFixed(0)}%`);
        },
        (error) => {
          console.error(`Failed to load ${spec.name}:`, error);
          reject(error);
        }
      );
    });

    const character = spec.kind === 'vrm'
      ? this.setupVrm(gltf, spec)
      : this.setupGlb(gltf, spec);

    const root = character.root;
    root.position.set(this.presenterX(personaId), 0, 0);
    // Turn characters slightly toward each other (across the split)
    root.rotation.y += (root.position.x < 0 ? 1 : -1) * SPLIT_FRAMING.inwardYaw;
    if (spec.framingDrop !== undefined) character.framingDrop = spec.framingDrop;

    // GLB rigs come in a T/A-pose: put the arms down with hands on the desk
    if (character.bones && !character.mixer && !applyGlbRestPose(root, character.bones)) {
      console.warn(`[SceneManager] ${spec.name}: rest pose skipped, arm bones not found`);
    }

    root.traverse((obj) => {
      obj.layers.set(layerOf(personaId));
      if ((obj as THREE.Mesh).isMesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
      }
    });

    this.scene.add(root);
    this.characters.set(personaId, character);
    this.updateLayout();

    console.log(`✓ Loaded character: ${spec.name} (${personaId}, ${spec.kind})` +
      (character.face ? ` – ${character.face.describe()}` : ''));
  }

  private setupVrm(gltf: any, spec: CharacterSpec): AvatarCharacter {
    const vrm = gltf.userData.vrm as VRM | undefined;
    if (!vrm) throw new Error(`No VRM data found in ${spec.url}`);

    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.removeUnnecessaryJoints(gltf.scene);
    VRMUtils.rotateVRM0(vrm);
    if (spec.rotationY) vrm.scene.rotation.y += spec.rotationY;

    // Measure head height once in rest pose to frame the camera
    vrm.scene.updateMatrixWorld(true);
    const headNode = vrm.humanoid?.getNormalizedBoneNode('head');
    const headY = headNode
      ? headNode.getWorldPosition(new THREE.Vector3()).y
      : SPLIT_FRAMING.fallbackHeadY;

    return {
      kind: 'vrm', root: vrm.scene, vrm, face: null, mixer: null, bones: null,
      framingDrop: SPLIT_FRAMING.targetDrop, analyserNode: null, name: spec.name, headY,
    };
  }

  private setupGlb(gltf: any, spec: CharacterSpec): AvatarCharacter {
    const root: THREE.Object3D = gltf.scene;
    if (spec.scale) root.scale.setScalar(spec.scale);
    if (spec.rotationY) root.rotation.y += spec.rotationY;
    root.updateMatrixWorld(true);

    // Hair cards and eyelashes come as alpha-blended materials; cut them out
    // instead, so they depth-sort correctly and render on both sides.
    root.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        if (mat.transparent) {
          mat.transparent = false;
          mat.alphaTest = 0.5;
          mat.side = THREE.DoubleSide;
        }
      }
    });

    const face = new FaceDriver(root);
    if (!face.hasArkit) {
      console.warn(`[SceneManager] ${spec.name}: no ARKit blendshapes found; the face will not animate.`);
    } else if (face.missing.length) {
      console.warn(`[SceneManager] ${spec.name}: missing ARKit blendshapes: ${face.missing.join(', ')}`);
    }

    // Play an idle clip if the file has one, so the body is not frozen in bind pose
    let mixer: THREE.AnimationMixer | null = null;
    const clips: THREE.AnimationClip[] = gltf.animations ?? [];
    const idle = clips.find((c) => /idle|breath/i.test(c.name)) ?? null;
    if (idle) {
      mixer = new THREE.AnimationMixer(root);
      mixer.clipAction(idle).play();
    }

    return {
      kind: 'glb', root, vrm: null, face: face.hasArkit ? face : null, mixer,
      bones: { ...ROCKETBOX_BONES, ...spec.bones },
      framingDrop: SPLIT_FRAMING.targetDrop, analyserNode: null, name: spec.name,
      headY: this.findHeadY(root, spec),
    };
  }

  /** Head height of a GLB: named bone, then any node ending in "head", then the model top. */
  private findHeadY(root: THREE.Object3D, spec: CharacterSpec): number {
    let head: THREE.Object3D | undefined;
    if (spec.headBone) head = root.getObjectByName(spec.headBone);
    if (!head) {
      root.traverse((obj) => {
        if (!head && /(^|[^a-z])head$/i.test(obj.name) && !/top|end/i.test(obj.name)) head = obj;
      });
    }
    if (head) return head.getWorldPosition(new THREE.Vector3()).y;
    const box = new THREE.Box3().setFromObject(root);
    return Number.isFinite(box.max.y) ? box.max.y - 0.12 : SPLIT_FRAMING.fallbackHeadY;
  }

  update(deltaTime?: number) {
    const dt = deltaTime !== undefined ? deltaTime : this.clock.getDelta();
    this.characters.forEach((character) => {
      character.vrm?.update(dt);
      character.mixer?.update(dt);
    });
  }

  render() {
    const size = this.renderer.getSize(new THREE.Vector2());
    const portrait = this.isPortrait();
    const halfW = portrait ? size.x : Math.floor(size.x / 2);
    const halfH = portrait ? Math.floor(size.y / 2) : size.y;

    this.renderer.setScissorTest(true);
    SPLIT_ORDER.forEach((personaId, i) => {
      // WebGL viewport origin is bottom-left: first half is left, or top in portrait.
      const x = portrait ? 0 : i * halfW;
      const y = portrait ? (i === 0 ? size.y - halfH : 0) : 0;
      const w = portrait ? size.x : (i === 0 ? halfW : size.x - halfW);
      const h = portrait ? (i === 0 ? halfH : size.y - halfH) : size.y;
      this.renderer.setViewport(x, y, w, h);
      this.renderer.setScissor(x, y, w, h);
      this.renderer.render(this.scene, this.cameras.get(personaId)!);
    });
    this.renderer.setScissorTest(false);
  }

  onResize(container: HTMLElement) {
    this.updateLayout(container);
  }

  setQuality(quality: 'low' | 'medium' | 'high') {
    switch (quality) {
      case 'low':
        this.renderer.setPixelRatio(0.75);
        this.renderer.shadowMap.enabled = false;
        break;
      case 'medium':
        this.renderer.setPixelRatio(1);
        this.renderer.shadowMap.enabled = true;
        break;
      case 'high':
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        break;
    }
    this.keyLight.castShadow = this.renderer.shadowMap.enabled;
  }

  dispose() {
    window.removeEventListener('resize', this.onWindowResize);
    this.renderer.domElement.remove();
    this.studio?.dispose();
    this.environment?.dispose();
    this.renderer.dispose();
    this.characters.forEach((character) => {
      character.root.traverse((obj) => {
        if ((obj as THREE.Mesh).isMesh) {
          const mesh = obj as THREE.Mesh;
          mesh.geometry.dispose();
          if (Array.isArray(mesh.material)) {
            mesh.material.forEach(mat => mat.dispose());
          } else {
            mesh.material.dispose();
          }
        }
      });
    });
  }
}
