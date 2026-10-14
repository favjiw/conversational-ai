import * as THREE from 'three';
import { VRM, VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

export interface AvatarCharacter {
  vrm: VRM;
  analyserNode: AnalyserNode | null;
  position: THREE.Vector3;
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
  distance: 2.05,
  /** How far below the head the camera aims, so the shot is chest-up (m). */
  targetDrop: 0.2,
  /** Distance between the two characters in the shared scene (m). */
  spacing: 1.6,
  /** Inward turn so the two halves read as facing each other (rad). */
  inwardYaw: Math.PI / 12,
  fallbackHeadY: 1.35,
};
const SPLIT_BACKGROUND: Record<string, number> = {
  persona_a: 0xeef3f1,
  persona_b: 0xf5eff1,
};

export class SceneManager {
  scene: THREE.Scene;
  cameras: Map<string, THREE.PerspectiveCamera>;
  renderer: THREE.WebGLRenderer;
  clock: THREE.Clock;
  characters: Map<string, AvatarCharacter>;
  
  constructor(container: HTMLElement) {
    this.scene = new THREE.Scene();
    this.cameras = new Map(
      SPLIT_ORDER.map((id) => [id, new THREE.PerspectiveCamera(SPLIT_FRAMING.fov, 1, 0.1, 100)])
    );
    
    this.renderer = new THREE.WebGLRenderer({ 
      antialias: true,
      alpha: true 
    });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    
    container.appendChild(this.renderer.domElement);
    
    this.clock = new THREE.Clock();
    this.characters = new Map();
    
    this.setupLights();
    this.setupBackground();
    this.updateLayout(container);
    
    this.onWindowResize = () => this.updateLayout(container);
    window.addEventListener('resize', this.onWindowResize);
  }

  private onWindowResize: () => void;
  
  setupLights() {
    // Key directional light (warm daylight)
    const mainLight = new THREE.DirectionalLight(0xffffff, 1.4);
    mainLight.position.set(1.5, 2.8, 2.2);
    mainLight.castShadow = true;
    mainLight.shadow.mapSize.width = 1024;
    mainLight.shadow.mapSize.height = 1024;
    mainLight.shadow.camera.near = 0.5;
    mainLight.shadow.camera.far = 10;
    mainLight.shadow.bias = -0.0005;
    this.scene.add(mainLight);
    
    // Fill light (soft cool white)
    const fillLight = new THREE.DirectionalLight(0xf1f5f9, 0.7);
    fillLight.position.set(-2, 1.5, 1.8);
    this.scene.add(fillLight);

    // Rim/Back light (crisp silhouette separation from light studio wall)
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.55);
    rimLight.position.set(0, 2.5, -2.2);
    this.scene.add(rimLight);
    
    // Ambient light for overall soft illumination in light theme
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    this.scene.add(ambientLight);
  }
  
  /** Shared background color, re-tinted per half while rendering. */
  private background = new THREE.Color(SPLIT_BACKGROUND.persona_a);

  setupBackground() {
    this.scene.background = this.background;
    
    // Studio ground shadow plane
    const groundGeometry = new THREE.PlaneGeometry(20, 20);
    const groundMaterial = new THREE.ShadowMaterial({ opacity: 0.1 });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = 0;
    ground.receiveShadow = true;
    this.scene.add(ground);
  }

  /** Whether the frame is split left/right (landscape) or top/bottom (portrait). */
  private isPortrait(): boolean {
    const size = this.renderer.getSize(new THREE.Vector2());
    return size.x < size.y;
  }

  updateLayout(container?: HTMLElement) {
    const parent = container || (this.renderer.domElement.parentElement as HTMLElement | null);
    const width = parent?.clientWidth || window.innerWidth;
    const height = parent?.clientHeight || window.innerHeight;
    this.renderer.setSize(width, height);

    const portrait = width < height;
    const halfAspect = portrait ? width / (height / 2) : (width / 2) / height;

    SPLIT_ORDER.forEach((personaId, i) => {
      const x = (i === 0 ? -1 : 1) * SPLIT_FRAMING.spacing / 2;
      const char = this.characters.get(personaId);
      const headY = char?.headY ?? SPLIT_FRAMING.fallbackHeadY;
      if (char?.vrm) char.vrm.scene.position.x = x;

      const camera = this.cameras.get(personaId)!;
      const targetY = headY - SPLIT_FRAMING.targetDrop;
      camera.fov = SPLIT_FRAMING.fov;
      camera.aspect = halfAspect;
      camera.position.set(x, targetY + 0.03, SPLIT_FRAMING.distance);
      camera.lookAt(x, targetY, 0);
      camera.updateProjectionMatrix();
    });
  }

  async loadCharacter(
    personaId: string, 
    modelPath: string, 
    position: THREE.Vector3,
    name: string
  ): Promise<void> {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    
    return new Promise((resolve, reject) => {
      loader.load(
        modelPath,
        (gltf) => {
          const vrm = gltf.userData.vrm as VRM;
          
          if (!vrm) {
            reject(new Error('No VRM data found in model'));
            return;
          }
          
          // Setup VRM
          VRMUtils.removeUnnecessaryVertices(gltf.scene);
          VRMUtils.removeUnnecessaryJoints(gltf.scene);
          VRMUtils.rotateVRM0(vrm);
          
          vrm.scene.position.copy(position);
          
          // Turn characters slightly toward each other (across the split)
          if (position.x < 0) {
            vrm.scene.rotation.y += SPLIT_FRAMING.inwardYaw; // left character looks right
          } else if (position.x > 0) {
            vrm.scene.rotation.y -= SPLIT_FRAMING.inwardYaw; // right character looks left
          }

          // Measure head height once in rest pose to frame the camera
          vrm.scene.updateMatrixWorld(true);
          const headNode = vrm.humanoid?.getNormalizedBoneNode('head');
          const headY = headNode
            ? headNode.getWorldPosition(new THREE.Vector3()).y
            : SPLIT_FRAMING.fallbackHeadY;
          
          // Enable shadows
          vrm.scene.traverse((obj) => {
            if ((obj as THREE.Mesh).isMesh) {
              obj.castShadow = true;
              obj.receiveShadow = true;
            }
          });
          
          this.scene.add(vrm.scene);
          
          this.characters.set(personaId, {
            vrm,
            analyserNode: null,
            position,
            name,
            headY,
          });
          
          this.updateLayout();

          console.log(`✓ Loaded character: ${name} (${personaId})`);
          resolve();
        },
        (progress) => {
          console.log(`Loading ${name}: ${(progress.loaded / progress.total * 100).toFixed(0)}%`);
        },
        (error) => {
          console.error(`Failed to load ${name}:`, error);
          reject(error);
        }
      );
    });
  }
  
  update(deltaTime?: number) {
    const dt = deltaTime !== undefined ? deltaTime : this.clock.getDelta();
    
    // Update each VRM
    this.characters.forEach((character) => {
      if (character.vrm) {
        character.vrm.update(dt);
      }
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
      this.background.setHex(SPLIT_BACKGROUND[personaId]);
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
  }
  
  dispose() {
    window.removeEventListener('resize', this.onWindowResize);
    this.renderer.domElement.remove();
    this.renderer.dispose();
    this.characters.forEach((character) => {
      character.vrm.scene.traverse((obj) => {
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
