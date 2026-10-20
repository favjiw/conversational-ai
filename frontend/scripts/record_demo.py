"""Record a demo of the live output (/stage) with sound, for review outside the app.

Video: Chrome DevTools screencast of a 1080x1920 page (frames come straight
from the compositor, independent of the window size).
Audio: tapped inside the page. Everything the stage plays through its
AudioContext (TTS turns) and same-origin media (jingles, bumpers) feeds a
MediaRecorder. Cross-origin song previews (Deezer) are logged with their start
time and mixed in afterwards from the downloaded preview.

The script starts the Clock Live rundown through the backend API, records for
a while, stops the rundown and writes an MP4 (H.264 + AAC).

Needs: backend on :8000 and frontend on :3000 running, and no other /stage
page open (the first stage to connect plays the audio).

    pip install playwright imageio-ffmpeg
    python frontend/scripts/record_demo.py --style realistic --minutes 5 --out demo-recordings/demo-3d-realistic.mp4
"""

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import imageio_ffmpeg
import websockets
from playwright.async_api import async_playwright

ROUTES = {"realistic": "/stage-3d-realistic", "animation": "/stage-animation"}
WIDTH, HEIGHT = 1080, 1920

# Installed before any page script: copies every sound the page plays to a tap.
AUDIO_TAP_JS = """
(() => {
  window.__tapEvents = [];
  const OrigAC = window.AudioContext;
  window.AudioContext = class extends OrigAC {
    constructor(...args) {
      super(...args);
      if (!window.__tapCtx) window.__tapCtx = this;
    }
  };
  const tapFor = (ctx) => (ctx.__tap ??= ctx.createMediaStreamDestination());
  window.__getTap = () => tapFor(window.__tapCtx ?? (window.__tapCtx = new window.AudioContext()));

  const connect = AudioNode.prototype.connect;
  AudioNode.prototype.connect = function (target, ...rest) {
    const out = connect.call(this, target, ...rest);
    if (target instanceof AudioDestinationNode) connect.call(this, tapFor(this.context));
    return out;
  };

  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    try {
      const url = new URL(this.currentSrc || this.src, location.href);
      if (url.origin === location.origin) {
        if (!this.__routed) {
          const ctx = window.__tapCtx ?? (window.__tapCtx = new window.AudioContext());
          ctx.createMediaElementSource(this).connect(ctx.destination);
          this.__routed = true;
        }
      } else {
        // Cross-origin (song previews): cannot be tapped without CORS; mixed in later
        window.__tapEvents.push({ url: url.href, t: Date.now() / 1000 });
      }
    } catch (e) { /* never break playback */ }
    return play.call(this);
  };
})();
"""

START_AUDIO_RECORDER_JS = """
async () => {
  await window.__tapCtx?.resume();
  const rec = new MediaRecorder(window.__getTap().stream, { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 160000 });
  rec.ondataavailable = async (e) => {
    if (!e.data.size) return;
    const bytes = new Uint8Array(await e.data.arrayBuffer());
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    await window.saveAudio(btoa(bin));
  };
  rec.onstop = () => window.audioDone();
  rec.start(1000);
  window.__recorder = rec;
  return Date.now() / 1000;
}
"""


def api(base: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        base + path, data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read())


async def connected_stages(backend: str) -> int:
    """How many /stage pages the backend sees (from a console-role greeting)."""
    url = backend.replace("http", "ws", 1) + "/ws/session?role=console"
    async with websockets.connect(url) as ws:
        for _ in range(5):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if msg["type"] == "output_status":
                return msg["data"]["clients"]["stage"]
    return -1


def build_mp4(work: Path, frames: list[tuple[float, Path]], audio: Path, audio_t0: float,
              songs: list[dict], song_sec: float, out: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    t0 = frames[0][0]

    # Variable-rate screencast frames -> concat list with real durations
    lines = []
    for (ts, path), (next_ts, _) in zip(frames, frames[1:] + [(frames[-1][0] + 1 / 30, None)]):
        lines += [f"file '{path.as_posix()}'", f"duration {max(next_ts - ts, 1 / 120):.4f}"]
    lines.append(f"file '{frames[-1][1].as_posix()}'")
    (work / "frames.txt").write_text("\n".join(lines), encoding="utf-8")

    inputs = ["-f", "concat", "-safe", "0", "-i", str(work / "frames.txt"), "-i", str(audio)]
    parts = []
    lead = audio_t0 - t0
    if lead >= 0:
        parts.append(f"[1:a]adelay={int(lead * 1000)}:all=1[a0]")
    else:
        parts.append(f"[1:a]atrim=start={-lead:.3f},asetpts=PTS-STARTPTS[a0]")
    mix = ["[a0]"]
    for i, song in enumerate(songs, start=2):
        inputs += ["-i", str(song["file"])]
        delay = max(0, int((song["t"] - t0) * 1000))
        parts.append(
            f"[{i}:a]atrim=0:{song_sec},afade=t=out:st={max(0, song_sec - 1.5)}:d=1.5,"
            f"volume=0.8,adelay={delay}:all=1[s{i}]"
        )
        mix.append(f"[s{i}]")
    parts.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first[aout]")
    parts.append(f"[0:v]scale={WIDTH}:{HEIGHT},setsar=1[vout]")

    subprocess.run([
        ffmpeg, "-y", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", "[vout]", "-map", "[aout]", "-fps_mode", "cfr", "-r", "30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out),
    ], check=True)


async def record(args) -> Path:
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="stage-rec-"))
    frames: list[tuple[float, Path]] = []
    audio_path = work / "audio.webm"
    audio_sink = audio_path.open("wb")
    audio_done = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            channel=args.channel or None,  # installed Chrome, fresh temporary profile
            args=["--autoplay-policy=no-user-gesture-required", "--ignore-gpu-blocklist", "--window-size=700,900"],
        )
        context = await browser.new_context(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
        await context.add_init_script(AUDIO_TAP_JS)
        page = await context.new_page()
        await page.expose_function("saveAudio", lambda b64: audio_sink.write(base64.b64decode(b64)))
        await page.expose_function("audioDone", lambda: audio_done.set())

        await page.goto(f"{args.frontend}{ROUTES[args.style]}?clean=1")
        await page.wait_for_selector(".canvas-container canvas")
        await page.wait_for_function("!document.querySelector('.overlay')", timeout=60_000)
        await page.wait_for_timeout(2000)

        stages = await connected_stages(args.backend)
        if stages != 1:
            raise SystemExit(f"Expected exactly 1 stage connected, found {stages}. Close other /stage tabs.")

        await page.mouse.click(100, 100)  # real input: unlocks audio playback
        cdp = await context.new_cdp_session(page)

        async def on_frame(ev):
            path = work / f"f_{len(frames):06d}.jpg"
            path.write_bytes(base64.b64decode(ev["data"]))
            frames.append((ev["metadata"]["timestamp"], path))
            await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

        cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
        await cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": 88, "maxWidth": WIDTH, "maxHeight": HEIGHT, "everyNthFrame": 1,
        })
        audio_t0 = await page.evaluate(START_AUDIO_RECORDER_JS)
        print(f"Recording {args.style}…", flush=True)

        await page.wait_for_timeout(1500)
        api(args.backend, "/api/clock/stop")  # clear any rundown left over from an earlier run
        await page.wait_for_timeout(500)
        print("Start rundown:", api(args.backend, "/api/clock/start", {"demo_music_sec": args.song_sec, "talk_turns_per_slot": 2}), flush=True)
        t_start = time.time()
        while time.time() - t_start < args.minutes * 60:
            await page.wait_for_timeout(10_000)
            elapsed = time.time() - t_start
            print(f"  {int(elapsed)} s, {len(frames)} frames (~{len(frames) / max(1, elapsed):.0f} fps)", flush=True)
        print("Stop rundown:", api(args.backend, "/api/clock/stop"), flush=True)
        await page.wait_for_timeout(1500)

        await cdp.send("Page.stopScreencast")
        await page.evaluate("window.__recorder.stop()")
        await asyncio.wait_for(audio_done.wait(), timeout=30)
        tap_events = await page.evaluate("window.__tapEvents")
        await page.wait_for_timeout(500)
        await browser.close()
    audio_sink.close()

    songs = []
    for i, ev in enumerate(tap_events):
        dest = work / f"song_{i}.mp3"
        for attempt in range(5):  # flaky DNS/Wi-Fi: retry before giving up on the music
            try:
                urllib.request.urlretrieve(ev["url"], dest)
                songs.append({"file": dest, "t": ev["t"]})
                break
            except Exception as e:  # a missing song only loses music, not the demo
                print(f"  song {i} attempt {attempt + 1} failed: {e}", flush=True)
                time.sleep(3 * (attempt + 1))

    print(f"Encoding {len(frames)} frames, {len(songs)} song(s)…", flush=True)
    build_mp4(work, frames, audio_path, audio_t0, songs, args.song_sec, out)
    shutil.rmtree(work, ignore_errors=True)
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--style", choices=ROUTES, default="realistic")
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--song-sec", type=int, default=20, help="Song preview length in the rundown")
    ap.add_argument("--out", default="demo-recordings/demo.mp4")
    ap.add_argument("--frontend", default="http://localhost:3000")
    ap.add_argument("--backend", default="http://localhost:8000")
    ap.add_argument("--channel", default="chrome", help='"chrome" (installed), "msedge", or "" for Playwright Chromium')
    asyncio.run(record(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
