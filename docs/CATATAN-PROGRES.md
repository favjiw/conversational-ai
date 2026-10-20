# Catatan Progres Proyek Penyiar AI HITS

Ringkasan perubahan sejak 14 Okt 2026, untuk melanjutkan pekerjaan di sesi chat lain. Acuan desain tetap `docs/KEPUTUSAN-DESAIN.md` (dibaca otomatis lewat `CLAUDE.md`). Dokumen ini hanya mencatat status dan konteks kerja.

Terakhir diperbarui: 20 Okt 2026.

---

## 1. Status singkat

- **Branch aktif: `song-recommender`**, dibuat dari `stage-portrait`. Isinya integrasi rekomendasi lagu (§11), **belum di-commit**.
- **PR #5 (`stage-portrait`)** menunggu review/merge:
  - Tahap 1 (layout 9:16)
  - dua gaya karakter
  - TTS ElevenLabs
  - Tahap 2 (HUD 9:16)
  - skrip rekam demo
- **Sudah di-merge ke `main`:**
  - PR #1/#2: peran WebSocket console vs stage
  - PR #3: rekaman stasiun, persiapan lagu di belakang layar, rundown 1 jam
  - PR #4: avatar realistis dan lip-sync viseme
- **Tes:** backend 149 tes lulus (`cd backend && python -m unittest discover -s tests`). `test_compute_factor_drift_stable` kadang gagal karena `np.random` tanpa seed (bawaan, tidak terkait). Frontend: type check, `vite build`, dan `oxlint src/stage` bersih.
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
  - Paket **Starter** (20 Okt), sehingga voice dari Voice Library bisa dipakai.
  - Voice persona (suara Indonesia, dipilih Favian 20 Okt): Raka `q8qwd1jY2jS3AWOBeq25` (Pratama), Salsa `I7sakys8pBZ1Z5f0UhT9` (Putri Maharani), lewat `ELEVENLABS_VOICE_A/B` di kedua `.env`.
  - Rundown memakai voice dari `.env`. Field `voice` di `app/data/persona/*.json` diabaikan saat `/api/clock/start`.
  - Panggilan pertama tiap voice setelah backend start ±15 s (voice dimuat); berikutnya ±1,6 s.
  - Sampel kandidat suara ada di `demo-recordings/voice-samples/` (di-gitignore).
  - Key ElevenLabs dibatasi (hanya TTS; tidak bisa membaca kuota atau voice).
  - **Key ElevenLabs dan Groq sempat ditulis di chat; rotasi key di dashboard masing-masing, lalu perbarui kedua `.env`.**
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
- Komentar TikTok sementara **diinput manual oleh operator**: `POST /api/comments` + panel "Komentar Penonton" di konsol (20 Okt, lihat §11).

## 6. Rencana bertahap `/stage` 9:16 (tugas yang sedang berjalan)

| Tahap | Status |
|---|---|
| 1. Layout dan zona aman, `?clean=1` | Selesai |
| 2. Overlay program (logo/AI di garis batas, pertanyaan pemancing, Talk/Lagu, penanda bicara) | Selesai |
| 3. Listening states: `attending_partner` (atas menunduk ke bawah, bawah melirik ke atas), `reading_comments`, `thinking`, `about_to_speak`, dengan transisi halus, untuk **kedua gaya** | **Belum** |
| 4. Sambungan Live Mode: `turn` → about_to_speak/attending; komentar operator (endpoint kecil + event `comment` lewat WS yang ada) → reading_comments; skenario JSON demo semua perilaku; kontrol pertanyaan pemancing dari operator | **Belum**. Endpoint `POST /api/comments` dan event WS `comment` sudah ada (§11); tinggal dipakai stage untuk `reading_comments`. |

Batasan dari Favian: jangan ubah logika LLM, rundown, prompt persona, lip-sync, atau pemetaan emosi kecuali untuk integrasi (jelaskan dulu). FPS sekitar 60. Berhenti di tiap tahap untuk dicek di browser.

## 7. Pertentangan dengan KEPUTUSAN-DESAIN yang belum dikerjakan

1. Tiga jenis segmen Talk (naskah tetap / improvisasi / roleplay) belum dibedakan, dan belum ada parsing Tema `.docx`.
2. Pipelining giliran Talk: giliran berikutnya baru dibuat setelah audio selesai (hanya lagu yang disiapkan lebih dulu).
3. TTS yang dipilih di keputusan adalah Gemini multi-speaker; yang dipakai sekarang ElevenLabs.
4. Belum ada:
   - pengambilan komentar TikTok otomatis (sekarang input manual operator, §11);
   - Supervisor di jalur live (komentar baru dimoderasi oleh LLM rekomendasi, bukan Supervisor);
   - musik berdasarkan emosi **sebagian**: mood/request dari komentar sudah jalan; mood topik Talk ada di belakang flag `RECOMMENDER_TALK_MOOD` karena §9 belum diputuskan;
   - log latensi per tahap **sebagian**: rekomendasi lagu + Deezer sudah dicatat (`logs/{session_id}.music.jsonl`); LLM persona, Supervisor, dan TTS per giliran belum.
5. Isi Tema masih contoh. Pembagian peran 3M/SKEMA dan posisi Bumper Skema masih asumsi.

## 8. Catatan teknis dan jebakan

- Stage pertama yang tersambung menjadi pemutar audio. Tutup tab `/stage` lain saat siaran atau merekam.
- Jangan mengedit file frontend saat merekam, karena hot-reload Vite akan memuat ulang stage.
- Internet laptop kadang putus (DNS). Unduhan lagu di skrip rekam sudah memakai retry.
- R3 (Audio2Face-3D) tidak bisa jalan di MX250 (butuh GPU Ampere/Blackwell dan ≥3–4,4 GiB VRAM). Pilihan "Metode" lip-sync di panel debug sudah siap untuk metode ketiga.
- Gaya animasi: lengan VRM masih agak terbuka. Pose istirahat dengan tangan di meja baru ada untuk GLB.
- Frame rate rekaman demo sekitar 20 fps (screencast CDP pada 1080×1920), diekspor 30 fps.
- Frame rate live di Intel UHD 620 belum terukur langsung. Biaya render pada 1080×1920 sekitar 10 ms/frame (kualitas medium).

## 9. File di PR #5 (`stage-portrait`)

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

1. Review dan merge PR #5 (`stage-portrait`), lalu PR `song-recommender` (§11).
2. Tahap 3: listening states untuk GLB dan VRM.
3. Tahap 4: komentar operator → event `comment` → `reading_comments`, kontrol pertanyaan pemancing dari operator, dan skenario JSON demo.
4. Setelah itu, prioritas dari KEPUTUSAN-DESAIN: jenis segmen Talk dan parsing Tema, pipelining giliran, serta Supervisor.

## 11. Integrasi rekomendasi lagu (branch `song-recommender`, 20 Okt)

Modul rekomendasi lagu buatan Iam (`ffromme/hits-song-recommender`, kredit di `docs/KREDIT.md`) disambungkan ke rundown. Komentar penonton yang meminta lagu (judul, artis, atau mood) diputar di slot lagu berikutnya, dan intro lagu menyebut username serta isi request-nya.

**Cara memasang (sekali)**

```bash
git submodule update --init
python -m pip install --no-deps -e external/hits-song-recommender
cd external/hits-song-recommender && python scripts/02_build_index.py   # indeks ChromaDB ke .cache/chroma
```

- Dependensi besar (torch CPU, sentence-transformers, chromadb) sudah ada di Python global 3.12 laptop ini. `pyproject.toml` rekan tidak mendeklarasikan dependensi, jadi `--no-deps` aman. Daftar lengkapnya ada di `requirements.txt` rekan.
- Unduhan pertama model embedding `intfloat/multilingual-e5-small` ±470 MB ke cache HuggingFace (drive C:).
- Jangan menjalankan `scripts/05_web.py` rekan bersamaan dengan backend, karena keduanya memakai port 8000.

**Konfigurasi** (`Settings`, `.env.example`, dan kedua `.env`)

| Variabel | Default | Arti |
|---|---|---|
| `RECOMMENDER_ENABLED` | `false` | Nyalakan modul. Mati juga otomatis bila `LLM_MODE=mock`, key kosong, atau paket belum terpasang. |
| `RECOMMENDER_LLM_API_KEY` | kosong | Key Groq (terpisah dari kuota Gemini persona). |
| `RECOMMENDER_LLM_BASE_URL` / `_MODEL` | Groq, `qwen/qwen3.8-27b` | API OpenAI-compatible. |
| `RECOMMENDER_LLM_REASONING_EFFORT` | kosong | Opsional (`low` = lebih cepat). |
| `RECOMMENDER_TIMEOUT_SEC` | `8` | Batas waktu satu rekomendasi; lewat dari itu dipakai fallback. |
| `RECOMMENDER_MAX_PENDING` | `5` | Maks request lagu yang menunggu, juga batas antrean klasifikasi. |
| `RECOMMENDER_TALK_MOOD` | `false` | Lagu dari mood topik Talk terakhir (KEPUTUSAN §9 belum diputuskan). |
| `RECOMMENDER_LLM_CACHE` | `false` | Cache jawaban LLM rekan. Mati agar latensi di log nyata. |

Konfigurasi preview `backend-rec` di `.claude/launch.json` menyalakan rekomendasi dengan TTS mock.

**Alur**

1. `POST /api/comments {username, text}` (maks 300 karakter) → `CommentQueue` (`backend/app/comments/queue.py`).
2. Klasifikasi satu per satu lewat `SongRecommenderService` (`backend/app/music/recommender.py`):
   - `explicit_song` / `mood_request` → status `waiting`;
   - bukan request → `general` (untuk Talk nanti);
   - moderasi → `rejected`, hanya console yang diberi tahu.
3. `ClockRunner._pick_track` memilih sumber lagu per slot:
   1. request yang menunggu (semua kategori kecuali `korea`);
   2. mood Talk (bila flag menyala);
   3. Deezer per kategori;
   4. fallback.
4. Audio lagu katalog dicari di Deezer (`artis judul`), lalu judul dan artis dicocokkan secara fuzzy. Bila tidak cocok, request ditandai `unavailable` dan request berikutnya dicoba.
5. Lagu dianggap diputar saat `clock_music` dikirim; saat itu request menjadi `played` dan masuk cooldown. Skip/stop sebelum on-air mengembalikan request ke antrean.

**Event WS**

- `comment`: ke semua klien; event ini juga yang nanti dipakai `/stage` untuk `reading_comments`.
- `comment_rejected`, `comment_queue`, `song_request_scheduled`: console saja.
- `clock_music.track` membawa field baru: `rec_source`, `requested_by`, `request_comment`, `host_line`, `reason`, `catalog_song_id`.

**Log**

`backend/logs/{session_id}.music.jsonl`: event `comment` (intent, lagu, `timings` hits_rec), `request_status`, `song_selected` (sumber, latensi rekomendasi, pencarian Deezer, total persiapan), dan `song_on_air`. Komentar di luar sesi live masuk `offair_YYYYMMDD.music.jsonl`.

**Uji**

- `python -m unittest tests.test_song_recommender tests.test_comments tests.test_song_sources`
- Ujung-ke-ujung: jalankan `backend-rec`, tutup tab `/stage`, lalu `python scripts/e2e_song_requests.py`.

**Jebakan**

- `import hits_rec` + `Recommender()` makan ±30–40 s, jadi dimuat di thread latar. Status tampil di `/health` dan panel konsol.
- Batas Groq gratis 8.000 token/menit (±3–4 rekomendasi/menit). Komentar beruntun bisa melewati batas waktu 8 s dan menjadi `general` tanpa moderasi (`moderated=false`). Stage sebaiknya hanya menampilkan komentar `moderated=true`.
- Klien OpenAI rekan (`max_retries=5, timeout=120`) diganti dari adapter (retry 1, timeout = `RECOMMENDER_TIMEOUT_SEC`), lewat atribut privat `hits_rec.llm._client`.
- `Recommender.recommend` langsung memanggil `history.add`. Adapter memakai `ReservingHistory`: `add` = pesan, `mark_played` = on-air, `release` = batal.
- Katalog: 102 lagu (43 id, 59 en, tanpa ko). Mood samar tanpa kata "lagu" kadang terbaca bukan request (masalah terbuka di repo rekan).
- Riwayat cooldown dan antrean hanya di memori; hilang saat backend restart.
- Kartu "Lagu Berikutnya" di `/stage` belum menampilkan request, karena data lagu baru sampai lewat `clock_music` setelah intro.

**Usulan PR ke repo rekan** (adapter sudah menanganinya, jadi tidak mendesak)

1. `history or PlayHistory()` → `if history is None`: riwayat kosong bernilai falsy dan diam-diam diganti objek baru (`pipeline.py`, `retrieval.py`).
2. `max_retries` dan `timeout` klien LLM bisa diatur lewat env.
3. Deklarasikan dependensi di `pyproject.toml` (sekarang hanya ada di `requirements.txt`).

**Hasil uji ujung-ke-ujung (20 Okt, `scripts/e2e_song_requests.py`)**

Backend `backend-rec` (Groq `qwen/qwen3.8-27b`, persona Gemini live, TTS mock), sesi `clock_6580740e`:

| Komentar | Hasil | Slot |
|---|---|---|
| @tulus_fans "puterin hati2 dijalan tulus" | eksplisit → Hati-Hati di Jalan — Tulus | s11 (indo_hits) |
| @genius_lover "req lathi weird genius" | tidak ada di katalog → Melompat Lebih Tinggi — Sheila on 7 | s12 (barat) |
| @anak_rantau "excited nungguin kakak pulang…" | mood → Sunflower — Post Malone | s14 (indo) |
| @telat_live "puterin hati hati di jalan lagi" | cooldown → Berdua Saja — Payung Teduh | s20 (indo) |
| @bandung_01 "halo kak salam dari bandung" | bukan request → komentar umum | - |
| @troll_99 (kasar) | ditolak moderasi | - |

- Slot lain (s22–s42, termasuk s29 korea) memakai Deezer per kategori.
- Latensi rekomendasi (hits_rec total): 1,2–3,4 s. Pencarian + pencocokan Deezer: 1,0–3,1 s.
- Persiapan lagu total 5–28 s, didominasi LLM intro/backsell persona. Semuanya disiapkan sebelum slotnya, jadi tidak terdengar sebagai jeda.
- Contoh intro request (Gemini): "Halo pisan nih buat tulus_fans yang udah mampir di live TikTok kita dan request lagu Hati-Hati di Jalan dari Tulus. …"
- Catatan: intro sempat menyebut "sore" padahal program pagi. Prompt intro tidak memberi konteks waktu (berlaku juga untuk intro non-request).
