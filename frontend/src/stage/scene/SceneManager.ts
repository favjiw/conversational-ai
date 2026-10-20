import * as THREE from 'three';
import { VRM, VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { FaceDriver } from '../face/FaceDriver';
import { StudioSet, type StudioSpot } from './StudioSet';
import { applyGlbRestPose, ROCKETBOX_BONES, type GlbBoneMap } from '../face/GlbRig';
import { CANVAS_HEIGHT, CANVAS_WIDTH, DEFAULT_LAYOUT, type StageLayoutConfig } from '../layout/stageLayout';

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
}

/** Renderer look per character style (avatar.config.json styles.<id>.render). */
export interface RenderStyle {
  /** "aces" suits PBR skin; "none" keeps anime (MToon) colors flat and saturated. */
  toneMapping?: 'aces' | 'neutral' | 'none';
  /** Strength of the image-based lighting. */
  environmentIntensity?: number;
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
  analyserNode: AnalyserNode | null;
  name: string;
  /** Head height in world units, measured once at load (rest pose). */
  headY: number;
}

/**
 * Stacked 9:16 framing: one camera per presenter, each rendered into its own
 * half of a fixed 1080x1920 canvas (see layout/stageLayout.ts). The two
 * presenters stand side by side in the shared scene; render layers keep each
 * camera to its own presenter plus the studio.
 */
const PERSONAS = ['persona_a', 'persona_b'] as const;
const SCENE = {
  /** Distance between the two presenters in the shared scene (m). */
  spacing: 1.6,
  /** Face centre above the head bone (the bone sits at the neck joint) (m). */
  faceAboveHeadBone: 0.08,
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
const layerOf = (personaId: string) => PERSONAS.indexOf(personaId as (typeof PERSONAS)[number]) + 1;

export class SceneManager {
  scene: THREE.Scene;
  cameras: Map<string, THREE.PerspectiveCamera>;
  renderer: THREE.WebGLRenderer;
  clock: THREE.Clock;
  characters: Map<string, AvatarCharacter>;
  private studio: StudioSet | null = null;
  private environment: THREE.Texture | null = null;
  private keyLight!: THREE.DirectionalLight;
  private layout: StageLayoutConfig;
  private renderScale = 1;

  constructor(container: HTMLElement, layout: StageLayoutConfig = DEFAULT_LAYOUT, renderStyle: RenderStyle = {}) {
    this.layout = layout;
    this.scene = new THREE.Scene();
    this.cameras = new Map(
      PERSONAS.map((id) => {
        const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
        camera.layers.enable(layerOf(id));
        return [id, camera];
      })
    );

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true
    });
    // Fixed broadcast resolution; CSS scales the canvas into the window (letterbox)
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(CANVAS_WIDTH, CANVAS_HEIGHT, false);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    // Filmic response keeps skin highlights from clipping on PBR characters
    this.renderer.toneMapping = {
      aces: THREE.ACESFilmicToneMapping,
      neutral: THREE.NeutralToneMapping,
      none: THREE.NoToneMapping,
    }[renderStyle.toneMapping ?? 'aces'];
    this.renderer.toneMappingExposure = 1.0;

    container.appendChild(this.renderer.domElement);

    this.clock = new THREE.Clock();
    this.characters = new Map();

    this.setupEnvironment(renderStyle.environmentIntensity ?? 0.55);
    this.setupLights();
    this.scene.background = new THREE.Color(STUDIO_BACKGROUND);
    this.updateLayout();
  }

  /** Image-based lighting for PBR materials (skin, metal, fabric). */
  private setupEnvironment(intensity: number) {
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const room = new RoomEnvironment();
    this.environment = pmrem.fromScene(room, 0.04).texture;
    room.dispose();
    pmrem.dispose();
    this.scene.environment = this.environment;
    this.scene.environmentIntensity = intensity;
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

  private presenterX(personaId: string): number {
    return (layerOf(personaId) === 1 ? -1 : 1) * SCENE.spacing / 2;
  }

  private faceY(personaId: string): number {
    return (this.characters.get(personaId)?.headY ?? SCENE.fallbackHeadY) + SCENE.faceAboveHeadBone;
  }

  /** Panel index (0 = top, 1 = bottom) a presenter is shown in. */
  panelOf(personaId: string): 0 | 1 {
    return this.layout.panels[0].persona === personaId ? 0 : 1;
  }

  /** Replace the panel layout (order or framing) at runtime. */
  setLayout(layout: StageLayoutConfig) {
    this.layout = layout;
    this.updateLayout();
  }

  /**
   * Where a presenter's face appears on the canvas, as fractions (0 - 1).
   * Used by the debug overlay to prove faces stay clear of the TikTok UI.
   */
  projectFace(personaId: string): { x: number; y: number } | null {
    const char = this.characters.get(personaId);
    if (!char) return null;
    const camera = this.cameras.get(personaId)!;
    const p = new THREE.Vector3(char.root.position.x, this.faceY(personaId), 0.1).project(camera);
    const panel = this.panelOf(personaId);
    return { x: (p.x + 1) / 2, y: panel * 0.5 + ((1 - p.y) / 2) * 0.5 };
  }

  /**
   * Aim each panel camera so the presenter's face lands at its target height
   * on the canvas (layout faceAt). Cameras stay level; the face position in
   * the panel comes from shifting the camera height.
   */
  updateLayout() {
    const panelAspect = CANVAS_WIDTH / (CANVAS_HEIGHT / 2);
    this.layout.panels.forEach((framing, panel) => {
      const personaId = framing.persona;
      const x = this.presenterX(personaId);
      const char = this.characters.get(personaId);
      if (char) char.root.position.x = x;

      // Face position inside this panel (0 = panel top) -> NDC y
      const inPanel = (framing.faceAt - panel * 0.5) / 0.5;
      const ndcY = 1 - 2 * inPanel;
      const halfHeight = framing.distance * Math.tan(THREE.MathUtils.degToRad(framing.fov / 2));
      const cameraY = this.faceY(personaId) - ndcY * halfHeight;

      const camera = this.cameras.get(personaId)!;
      camera.fov = framing.fov;
      camera.aspect = panelAspect;
      camera.position.set(x, cameraY, framing.distance);
      camera.lookAt(x, cameraY, 0);
      camera.updateProjectionMatrix();
    });
  }

  /**
   * Build the radio studio around the loaded presenters. Call once after
   * loadCharacter() so desks and microphones match each head height.
   */
  buildStudio() {
    this.studio?.dispose();
    const spots: StudioSpot[] = PERSONAS.map((personaId) => ({
      personaId,
      x: this.presenterX(personaId),
      headY: this.characters.get(personaId)?.headY ?? SCENE.fallbackHeadY,
      outerSide: layerOf(personaId) === 1 ? -1 : 1,
      // One sign, in the top panel: the bottom panel's top edge meets the program pill
      sign: this.layout.panels[0].persona === personaId ? STUDIO_SIGNS.persona_a : null,
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
    // Stacked panels: both presenters face their own camera straight on
    root.position.set(this.presenterX(personaId), 0, 0);

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
      : SCENE.fallbackHeadY;

    return {
      kind: 'vrm', root: vrm.scene, vrm, face: null, mixer: null, bones: null,
      analyserNode: null, name: spec.name, headY,
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
      analyserNode: null, name: spec.name,
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
    return Number.isFinite(box.max.y) ? box.max.y - 0.12 : SCENE.fallbackHeadY;
  }

  update(deltaTime?: number) {
    const dt = deltaTime !== undefined ? deltaTime : this.clock.getDelta();
    this.characters.forEach((character) => {
      character.vrm?.update(dt);
      character.mixer?.update(dt);
    });
  }

  render() {
    const w = CANVAS_WIDTH * this.renderScale;
    const half = Math.floor((CANVAS_HEIGHT * this.renderScale) / 2);
    this.renderer.setScissorTest(true);
    this.layout.panels.forEach((framing, panel) => {
      // WebGL viewport origin is bottom-left: panel 0 (top) sits at y = half
      const y = panel === 0 ? half : 0;
      this.renderer.setViewport(0, y, w, half);
      this.renderer.setScissor(0, y, w, half);
      this.renderer.render(this.scene, this.cameras.get(framing.persona)!);
    });
    this.renderer.setScissorTest(false);
  }

  /** Quality presets scale the internal resolution (CSS keeps the display size) and toggle shadows. */
  setQuality(quality: 'low' | 'medium' | 'high') {
    this.renderScale = quality === 'low' ? 0.75 : 1;
    this.renderer.setPixelRatio(this.renderScale);
    this.renderer.setSize(CANVAS_WIDTH, CANVAS_HEIGHT, false);
    this.renderer.shadowMap.enabled = quality !== 'low';
    this.keyLight.castShadow = this.renderer.shadowMap.enabled;
  }

  dispose() {
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
