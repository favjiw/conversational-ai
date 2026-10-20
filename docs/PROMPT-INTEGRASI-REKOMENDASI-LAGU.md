# Prompt Claude Code: Integrasi Rekomendasi Lagu ke Penyiar AI HITS

> Cara pakai: buka Claude Code di root repo `penyiar-ai`, lalu tempel seluruh isi di bawah garis ini (atau: "Baca dan kerjakan `docs/PROMPT-INTEGRASI-REKOMENDASI-LAGU.md`").

---

## Tugas

Gabungkan modul rekomendasi lagu buatan rekan saya (Iam), repo **https://github.com/ffromme/hits-song-recommender**, ke sistem penyiar AI ini. Tujuannya memenuhi fitur wajib no. 2 di `docs/KEPUTUSAN-DESAIN.md` ("rekomendasi musik berdasarkan emosi") dan sebagian fitur no. 4 (komentar penonton direspons).

Sebelum mulai, baca: `CLAUDE.md` (dan dokumen yang dirujuknya), `docs/CATATAN-PROGRES.md`, lalu `README.md` + `CLAUDE.md` milik repo rekan setelah repo itu tersedia (Tahap 0).

## Aturan kerja

1. Kerjakan **per tahap**. Di akhir tiap tahap: jalankan tes, tunjukkan output nyata, ringkas 3–5 kalimat, lalu **berhenti dan tunggu saya bilang "lanjut"**.
2. Batasan lama tetap berlaku: jangan ubah logika LLM persona, rundown, prompt persona, lip-sync, atau pemetaan emosi **kecuali untuk integrasi ini, dan jelaskan dulu sebelum mengubah**.
3. **Kode rekan tidak diedit di dalam repo ini.** Kalau butuh perubahan di `hits_rec`, buat lapisan adapter di sisi kita. Kalau memang harus mengubah kodenya, tulis usulannya untuk saya ajukan sebagai PR ke repo rekan.
4. Jika kode bertentangan dengan `docs/KEPUTUSAN-DESAIN.md`, laporkan dulu.
5. Jangan instal paket besar tanpa memberi tahu dulu (lihat Tahap 0: PyTorch CPU ±1,4 GB).
6. Rahasia hanya di `.env`. Ingat ada **dua `.env`** (root dan `backend/.env`, yang kedua menimpa yang pertama). Cek diff tidak berisi API key sebelum commit.
7. Komentar kode dan dokumen berbahasa Indonesia, nama variabel/fungsi berbahasa Inggris (mengikuti gaya repo).
8. Setiap kegagalan rekomendasi **tidak boleh menghentikan live**: selalu ada fallback ke perilaku sekarang (Deezer per kategori).

## Konteks yang sudah saya kumpulkan (verifikasi sendiri sebelum dipakai)

### Sisi penyiar-ai (repo ini)
- Branch aktif `stage-portrait`, banyak perubahan **belum di-commit** (lihat `docs/CATATAN-PROGRES.md` §1 dan §9).
- Musik sekarang: `backend/app/music/provider.py` (`DeezerMusicProvider.search(category, query, limit)`, kueri acak per kategori `indo_hits | indo | barat | korea`) dan `backend/app/music/models.py` (`MusicTrack`, `MusicSearchRequest` dengan field `mood` yang belum dipakai).
- `backend/app/orchestrator/clock_runner.py`:
  - `_prepare_song(slot, idx)` memilih lagu: `music.search(category=..., limit=3)` lalu ambil `tracks[0]`, membuat intro + backsell via LLM, dan TTS keduanya paralel. Hasilnya `PreparedSong(track, intro, outro)`.
  - `_schedule_song_prep(idx)` menyiapkan **lagu pertama di/setelah slot idx**. Dugaan saya: untuk dua slot lagu berturutan (mis. s11 → s12), persiapan s12 baru dimulai saat s12 sendiri mulai, jadi tidak ada prefetch dan bisa ada jeda. Tolong cek dengan tes; kalau benar, usulkan perbaikan (mis. sekaligus menyiapkan lagu berikutnya saat slot lagu dimulai) dan tunggu persetujuan saya.
  - Event `clock_music` membawa `track.model_dump()`, jadi field baru di `MusicTrack` otomatis sampai ke frontend.
- `backend/app/main.py`: `music_provider = create_music_provider(...)` dibuat saat import; `ClockRunner` dibuat di `POST /api/clock/start`. Belum ada endpoint komentar.
- Rundown `clock-pagi-bener-live-1jam.json`: 11 slot lagu dengan kategori `indo_hits`, `indo`, `barat`, `korea`.
- Tes backend: `cd backend && python -m unittest discover -s tests` (96 tes lulus per 20 Okt). Ada `tests/test_music.py` dan `tests/test_song_prefetch.py`.
- Rencana Tahap 4 `/stage` di CATATAN-PROGRES: "komentar operator (endpoint kecil + event `comment` lewat WS yang ada) → `reading_comments`". **Endpoint dan event komentar yang dibuat di tugas ini harus bisa dipakai ulang oleh Tahap 4 itu**, jadi jangan buat jalur kedua.
- `KEPUTUSAN-DESAIN.md` §3.B.7: komentar dikumpulkan ke antrean, disaring, dan **tidak memotong lagu**. §9 masih belum memutuskan "emosi untuk musik: emosi topik Talk atau emosi komentar penonton".

### Sisi hits-song-recommender (repo rekan)
- Library Python `src/hits_rec/`, paket `hits-rec` (punya `pyproject.toml`, bisa `pip install -e .`).
- Alur: komentar → `intent` (LLM: `explicit_song | mood_request | not_a_request`, plus `needs_moderation`) → `retrieval` (fuzzy match judul/artis, atau vector search ChromaDB + filter bahasa/energi/cooldown) → `rerank` (LLM pilih 1 dari maks 8 + `reason` + `host_line`).
- API utama: `Recommender().recommend(comment) -> PipelineResult` (`intent`, `recommendation: Recommendation | None`, `note`, `timings`). `Recommendation` berisi `song: LabeledSong` (`song_id, title, artist, language, genre, year, moods, energy, valence, mood_description, ...`), `reason`, `host_line`.
- Fungsi tingkat bawah yang mungkin berguna untuk lagu berbasis mood Talk (tanpa komentar): `retrieval.search_by_mood(profile, energy, language, history)` dan `rerank.rerank(comment, situation, candidates)`.
- **Jebakan yang perlu ditangani di adapter:**
  - `hits_rec.config` membaca `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / LLM_REASONING_EFFORT` lewat `os.getenv` **saat import**, dan `load_dotenv` dari root repo rekan (tidak menimpa env yang sudah ada). Jadi adapter harus mengisi `os.environ` dari `Settings` kita **sebelum** `import hits_rec`.
  - Path data (`data/raw/songs.csv`, `data/labeled/songs_labeled.jsonl`, `.cache/chroma`) dihitung relatif terhadap root repo rekan. Instal dari URL git (bukan editable) akan merusak path ini.
  - Semua fungsinya **sinkron** (klien `openai` sinkron, `max_retries=5`, `timeout=120`). Jalankan lewat `asyncio.to_thread` dengan batas waktu sendiri (mis. `asyncio.wait_for`, ±8 s) supaya event loop dan live tidak tertahan.
  - `Recommender.__init__` memuat model embedding `intfloat/multilingual-e5-small` (±10 s; unduhan pertama ±470 MB). Muat di latar belakang saat backend start, jangan memblok startup.
  - `Recommender.recommend()` **langsung memasukkan lagu ke riwayat cooldown** (`PlayHistory`, di memori, 10 lagu). Pikirkan kapan lagu dianggap "diputar" (saat dipilih atau saat benar-benar on-air) dan jelaskan pilihanmu.
  - Katalog berisi 102 lagu: 43 `id`, 59 `en`, **tidak ada `ko`**. Slot `korea` tidak bisa dilayani katalog.
  - Katalog **tidak punya audio**. Audio harus dicari di Deezer berdasarkan `artist + title`, lalu dicocokkan (fuzzy) judul dan artisnya sebelum dipakai. Kalau tidak ketemu, coba kandidat lain atau fallback.
  - LLM runtime yang dipakai rekan: Groq `qwen/qwen3.8-27b` via API OpenAI-compatible. Batas gratis 8.000 token/menit (±3–4 rekomendasi/menit) dan 1.000 request/hari.
  - Web demo rekan (`scripts/05_web.py`) memakai port 8000, sama dengan backend kita. Jangan jalankan bersamaan.
  - Diuji di Windows 11 + Python 3.14. Pernah kena Windows Smart App Control (DLL diblokir). Jangan ubah pengaturan keamanan Windows sendiri.

## Keputusan yang harus kamu tanyakan ke saya di awal (beri rekomendasi + alasan singkat)

1. **Cara memasukkan kode rekan.** Rekomendasi saya: git submodule di `external/hits-song-recommender` + `pip install -e external/hits-song-recommender` di venv backend, supaya kode rekan tidak tercampur, versinya terkunci per commit, dan path datanya tetap benar. Alternatif: salin ke `backend/app/...` (lebih mudah dijalankan, tapi sulit sinkron dengan update rekan).
2. **Sumber lagu untuk slot lagu tanpa request penonton.** Usulan urutan prioritas: (a) request dari komentar penonton yang menunggu; (b) lagu berbasis mood topik Talk terakhir lewat `search_by_mood` dengan filter bahasa sesuai kategori slot (`indo_hits/indo → id`, `barat → en`); (c) Deezer per kategori seperti sekarang (termasuk semua slot `korea`). Poin (b) menyentuh keputusan §9 yang belum diputuskan, jadi tanyakan apakah (b) dipakai sekarang atau di belakang flag.
3. **Provider LLM untuk rekomendasi.** Usulan: Groq (key terpisah, tidak memakan kuota Gemini kita). Alternatif: Gemini lewat endpoint OpenAI-compatible-nya.
4. **Branch.** `stage-portrait` belum di-commit. Tanyakan apakah saya mau commit + PR dulu (langkah 1 di CATATAN-PROGRES §10), lalu kerja di branch baru `song-recommender`.

## Tahapan

### Tahap 0: Persiapan dan uji modul rekan secara terpisah
- Cek `git status`, laksanakan keputusan no. 4.
- Tambahkan repo rekan sesuai keputusan no. 1. Cek versi Python venv backend (`python --version`) dan pastikan cocok dengan `requires-python >= 3.10` serta tersedia wheel PyTorch/ChromaDB untuk versi itu.
- **Beri tahu saya dulu** sebelum instalasi `sentence-transformers` + `chromadb` (PyTorch CPU ±1,4 GB). Laptop saya: GPU MX250 2 GB, jadi pakai versi CPU.
- Tambahkan variabel ke `Settings` (`backend/app/config.py`), `.env.example`, dan kedua `.env` (nilai kosong, saya yang mengisi key):
  `RECOMMENDER_ENABLED`, `RECOMMENDER_LLM_API_KEY`, `RECOMMENDER_LLM_BASE_URL`, `RECOMMENDER_LLM_MODEL`, `RECOMMENDER_LLM_REASONING_EFFORT`, `RECOMMENDER_TIMEOUT_SEC`, dan `RECOMMENDER_MAX_PENDING` (atau nama lain yang lebih konsisten, jelaskan).
- Bangun indeks: `python scripts/02_build_index.py` di folder repo rekan (label `songs_labeled.jsonl` sudah ada, **jangan** melabel ulang).
- Jalankan `pytest` milik rekan dan `python -m hits_rec.pipeline` sebagai smoke test. Tunjukkan output dan latensinya.

### Tahap 1: Adapter backend `app/music/recommender.py`
- Kelas layanan (mis. `SongRecommenderService`) yang:
  - mengisi `os.environ` untuk `hits_rec` dari `Settings`, lalu import secara lazy;
  - memuat `Recommender` di thread latar saat startup backend, dengan status `loading | ready | disabled | error` (tampilkan di `/health` atau endpoint status);
  - `async recommend_for_comment(username, text)` → hasil terstruktur (intent, lagu katalog, `host_line`, `reason`, `timings`, catatan) lewat `asyncio.to_thread` + timeout;
  - (bila keputusan no. 2b disetujui) `async recommend_for_mood(mood_text, language)`;
  - `async resolve_audio(song) -> MusicTrack | None`: cari di Deezer (`"{artist} {title}"`), cocokkan fuzzy judul + artis, ambil `preview_url`;
  - mati dengan rapi (tanpa error) bila `RECOMMENDER_ENABLED=false`, `LLM_MODE=mock`, key kosong, atau paket belum terinstal. Dalam kondisi itu sistem berjalan persis seperti sekarang.
- Perluas `MusicTrack` dengan field opsional, mis. `rec_source` (`comment | talk_mood | category | fallback`), `requested_by`, `request_comment`, `host_line`, `reason`, `catalog_song_id`. Field default harus menjaga semua tes lama tetap lulus.
- Tes unit **tanpa API dan tanpa memuat model** (mock `hits_rec`): mode nonaktif, timeout, Deezer tidak cocok, dan konversi ke `MusicTrack`.

### Tahap 2: Antrean komentar dan endpoint
- `POST /api/comments` dengan body `{username, text}` (validasi panjang, mis. maks 300 karakter, dan username wajib). Broadcast event WS `comment` ke console dan stage (event yang sama akan dipakai Tahap 4 `/stage` untuk `reading_comments`).
- Klasifikasi tiap komentar lewat adapter:
  - `explicit_song` / `mood_request` → masuk **antrean request lagu** beserta hasil rekomendasinya;
  - `not_a_request` → simpan di antrean komentar umum untuk segmen Talk nanti (**belum** disuntikkan ke Talk; itu tugas lain);
  - `needs_moderation` → tidak masuk antrean mana pun, dicatat di log, dan hanya console yang diberi tahu (event mis. `comment_rejected`).
- Batasi beban LLM: proses komentar satu per satu (semaphore), batasi jumlah request yang menunggu (`RECOMMENDER_MAX_PENDING`), satu request aktif per username, dan buang duplikat. Komentar yang melebihi batas tetap disimpan sebagai komentar biasa.
- `GET /api/comments` atau ikut di event WS: daftar antrean beserta status (`menunggu`, `dijadwalkan di slot sXX`, `diputar`, `ditolak`, `tidak tersedia`).
- Tes untuk endpoint, antrean, batas, dan moderasi.

### Tahap 3: Sambungkan ke `ClockRunner._prepare_song`
- Urutan sumber lagu sesuai keputusan no. 2, dengan fallback ke Deezer per kategori yang sudah ada.
- Request penonton boleh mengabaikan kategori slot (request lagu barat bisa diputar di slot `indo`). Jelaskan bila kamu ingin aturan lain.
- **Intro lagu request** harus menyebut username dan isi request, sesuai fitur wajib no. 4. Usulan: `host_line` dari rekomendasi dipakai sebagai bahan di prompt intro persona yang sudah ada (bukan dibacakan mentah-mentah), lalu tetap melewati `clean_text_for_tts`. **Ini mengubah prompt intro lagu, jadi tunjukkan diff prompt-nya dan tunggu persetujuan saya.** Backsell tidak diubah.
- Tangani waktu: request yang masuk setelah persiapan slot lagu berikutnya dimulai otomatis dipakai untuk slot lagu sesudahnya. Laporkan juga hasil pengecekan prefetch dua lagu berturutan (lihat konteks di atas).
- Skip/stop saat persiapan: request yang belum diputar dikembalikan ke antrean (atau jelaskan alternatifnya). Riwayat cooldown konsisten dengan keputusan di Tahap 1.
- Kirim event console (mis. `song_request_scheduled`) saat request dijadwalkan ke slot tertentu.
- Tambah tes di `tests/test_song_prefetch.py` atau file baru: request dipakai lebih dulu, fallback saat rekomendasi gagal/timeout/audio tidak ketemu, slot `korea` tetap ke Deezer, dan tes lama tetap lulus.

### Tahap 4: UI
- Konsol operator (`frontend/src/components/`, mis. `SessionConsole.jsx`/`LiveSession.jsx`): form input komentar (username + teks), daftar antrean request dengan statusnya, dan status layanan rekomendasi (`loading/ready/disabled`). `NowPlayingMusic.jsx` menampilkan "Request dari @username" bila ada.
- `/stage` (`PortraitHUD.tsx`): perubahan **minimal**, cukup tampilkan "Request @username" di kartu Lagu / Lagu Berikutnya bila field-nya ada. **Jangan** mengerjakan listening states (`reading_comments` dll.), karena itu Tahap 3–4 rencana `/stage` sendiri.
- Type check, `vite build`, dan `oxlint src/stage` harus tetap bersih. Beri tahu saya bagian mana yang perlu dicek di browser.

### Tahap 5: Uji ujung-ke-ujung, log, dan dokumen
- Skenario uji live (bisa memakai mode `backend-mock` di `.claude/launch.json` untuk TTS/LLM persona): kirim komentar contoh berikut berurutan lewat endpoint (diambil dari `DEMO_COMMENTS` rekan), lalu tunjukkan slot mana memutar lagu apa:
  - `kak puterin hati2 dijalan nya tulus dong 🥺🙏` (eksplisit, ada di katalog)
  - `req lathi weird genius dong kak 🔥` (tidak ada di katalog → lagu mirip)
  - `lg excited bgt nungguin kakak pulang dr rantau, lagu apa ya yg cocok?? 😆` (mood)
  - `kak puterin hati hati di jalan lagi dong, td telat masuk live` (cooldown)
  - `halo kak salam dari bandung 👋` (bukan request)
  - satu komentar kasar (moderasi)
- Catat ke log sesi (`session_logging`): komentar, intent, lagu terpilih, sumber (`rec_source`), dan latensi per langkah (`timings` dari rekan + pencarian Deezer). Ini juga mengisi butir "log latensi per tahap" di CATATAN-PROGRES §7.
- Perbarui `docs/CATATAN-PROGRES.md` (status, cara menjalankan, konfigurasi baru, jebakan). Untuk `docs/KEPUTUSAN-DESAIN.md`, usulkan perubahan teks §2.2, §3, §7, dan §9 dan **tunggu persetujuan saya** sebelum menulis.
- Tambahkan kredit untuk repo rekan (Iam, `ffromme/hits-song-recommender`) di README/dokumen yang sesuai.
- Siapkan pesan commit dan deskripsi PR, tapi jangan push sebelum saya minta.
