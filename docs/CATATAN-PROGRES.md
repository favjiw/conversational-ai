# Catatan Progres Proyek Penyiar AI HITS

Ringkasan perubahan sejak 14 Okt 2026, untuk melanjutkan pekerjaan di sesi chat lain. Acuan desain tetap `docs/KEPUTUSAN-DESAIN.md` (dibaca otomatis lewat `CLAUDE.md`). Dokumen ini hanya mencatat status dan konteks kerja.

Terakhir diperbarui: 20 Okt 2026.

---

## 1. Status singkat

- **Branch aktif: `stage-portrait`**, dibuat dari `main` setelah PR #4. Isinya **belum di-commit**:
  - Tahap 1 (layout 9:16)
  - dua gaya karakter
  - TTS ElevenLabs
  - Tahap 2 (HUD 9:16)
  - skrip rekam demo
- **Sudah di-merge ke `main`:**
  - PR #1/#2: peran WebSocket console vs stage
  - PR #3: rekaman stasiun, persiapan lagu di belakang layar, rundown 1 jam
  - PR #4: avatar realistis dan lip-sync viseme
- **Tes:** backend 96 tes lulus (`cd backend && python -m unittest discover -s tests`). Frontend: type check, `vite build`, dan `oxlint src/stage` bersih.
- **Demo untuk pembimbing** sudah direkam di `demo-recordings/` (di-gitignore):
  - `demo-3d-realistic.mp4` (5 menit)
  - `demo-animation.mp4` (2 menit 22 detik)

## 2. Cara menjalankan

```bash
cd backend && python -m uvicorn app.main:app --port 8000
cd frontend && npx vite --port 3000
```

Konfigurasi preview juga ada di `.claude/launch.json` (`backend`, `backend-mock`, `frontend`).

| Halaman | Fungsi |
|---|---|
| `http://localhost:3000/` | Konsol operator: pilih mode, mulai/hentikan live, transkrip, rundown |
| `/stage-3d-realistic` | Output live gaya realistis (Rocketbox GLB) |
| `/stage-animation` | Output live gaya animasi/VTuber (VRM) |
| `/stage` | Gaya default dari `avatar.config.json` (`?style=animation` untuk mengganti) |
| `?clean=1` | Tampilan bersih untuk ditangkap TikTok LIVE Studio/OBS |
| `?zones=1` | Overlay zona aman TikTok dan penanda posisi wajah |
| `?mode=debug` | Lab avatar: toolbar, lil-gui, FPS, slider ARKit, input "Ucapkan" teks |

**Rekam demo**

Syarat: backend dan frontend jalan, dan tidak ada tab `/stage` lain yang terbuka.

```bash
python frontend/scripts/record_demo.py --style realistic --minutes 5 --out demo-recordings/demo.mp4
```

Butuh `pip install playwright imageio-ffmpeg` dan Google Chrome terpasang. Chromium unduhan Playwright diblokir di laptop ini, jadi skrip memakai `--channel chrome`.

## 3. Konfigurasi penting

- **Dua file `.env`** (keduanya di-gitignore):
  - `.env` di root;
  - `backend/.env`, **dibaca terakhir dan menimpa root**.

  Ubah keduanya bila mengganti pengaturan.
- **TTS sekarang `TTS_PROVIDER=elevenlabs`** (model `eleven_flash_v2_5`).
  - Voice persona: Raka `JBFqnCBsd6RMkjVDRZzb` (George), Salsa `EXAVITQu4vr4xnSDxMaL` (Sarah).
  - `ELEVENLABS_VOICE_A=kLhAs…` di `.env` butuh paket berbayar (402), jadi otomatis jatuh ke George.
  - Key ElevenLabs dibatasi (tidak bisa membaca kuota atau voice).
  - **Key sempat ditulis di chat; rotasi key di dashboard ElevenLabs, lalu perbarui kedua `.env`.**
- `frontend/public/avatar.config.json` berisi:
  - `defaultStyle`, `styles` (realistic dan animation: karakter dan tone mapping);
  - `program` (judul, stasiun, `pinnedQuestion`);
  - `layout` (urutan panel dan framing, opsional);
  - parameter `lipsync`, `expression`, `idle`, `viseme`, `glbFace`.
- Rekaman stasiun (jingle, bumper, taping) ada di `backend/data/station_audio/`. `*.mp3` tidak di-commit; daftar nama filenya ada di README di folder itu.
- Laptop streaming: MX250 2 GB. Chrome dan OBS default memakai Intel UHD 620, jadi set ke "High performance" di Windows Graphics settings.

## 4. Arsitektur yang sudah ada

**Backend (FastAPI)**
- `main.py`
  - WebSocket `/ws/session?role=console|stage` dengan satu pemutar audio (Stage tertua), event `output_status` dan `speaking`.
  - Status live tetap benar setelah reload (`live_state()`).
  - Endpoint `/api/tts/line`, `/station-audio/{file}`, `/api/clock/start|stop|next`, `/api/session/start|stop`.
- `orchestrator/clock_runner.py`
  - Rundown 42 slot (`clock-pagi-bener-live-1jam.json`, sesuai `docs/RUNDOWN-LIVE-1-JAM-DRAF.md`).
  - Slot `static_audio` memutar rekaman; tanpa file, slot dilewati.
  - Lagu disiapkan satu slot di depan (Deezer, intro dan backsell LLM, TTS secara paralel).
  - Event `turn` membawa `word_timings`.
- `tts/provider.py`
  - `synthesize_with_timings`: Edge (`WordBoundary`) dan ElevenLabs (`/with-timestamps`, alignment karakter dikelompokkan per kata).
  - Cache untuk timing.
  - Breaker ElevenLabs: setelah 401/402/403, berhenti mencoba.
- Tema library: `app/data/tema/pagi_bener.json`, dengan kunci = ID slot. Isinya masih contoh sementara.

**Frontend `/stage` (`frontend/src/stage/`)**
- `scene/SceneManager.ts`
  - Kanvas tetap 1080×1920, dua viewport scissor (atas dan bawah).
  - Kamera dihitung dari target letak wajah (`faceAt`).
  - Render layer per karakter.
  - `projectFace()` untuk overlay zona aman.
- `layout/stageLayout.ts`: zona aman TikTok, pita wajah, dan default framing (sumber tunggal angka layout).
- `scene/StudioSet.ts`: studio prosedural (busa, meja, mic, neon ON AIR).
- Karakter:
  - GLB: `face/FaceDriver.ts` (ARKit), `face/GlbFaceAnimator.ts` (viseme, emosi, kedip, saccade, tatapan dengar), `face/GlbRig.ts` (pose istirahat, napas, anggukan).
  - VRM: `expression/*`, `idle/*`, dan `lipsync/VrmVisemes.ts` (viseme ke 5 vokal VRM).
- Lip-sync:
  - `lipsync/IndonesianVisemes.ts`: teks ke viseme Oculus, ditempatkan dalam timing kata TTS.
  - `lipsync/VisemeLipSync.ts`: koartikulasi dan gating diam.
  - `LipSyncLevel1.ts`: amplitudo (cadangan).
- `live/LiveBroadcastAdapter.ts`
  - Event WS → audio, emosi, `onLineStart` (teks dan timing), `onTopicChange`.
  - Antrean giliran; audio ditahan bila diblokir autoplay.
- `components/PortraitHUD.tsx`: HUD 9:16.
  - Pil program dan badge AI di garis batas.
  - Label dan bingkai penyiar yang sedang bicara.
  - Pertanyaan pemancing.
  - Kartu Talk, Lagu, Lagu Berikutnya, dan cue di kolom kanan panel bawah.
- `components/SafeZoneOverlay.tsx`: overlay zona (`?zones=1`).
- Model:
  - `public/models/realistic/{raka,salsa}.glb`: Rocketbox, MIT, dibuat dengan `frontend/scripts/convert_rocketbox.py`;
  - `public/models/red-male.vrm` dan `female.vrm`.

  Lisensi tercatat di `docs/avatar/ASSETS.md`.

## 5. Keputusan yang diambil di sesi ini (sudah tercatat di KEPUTUSAN-DESAIN)

- 14 Okt: `/` adalah konsol operator, `/stage` adalah output siaran (satu pemutar audio).
- 15 Okt: rekaman stasiun diputar asli. LLM+TTS hanya untuk Talk, intro lagu, dan adlibs. Rundown mengikuti draf 1 jam.
- 15 Okt: karakter realistis GLB (Rocketbox) dan lip-sync viseme dari timing kata TTS.
- 17 Okt: layout **9:16 bertumpuk** (atas Raka, bawah Salsa) dengan zona aman TikTok, menggantikan split kiri-kanan.
- 19 Okt: **dua gaya karakter setara** (`/stage-3d-realistic`, `/stage-animation`), sepasang penyiar selalu bergaya sama.
- 20 Okt: TTS memakai ElevenLabs.
- Komentar TikTok sementara **diinput manual oleh operator** (belum dibuat).

## 6. Rencana bertahap `/stage` 9:16 (tugas yang sedang berjalan)

| Tahap | Status |
|---|---|
| 1. Layout dan zona aman, `?clean=1` | Selesai |
| 2. Overlay program (logo/AI di garis batas, pertanyaan pemancing, Talk/Lagu, penanda bicara) | Selesai |
| 3. Listening states: `attending_partner` (atas menunduk ke bawah, bawah melirik ke atas), `reading_comments`, `thinking`, `about_to_speak`, dengan transisi halus, untuk **kedua gaya** | **Belum** |
| 4. Sambungan Live Mode: `turn` → about_to_speak/attending; komentar operator (endpoint kecil + event `comment` lewat WS yang ada) → reading_comments; skenario JSON demo semua perilaku; kontrol pertanyaan pemancing dari operator | **Belum** |

Batasan dari Favian: jangan ubah logika LLM, rundown, prompt persona, lip-sync, atau pemetaan emosi kecuali untuk integrasi (jelaskan dulu). FPS sekitar 60. Berhenti di tiap tahap untuk dicek di browser.

## 7. Pertentangan dengan KEPUTUSAN-DESAIN yang belum dikerjakan

1. Tiga jenis segmen Talk (naskah tetap / improvisasi / roleplay) belum dibedakan, dan belum ada parsing Tema `.docx`.
2. Pipelining giliran Talk: giliran berikutnya baru dibuat setelah audio selesai (hanya lagu yang disiapkan lebih dulu).
3. TTS yang dipilih di keputusan adalah Gemini multi-speaker; yang dipakai sekarang ElevenLabs.
4. Belum ada:
   - pengambilan komentar TikTok;
   - Supervisor di jalur live;
   - musik berdasarkan emosi;
   - log latensi per tahap.
5. Isi Tema masih contoh. Pembagian peran 3M/SKEMA dan posisi Bumper Skema masih asumsi.

## 8. Catatan teknis dan jebakan

- Stage pertama yang tersambung menjadi pemutar audio. Tutup tab `/stage` lain saat siaran atau merekam.
- Jangan mengedit file frontend saat merekam, karena hot-reload Vite akan memuat ulang stage.
- Internet laptop kadang putus (DNS). Unduhan lagu di skrip rekam sudah memakai retry.
- R3 (Audio2Face-3D) tidak bisa jalan di MX250 (butuh GPU Ampere/Blackwell dan ≥3–4,4 GiB VRAM). Pilihan "Metode" lip-sync di panel debug sudah siap untuk metode ketiga.
- Gaya animasi: lengan VRM masih agak terbuka. Pose istirahat dengan tangan di meja baru ada untuk GLB.
- Frame rate rekaman demo sekitar 20 fps (screencast CDP pada 1080×1920), diekspor 30 fps.
- Frame rate live di Intel UHD 620 belum terukur langsung. Biaya render pada 1080×1920 sekitar 10 ms/frame (kualitas medium).

## 9. File baru dan berubah di branch `stage-portrait` (belum di-commit)

- Backend:
  - `app/tts/provider.py` (ElevenLabs dengan timing)
  - `tests/test_tts_elevenlabs.py`, `tests/test_song_prefetch.py`
- Frontend:
  - `src/main.jsx` (route gaya)
  - `src/stage/StageApp.tsx`, `StageApp.css`
  - `scene/SceneManager.ts`, `scene/StudioSet.ts`
  - `layout/stageLayout.ts`
  - `components/PortraitHUD.tsx`, `components/SafeZoneOverlay.tsx`, `components/DebugToolbar.tsx`
  - `live/LiveBroadcastAdapter.ts`, `scenario/ScenarioPlayer.ts`
  - `lipsync/VrmVisemes.ts`
  - `public/avatar.config.json`
  - `StageBroadcastHUD.tsx` dihapus
- Skrip: `frontend/scripts/record_demo.py`
- Dokumen: `docs/KEPUTUSAN-DESAIN.md` (§2.3, §7, §8), dokumen ini.
- `.gitignore` (`demo-recordings/`).
- Tidak di-commit dengan sengaja: 4 model VRM cadangan (`AliciaSolid`, `Seed-san`, `VRM1_Constraint_Twist_Sample`, `male`) dan `.claude/`.

## 10. Langkah berikutnya yang disarankan

1. Commit branch `stage-portrait` dan buat PR (Tahap 1–2, dua gaya, ElevenLabs, skrip rekam).
2. Tahap 3: listening states untuk GLB dan VRM.
3. Tahap 4: komentar operator → event `comment` → `reading_comments`, kontrol pertanyaan pemancing dari operator, dan skenario JSON demo.
4. Setelah itu, prioritas dari KEPUTUSAN-DESAIN: jenis segmen Talk dan parsing Tema, pipelining giliran, serta Supervisor.
