import type { VRM } from '@pixiv/three-vrm';
import { RestPose } from './RestPose';
import { MusicGroove, type GrooveConfig } from './MusicGroove';
import { TalkMotion, type TalkMotionConfig } from './TalkMotion';
import type { ExpressionAdapter } from '../expression/ExpressionAdapter';
import type { ExpressionDriver } from '../expression/ExpressionDriver';

export interface IdleConfig {
  blinkMinSec: number;
  blinkMaxSec: number;
  headSway: number;
  breath: number;
}

export class IdleManager {
  private vrm: VRM;
  private adapter: ExpressionAdapter;
  private expressionDriver?: ExpressionDriver;
  private config: IdleConfig;

  private blinkTimer = 0;
  private nextBlinkInterval = 3.0;
  private isBlinking = false;
  private blinkProgress = 0;
  private blinkDuration = 0.16;
  private pendingDoubleBlink = false;

  private breathPhase = 0;
  private breathSpeed = 1.4;

  private swayPhaseX = Math.random() * Math.PI * 2;
  private swayPhaseY = Math.random() * Math.PI * 2;
  private swayPhaseZ = Math.random() * Math.PI * 2;

  private saccadeTimer = 0;
  private nextSaccadeInterval = 2.0;
  private currentSaccadeYaw = 0;
  private currentSaccadePitch = 0;
  private targetSaccadeYaw = 0;
  private targetSaccadePitch = 0;

  public isSpeaking = false;

  /** Joget sederhana saat lagu diputar (lapisan di atas idle). */
  private groove: MusicGroove;
  /** Gerak ala VTuber saat bicara / mendengar (lapisan di atas idle). */
  private talk: TalkMotion;

  constructor(
    vrm: VRM,
    adapter: ExpressionAdapter,
    expressionDriver?: ExpressionDriver,
    config: IdleConfig = { blinkMinSec: 2, blinkMaxSec: 6, headSway: 0.3, breath: 0.4 }
  ) {
    this.vrm = vrm;
    this.adapter = adapter;
    this.expressionDriver = expressionDriver;
    this.config = config;

    // Fase acak kecil: dua penyiar bergerak di tempo yang sama tapi tidak identik.
    this.groove = new MusicGroove({}, Math.random() * 0.8);
    this.talk = new TalkMotion();

    this.scheduleNextBlink();
    this.scheduleNextSaccade();
    // Sudut lengan turun dihitung per model (pose A di female.vrm dengan sudut tetap).
    RestPose.calibrate(this.vrm);
    RestPose.apply(this.vrm);
  }

  /** Nyalakan/matikan joget (dipanggil saat audio lagu mulai/berhenti). */
  setMusicPlaying(playing: boolean): void {
    this.groove.active = playing;
  }

  setGrooveConfig(config: Partial<GrooveConfig>): void {
    this.groove.setConfig(config);
  }

  setTalkMotionConfig(config: Partial<TalkMotionConfig>): void {
    this.talk.setConfig(config);
  }

  getConfig(): IdleConfig {
    return this.config;
  }

  setConfig(newConfig: Partial<IdleConfig>): void {
    Object.assign(this.config, newConfig);
  }

  private scheduleNextBlink(): void {
    const range = Math.max(0.5, this.config.blinkMaxSec - this.config.blinkMinSec);
    this.nextBlinkInterval = this.config.blinkMinSec + Math.random() * range;
    this.blinkTimer = 0;
    this.isBlinking = false;
    this.blinkProgress = 0;
  }

  update(deltaTime: number): void {
    const humanoid = this.vrm.humanoid;
    if (!humanoid) return;

    RestPose.apply(this.vrm);
    // Tulang badan/kepala hanya ditulis lapisan idle: mulai dari nol tiap frame supaya
    // tambahan gerakan joget tidak menumpuk antar-frame.
    for (const bone of ['spine', 'chest', 'upperChest', 'neck', 'head'] as const) {
      humanoid.getNormalizedBoneNode(bone)?.rotation.set(0, 0, 0);
    }
    this.updateBlinking(deltaTime);
    this.updateBreathing(deltaTime, humanoid);
    this.updateHeadSway(deltaTime, humanoid);
    this.updateSaccades(deltaTime, humanoid);
    this.talk.speaking = this.isSpeaking;
    this.talk.enabled = !this.groove.active;
    this.talk.update(deltaTime, this.vrm);
    this.groove.update(deltaTime, this.vrm);
  }

  private updateBlinking(deltaTime: number): void {
    if (!this.isBlinking) {
      this.blinkTimer += deltaTime;
      if (this.blinkTimer >= this.nextBlinkInterval) {
        this.isBlinking = true;
        this.blinkProgress = 0;
      }
    } else {
      this.blinkProgress += deltaTime / this.blinkDuration;
      let blinkWeight: number;

      if (this.blinkProgress <= 0.4) {
        blinkWeight = this.blinkProgress / 0.4;
      } else if (this.blinkProgress <= 1.0) {
        blinkWeight = 1.0 - (this.blinkProgress - 0.4) / 0.6;
      } else {
        blinkWeight = 0;
        this.isBlinking = false;
        if (!this.pendingDoubleBlink && Math.random() < 0.15) {
          this.pendingDoubleBlink = true;
          this.nextBlinkInterval = 0.12;
          this.blinkTimer = 0;
        } else {
          this.pendingDoubleBlink = false;
          this.scheduleNextBlink();
        }
      }
      this.adapter.setValue(this.vrm, 'blink', blinkWeight);
    }
  }

  private updateBreathing(deltaTime: number, humanoid: NonNullable<VRM['humanoid']>): void {
    if (this.config.breath <= 0) return;
    this.breathPhase += deltaTime * this.breathSpeed;
    const breathCycle = Math.sin(this.breathPhase);

    const isVRM0 = this.vrm.meta?.metaVersion === '0';
    const xSign = isVRM0 ? -1 : 1;
    const zSign = isVRM0 ? -1 : 1;

    const chest = humanoid.getNormalizedBoneNode('chest') || humanoid.getNormalizedBoneNode('spine');
    if (chest) {
      chest.rotation.x = breathCycle * 0.02 * this.config.breath * xSign;
    }

    const leftShoulder = humanoid.getNormalizedBoneNode('leftShoulder');
    const rightShoulder = humanoid.getNormalizedBoneNode('rightShoulder');
    const shoulderLift = breathCycle * 0.012 * this.config.breath * zSign;
    if (leftShoulder) leftShoulder.rotation.z = shoulderLift;
    if (rightShoulder) rightShoulder.rotation.z = -shoulderLift;
  }

  private updateHeadSway(deltaTime: number, humanoid: NonNullable<VRM['humanoid']>): void {
    if (this.config.headSway <= 0) return;
    const speed = this.isSpeaking ? 1.8 : 1.0;
    const strength = this.config.headSway * (this.isSpeaking ? 1.5 : 1.0);

    this.swayPhaseX += deltaTime * 0.8 * speed;
    this.swayPhaseY += deltaTime * 0.5 * speed;
    this.swayPhaseZ += deltaTime * 0.65 * speed;

    let pitch = (Math.sin(this.swayPhaseX) * 0.025 + Math.sin(this.swayPhaseX * 2.3) * 0.01) * strength;
    let yaw = (Math.sin(this.swayPhaseY) * 0.035 + Math.cos(this.swayPhaseY * 1.7) * 0.015) * strength;
    let roll = Math.sin(this.swayPhaseZ) * 0.02 * strength;

    if (this.isSpeaking) {
      pitch += Math.sin(this.swayPhaseX * 3.5) * 0.02 * strength;
    }

    if (this.expressionDriver) {
      pitch += this.expressionDriver.headPoseOffset.pitch;
      yaw += this.expressionDriver.headPoseOffset.yaw;
      roll += this.expressionDriver.headPoseOffset.roll;
    }

    const isVRM0 = this.vrm.meta?.metaVersion === '0';
    const xSign = isVRM0 ? -1 : 1;
    const zSign = isVRM0 ? -1 : 1;

    const neck = humanoid.getNormalizedBoneNode('neck');
    const head = humanoid.getNormalizedBoneNode('head');
    if (neck) {
      neck.rotation.x = pitch * 0.4 * xSign;
      neck.rotation.y = yaw * 0.4;
      neck.rotation.z = roll * 0.4 * zSign;
    }
    if (head) {
      head.rotation.x = pitch * 0.6 * xSign;
      head.rotation.y = yaw * 0.6;
      head.rotation.z = roll * 0.6 * zSign;
    }
  }

  private updateSaccades(deltaTime: number, humanoid: NonNullable<VRM['humanoid']>): void {
    this.saccadeTimer += deltaTime;
    if (this.saccadeTimer >= this.nextSaccadeInterval) {
      this.scheduleNextSaccade();
    }

    const step = Math.min(1.0, deltaTime * 12.0);
    this.currentSaccadeYaw += (this.targetSaccadeYaw - this.currentSaccadeYaw) * step;
    this.currentSaccadePitch += (this.targetSaccadePitch - this.currentSaccadePitch) * step;

    const isVRM0 = this.vrm.meta?.metaVersion === '0';
    const xSign = isVRM0 ? -1 : 1;

    const leftEye = humanoid.getNormalizedBoneNode('leftEye');
    const rightEye = humanoid.getNormalizedBoneNode('rightEye');
    if (leftEye && rightEye) {
      leftEye.rotation.y = this.currentSaccadeYaw;
      leftEye.rotation.x = this.currentSaccadePitch * xSign;
      rightEye.rotation.y = this.currentSaccadeYaw;
      rightEye.rotation.x = this.currentSaccadePitch * xSign;
    } else {
      if (this.currentSaccadeYaw > 0) {
        this.adapter.setValue(this.vrm, 'lookLeft', this.currentSaccadeYaw * 5);
        this.adapter.setValue(this.vrm, 'lookRight', 0);
      } else {
        this.adapter.setValue(this.vrm, 'lookRight', -this.currentSaccadeYaw * 5);
        this.adapter.setValue(this.vrm, 'lookLeft', 0);
      }
    }
  }

  private scheduleNextSaccade(): void {
    this.nextSaccadeInterval = 1.5 + Math.random() * 2.0;
    this.saccadeTimer = 0;
    this.targetSaccadeYaw = (Math.random() - 0.5) * 0.08;
    this.targetSaccadePitch = (Math.random() - 0.5) * 0.04;
  }
}
