# PRD: HITS AI Live, Penyiar AI Percakapan untuk Live TikTok

| | |
|---|---|
| **Versi** | 0.3 (draft, fokus Fase 1: conversational AI + TTS; rundown live 1 jam) |
| **Tanggal** | 2 Oktober 2026 |
| **Pemilik** | Muhammad Favian Jiwani |
| **Mitra** | HITS Unikom Radio |
| **Status** | Perencanaan, belum ada implementasi |
| **Tenggat** | Sebelum UTS semester 7 (sekitar akhir Desember 2026) |
| **Model AI** | Google Gemini API (via Google AI Studio) |
| **Alat build** | Antigravity (vibe coding) |

Label di dokumen ini: **[Keputusan]** sudah diputuskan, **[Usulan]** belum diputuskan dan boleh diubah.

---

## 0. Fokus saat ini: Fase 1 (conversational AI + TTS) [Keputusan]

Untuk saat ini pengerjaan **hanya sampai conversational AI (LLM dengan LLM) dan text-to-speech**. Bagian lain di dokumen ini tetap dipertahankan sebagai arah jangka panjang (Fase 2), tetapi **tidak boleh dikerjakan** pada Fase 1. Agen coding hanya mengerjakan item di kolom "Fase 1".

| Kebutuhan | Fase 1 (kerjakan sekarang) | Fase 2 (ditunda) |
|---|---|---|
| FR-1 Parser Tema dan clock | Versi ringkas: Tema dimuat dari file JSON atau ditempel di UI. Parser docx dan gambar clock opsional (P1) | Parser penuh, seluruh clock |
| FR-2 Orchestrator | Versi ringkas: menjalankan satu atau beberapa slot Talk secara berurutan | Seluruh slot non-Talk dan state machine penuh |
| FR-3 Conversation Engine + Supervisor | **Ya (inti)** | |
| FR-4 TTS dua suara | **Ya (inti)** | |
| FR-5 Avatar 3D dan lip-sync | | Ditunda. Pada Fase 1 cukup lingkaran inisial persona sebagai penanda yang sedang bicara |
| FR-6 Audio engine | Hanya pemutaran audio berurutan dengan kunci giliran (tanpa ducking) | Ducking dan musik |
| FR-7 Musik berbasis emosi | | Ditunda |
| FR-8 Panel operator | Versi ringkas (Session Console, lihat di bawah) | Kontrol penuh |
| FR-9 Halaman /stage | | Ditunda |
| FR-10 Fallback | Retry, backoff, dan fallback jika LLM atau TTS gagal; `FAIL_INJECT` | Fallback lagu dan audio rekaman |
| FR-11 Logging | **Ya** | |
| FR-12 Runner eksperimen | **Ya** (simulasi teks A/B/C) | |
| FR-13 VAD | | Ditunda |

**UI Fase 1** (satu aplikasi web, layar desktop):

1. **Session Console:** pilih Tema, kondisi (A/B/C), mulai, jeda, lanjut, berhenti. Transkrip percakapan dua persona bergantian dengan tag emosi, pemutar audio per giliran dengan status "sedang berbicara", panel Supervisor Inspector (status drift, jenis drift, bukti, koreksi memori, ledger fakta), serta rincian latensi (persona, supervisor, TTS) dan status API.
2. **Persona Editor:** edit dua kartu persona dan pratinjau suara.
3. **Tema Library:** daftar Tema dengan mode (`scripted`, `improv`, `listener_content`) dan editor teks yang menandai jeda `/` dan `//`.
4. **TTS Lab:** uji suara (teks, provider, suara pria atau wanita) dan form skor naturalness 1 sampai 5 untuk tes minggu 4.
5. **Experiment Runner:** jalankan simulasi kondisi A/B/C, lihat hasil per snapshot, ekspor log.

Prompt desain untuk Google Stitch tersedia di berkas terpisah (`Stitch-Prompt-HITS-AI-Live.md`).

**Fase 1 selesai jika** (Definition of Done Fase 1 ada di bagian 17): percakapan dua persona berjalan beberapa menit dengan suara pria dan wanita, supervisor mendeteksi dan mengoreksi drift, dan log tiga kondisi eksperimen bisa dihasilkan.

---

## 1. Ringkasan

HITS AI Live adalah aplikasi web yang menjalankan satu jam program live TikTok HITS Unikom Radio dengan dua penyiar AI (satu pria, satu wanita) yang berbincang satu sama lain. Aplikasi membaca rundown (clock) "Pagi Bener" dan materi Tema, menjalankan slot non-Talk (jingle, iklan, time signal, lagu) secara berurutan, dan mengisi slot Talk lewat percakapan dua LLM yang dimediasi supervisor. Penyiar tampil sebagai dua karakter 3D dengan suara natural, lip-sync, dan ekspresi. Tampilan web ditangkap oleh TikTok LIVE Studio untuk disiarkan.

Proyek ini punya dua keluaran:

1. **Produk KP:** demo live 1 jam untuk stakeholder HITS.
2. **Bahan skripsi:** mekanisme supervisor (AI-in-the-Loop) pada arsitektur Multi-LLM untuk mengurangi identity drift. Live streaming menjadi studi kasus.

## 2. Latar belakang dan masalah

- Live TikTok HITS saat ini dibawakan penyiar manusia dan bisa batal jika penyiar tidak hadir. [Keputusan]
- Penyiar manusia berimprovisasi dari Tema yang diserahkan HITS. Isi Tema tidak seragam: sebagian hampir tertulis penuh, sebagian hanya arahan.
- Percakapan antar LLM yang panjang rentan identity drift (Choi et al., 2025, arXiv:2412.00804): persona bergeser, model mengarang detail fiktif, dan persona lewat prompt saja tidak menjamin identitas stabil. Paper tersebut belum menguji mitigasi, dan di sinilah kontribusi skripsi.

## 3. Tujuan, non-tujuan, dan metrik

### Tujuan (MVP)

- **G1.** Percakapan AI dengan AI, 1 suara pria dan 1 suara wanita yang tidak terdengar seperti robot. [Keputusan]
- **G2.** Suara selaras dengan ekspresi wajah dan gerak mulut karakter 3D. [Keputusan]
- **G3.** Rekomendasi musik berdasarkan emosi dari pesan pendengar, musik dari API. [Keputusan]
- **G4.** Satu sesi live 1 jam yang berjalan sesuai clock tanpa intervensi manusia di dalam aplikasi. [Keputusan]
- **G5.** Infrastruktur eksperimen yang menghasilkan data untuk membandingkan kondisi A/B/C pada skripsi. [Usulan]

### Non-tujuan

- Sistem siaran radio on-air (sudah dikeluarkan dari target KP). [Keputusan]
- Otomasi UI TikTok (membuka TikTok, menekan Go Live). Dilakukan manual pada MVP. [Usulan]
- Arsitektur multi-agent penuh yang memutuskan jalannya siaran. Dicatat sebagai saran pengembangan lanjutan. [Usulan]
- Sesi 3 jam akhir pekan, clock selain "Pagi Bener", integrasi database musik HITS.
- Meniru penyiar HITS yang nyata (kecuali ada izin tertulis).

### Metrik keberhasilan

| Metrik | Target |
|---|---|
| Durasi sesi berjalan tanpa crash | 60 menit penuh, minimal 2 kali berturut-turut saat rehearsal |
| Jeda antar ucapan penyiar (dirasakan penonton) | Rata-rata 2 detik atau kurang berkat prefetch [Usulan] |
| Naturalness suara | Skor rata-rata 4 dari 5 oleh 3 sampai 5 pendengar [Usulan] |
| Lip-sync | Mulut bergerak hanya saat karakter itu berbicara, tanpa lag terlihat |
| Fallback | Kegagalan API tidak menghentikan siaran lebih dari 5 detik |
| Skripsi | Data 3 kondisi (A/B/C) dengan log lengkap |

## 4. Pengguna dan stakeholder

- **Operator (Favian/staf HITS):** menyiapkan clock dan Tema, menjalankan sesi, memantau, menekan Go Live di TikTok LIVE Studio.
- **Penonton TikTok Live:** menikmati siaran, kelak mengirim pesan.
- **Direktur dan Program/Music Director HITS:** menilai demo.
- **Pembimbing skripsi dan reviewer:** menilai kontribusi riset.

## 5. Ruang lingkup

| Area | MVP | Nanti |
|---|---|---|
| Mode percakapan | AI dengan AI (dua arah) | Monolog satu arah, tamu manusia dengan VAD |
| Clock | "Pagi Bener" 1 jam | Clock lain, sesi 3 jam |
| Pesan pendengar | Disimulasikan lewat panel operator | Baca komentar TikTok langsung |
| Musik | API musik, fallback lagu cadangan | Database musik HITS, RAG |
| Siaran | Tangkap jendela via TikTok LIVE Studio | Otomasi penuh |

## 5b. Rundown live 1 jam (adaptasi dari clock on-air)

Clock "Pagi Bener" adalah rundown **siaran on-air** HITS Unikom Radio (tiga blok, 06.00 sampai 09.00). AI Live TikTok adalah program baru dan oleh perusahaan dibatasi **1 jam**, jadi rundown live memakai satu blok clock asli dengan penyesuaian seperlunya. [Keputusan: durasi 1 jam dan mengikuti rundown asli. Pemilihan blok dan adaptasi di bawah: Usulan]

**Dasar:** blok 07.00 sampai 08.00, karena satu-satunya blok dengan 5 slot Talk dan struktur paling lengkap (blok 06.00 dan 08.00 dapat dijadikan varian dengan template yang sama). Berkas: `data/clock/clock-pagi-bener-live-1jam.json` (39 slot).

| Kuartal | Urutan slot (durasi nominal) |
|---|---|
| 00:00 sampai 07.15 | Smash Time Signal (9 dtk), Time Signal Jam 7 (10 dtk), Jingle Alamat HITS (13 dtk), P.S.A (1 mnt), Greetings Artis (20 dtk), Image/Mashup (32 dtk), Lagu Indo HITS (3), **Talk 1 HITS News (1)**, Lagu Indo HITS (3), **Talk 2 Traffic Info (3)**, Lagu Barat (3) |
| 07.15 sampai 07.30 | Smash Versi (5 dtk), 2x Spot/Adlibs (1), Jingle HITS (25 dtk), 2x Lagu Indo (3), **Talk 3 Teaser 3M (3)**, Lagu Barat (3) |
| 07.30 sampai 07.45 | Smash Versi, 2x Spot/Adlibs, Jingle HITS, Lagu Indo, Lagu Korea, **Talk 4 3M (3)**, Lagu Indo |
| 07.45 sampai 08.00 | Smash Versi, 2x Spot/Adlibs, Jingle HITS, Lagu Barat, **Talk 5 3M (3)**, Lagu Indo, **Closing + Selling Next Live (3)**, Jingle Alamat HITS (outro) |

**Komposisi (nominal):** 6 slot Talk (16 menit), 11 lagu (33 menit), 6 Spot/Adlibs (6 menit), sisanya jingle dan stinger. Total nominal 59,1 menit.

**Adaptasi dari clock asli** [Usulan]
- **Selling Next Hour menjadi Closing + Selling Next Live.** Live berhenti setelah 1 jam sehingga tidak ada jam berikutnya untuk dipromosikan.
- **Lagu terakhir clock asli dihapus.** Lagu itu hanya menjembatani ke jam berikutnya. Durasi nominal blok asli jika dijumlahkan sekitar 62 menit, dan penghapusan ini membuatnya muat dalam 60 menit. Jingle Alamat HITS ditambahkan (opsional) sebagai penutup.
- **Time Signal diparameterkan** (`time_signal_hour`), karena rekaman time signal terikat jam tayang. Jam tayang live sebenarnya belum diketahui.
- **Greetings Artis opsional** (rekaman dari HITS; dilewati jika berkas tidak ada).
- **Slot non-Talk dilewati pada Fase 1.** Hanya 6 slot Talk yang dijalankan.

**Sinkronisasi waktu:** durasi lagu aktual bervariasi, jadi tiga `time_marker` (07.15, 07.30, 07.45) berfungsi sebagai titik sinkron dan sesi punya batas keras 60:00 (lihat FR-2).

---

## 6. Kebutuhan fungsional

Prioritas: **P0** wajib MVP, **P1** penting, **P2** opsional. AC = acceptance criteria.

### FR-1 Parser Tema dan clock (P0)

- Rundown live 1 jam (bagian 5b) sudah ditranskripsi dari gambar clock ke `data/clock/clock-pagi-bener-live-1jam.json`. Parser cukup mengisi `tema.content` tiap slot Talk dari `PAGI_BENER.docx`.
- Docx diekstrak teksnya dengan `python-docx`, lalu Gemini menstrukturkan hasilnya per Tema (structured output) dan hasilnya diperiksa manual. Parser untuk gambar clock tidak diperlukan lagi.
- Klasifikasi elemen: Greetings Artis = audio rekaman statis; Spot/Adlibs dan Ice Breaking (hanya ada di blok 06.00) = TTS; jingle, smash, time signal, PSA, image/mashup = audio statis atau TTS yang di-cache; lagu = API musik; Talk = percakapan LLM. [Keputusan]
- Tanda jeda `/` dan `//` dipertahankan sebagai penanda jeda pendek dan panjang.
- Tiap Tema diberi `mode`: `scripted` (dialog hampir tertulis penuh, misal HITS News dan Sport), `improv` (hanya arahan), atau `listener_content` ("Say Hi!", "3M").
- **AC:** JSON valid terhadap skema (bagian 10), tiap slot punya `type`, `order`, `duration_sec`, dan slot Talk punya `tema`. Ada perintah CLI `validate-clock`.

### FR-2 Orchestrator (P0)

- State machine yang mengeksekusi slot sesuai urutan clock: `IDLE → RUNNING → (PAUSED) → FINISHED`, dengan sub-state per slot. Tidak ada keputusan agentik. [Keputusan]
- Slot non-Talk memicu aksi audio. Slot Talk memanggil Conversation Engine (FR-3).
- Sinkronisasi waktu: `time_marker` (07.15, 07.30, 07.45) adalah titik sinkron. Karena durasi lagu aktual bervariasi, orchestrator memilih lagu menurut sisa waktu atau melakukan fade-out agar tiba tepat di marker, dan sesi berakhir dengan batas keras 60:00. [Usulan]
- Kontrol operator: start, pause, resume, skip slot, kill switch.
- **AC:** dengan clock uji berdurasi 5 menit dan mode mock, seluruh slot berjalan berurutan dan status terkirim ke UI lewat WebSocket.

### FR-3 Conversation Engine dengan Supervisor (P0)

- Dua persona (A pria, B wanita) berbicara bergantian pada slot Talk. Setiap giliran melewati supervisor. [Keputusan]
- Siklus: supervisor menerima Tema, meminta balasan satu persona, memeriksa identity drift, menyuntikkan koreksi (memori persona dan percakapan) bila ada drift, lalu meneruskan ke persona lain sampai Tema selesai. [Keputusan]
- Memori supervisor [Usulan]:
  - **Kartu persona** (tetap).
  - **Ringkasan percakapan** bergulir.
  - **Ledger fakta**: klaim yang sudah diucapkan tiap persona tentang dirinya atau lawan bicara, untuk mendeteksi pengarangan detail fiktif dan kontradiksi.
- Jenis drift yang diperiksa: (1) mengarang detail fiktif tentang diri atau lawan bicara, (2) pergeseran gaya bicara atau sifat, (3) melanggar batasan topik persona, (4) kontradiksi dengan ucapan sebelumnya, (5) tertukar peran atau meniru suara lawan bicara.
- Maksimal 2 kali regenerasi per giliran. Jika masih drift, supervisor mengoreksi teks secara langsung lalu meneruskan, dan mencatatnya di log.
- Keluaran akhir per giliran: `text` dan `emotion` (lihat bagian 10).
- Mode `scripted`: teks Tema dibacakan dengan variasi minimal, supervisor tetap memeriksa konsistensi persona.
- **AC:** pada mode mock, loop selesai untuk Tema uji; setiap giliran menghasilkan satu entri log berisi balasan mentah, verdict supervisor, koreksi, dan latensi.

### FR-4 Text-to-Speech dua suara (P0)

- Antarmuka `TTSProvider` dengan dua implementasi: `gemini` (default MVP, satu API key dengan LLM) dan `elevenlabs` (asumsi awal di keputusan sebelumnya). Dipilih lewat `TTS_PROVIDER`. [Usulan, lihat bagian 16]
- Satu suara pria dan satu suara wanita, bahasa Indonesia santai.
- Tanda jeda `/` dan `//` diubah menjadi jeda pendek dan panjang dengan memecah teks menjadi segmen dan menyisipkan keheningan (agnostik terhadap provider).
- Audio statis (jingle, iklan, time signal) di-generate sekali dan di-cache dengan kunci `hash(teks, suara, provider)`.
- Output Gemini TTS berupa PCM mentah, jadi perlu dibungkus menjadi WAV sebelum dikirim ke browser. (Verifikasi format terbaru di dokumentasi.)
- **AC:** endpoint `POST /tts` mengembalikan audio yang bisa diputar; cache hit tidak memanggil API; tes naturalness minggu 4 dijalankan.

### FR-5 Avatar 3D dan lip-sync (P0)

- Dua karakter VRM dalam satu scene three.js. [Usulan]
- Mulut digerakkan oleh amplitudo audio (WebAudio `AnalyserNode`) ke blendshape mulut VRM. Viseme penuh adalah P2.
- Ekspresi dari tag emosi, ditambah animasi idle (kedip, napas, gerak kepala kecil).
- Karakter yang sedang bicara diberi penanda (sorotan atau nama di layar).
- Harus berjalan lancar pada laptop GPU MX250 bersama TikTok LIVE Studio. Sediakan pengaturan kualitas rendah.
- Pustaka spesifik (misalnya `@pixiv/three-vrm`) perlu diverifikasi versinya dan lisensi model VRM yang dipakai.
- **AC:** minimal 30 FPS pada laptop target dengan dua karakter; mulut diam saat tidak ada audio dari karakter itu.

### FR-6 Audio engine (P0)

- Pemutaran lewat WebAudio dengan gain node: musik mengecil (ducking) saat penyiar bicara dan kembali naik sesudahnya.
- Antrean audio berurutan dengan event `ended` yang mengunci pergantian giliran.
- **AC:** ducking terdengar jelas, tidak ada dua penyiar bicara bersamaan.

### FR-7 Musik berbasis emosi (P1)

- Alur: pesan pendengar → klasifikasi emosi oleh Gemini (structured output) → pemetaan ke kueri musik → panggilan API musik sebagai tool (function calling) → persona mengumumkan lagu → lagu diputar dengan ducking. [Keputusan, musik dari API]
- Antarmuka `MusicProvider` dengan `MockProvider` (daftar lagu lokal) lebih dulu. API musik nyata dipilih setelah keputusan lisensi (bagian 16).
- Fallback: jika API gagal atau lagu tidak ditemukan, putar lagu cadangan dari daftar lokal.
- Pesan pendengar diinput lewat panel operator pada MVP.
- **AC:** input "gw lagi sedih, saranin lagu dong" menghasilkan emosi `sedih`, satu lagu terpilih, dan pengumuman persona; kegagalan API memicu fallback tanpa menghentikan sesi.

### FR-8 Panel operator (P0)

- Tombol start, pause, resume, skip, kill switch.
- Indikator slot aktif, timer, dan status API (OK, rate limit, gagal).
- Input pesan pendengar simulasi.
- Pemilih mode: `live` (API nyata) atau `mock`.
- Tampilan log giliran terakhir (balasan, verdict supervisor, latensi).
- **AC:** seluruh kontrol berfungsi saat sesi berjalan.

### FR-9 Tampilan panggung / Stage (P0)

- Halaman terpisah `/stage` bersih (tanpa kontrol) khusus untuk ditangkap TikTok LIVE Studio.
- Rasio layar dapat dikonfigurasi (16:9 atau 9:16).
- Menampilkan dua avatar, nama program, dan teks lagu atau judul slot yang sedang berjalan.
- **AC:** `/stage` tampil sama persis di jendela browser yang ditangkap TikTok LIVE Studio, audio ikut tertangkap (mungkin lewat virtual audio cable).

### FR-10 Fallback dan ketahanan (P0)

- Jika Gemini atau TTS gagal: coba ulang dengan backoff, lalu putar audio rekaman atau lagu cadangan dan lanjut ke slot berikutnya.
- Prefetch: hasilkan giliran berikutnya (teks dan audio) saat audio giliran sekarang masih diputar, untuk menutup latensi. [Usulan]
- **AC:** simulasi kegagalan (`FAIL_INJECT=tts`) tidak membuat sesi berhenti lebih dari 5 detik.

### FR-11 Logging dan ekspor eksperimen (P0)

- Log JSONL per giliran: id sesi, kondisi (A/B/C), slot, giliran, persona, balasan mentah, verdict supervisor, koreksi, teks final, emosi, latensi tiap tahap, model dan versi yang dipakai.
- Skrip ekspor ke CSV untuk analisis.
- **AC:** setiap sesi menghasilkan satu file log yang bisa dibaca skrip evaluasi.

### FR-12 Runner eksperimen (P1)

- Mode headless tanpa TTS dan avatar yang menjalankan simulasi teks untuk kondisi A, B, atau C dan menyimpan log (bagian 12).
- **AC:** `python -m experiments.run --condition C --sessions 10` berjalan sampai selesai dan menulis log.

### FR-13 Turn-taking dengan VAD (P2)

- Eksplorasi silence detection untuk pergantian giliran pada mode dengan tamu manusia. Pada mode AI dengan AI, giliran diatur orchestrator lewat event akhir audio, sehingga VAD tidak diperlukan. [Keputusan: ingin dicoba; Usulan: tunda sampai MVP selesai]

## 7. Kebutuhan non-fungsional

- **Performa:** 30 FPS avatar pada MX250; backend responsif saat tiga proses berjalan paralel.
- **Latensi:** per giliran normal 2 panggilan LLM (persona + supervisor), tambahan 1 panggilan per regenerasi. Prefetch menutup jeda. [Usulan]
- **Keandalan:** 60 menit tanpa crash; semua panggilan eksternal punya timeout, retry, dan fallback.
- **Keamanan:** API key hanya di backend (`.env`, tidak masuk repo). Frontend tidak memanggil Gemini langsung.
- **Biaya:** pantau jumlah panggilan dan karakter TTS per sesi; target tetap di free tier atau anggaran kecil. Hitung sebelum rehearsal.
- **Reproduksibilitas:** model dan versi dicatat di tiap log; untuk eksperimen skripsi gunakan ID model yang di-pin, bukan alias yang bisa berganti.
- **Testabilitas:** `LLM_MODE=mock` dan `TTS_MODE=mock` menghasilkan keluaran deterministik agar pengembangan dan tes tidak memakai kuota.
- **Kepatuhan:** konfirmasi aturan live TikTok dan konten AI, serta lisensi musik, bersama HITS.

## 8. Arsitektur

```
Clock (JSON) --> Orchestrator (state machine)
                    |
 slot non-Talk -----+--> Audio action (jingle, iklan, time signal, lagu)
                    |
 slot Talk ---------+--> Supervisor <--> Persona A (pria)
                            |       <--> Persona B (wanita)
                            v
                  teks final + tag emosi
                            v
                  TTS (Gemini TTS / ElevenLabs, 2 suara)
                            v
         Web app: audio player + avatar 3D (lip-sync, ekspresi)
                            v
         TikTok LIVE Studio (tangkap jendela + audio) --> TikTok Live
```

**Alur satu giliran bicara**

1. Orchestrator mengambil slot Talk beserta potongan Tema.
2. Supervisor mengirim instruksi ke Persona A dan menerima balasan `{text, emotion}`.
3. Supervisor memeriksa balasan terhadap kartu persona, ringkasan percakapan, dan ledger fakta.
4. Jika drift: suntikkan koreksi dan minta ulang (maksimal 2 kali). Jika tidak: teruskan.
5. Teks final ke TTS, audio dan emosi ke avatar, lalu giliran Persona B. Sambil audio diputar, giliran berikutnya diproduksi di belakang layar (prefetch).

**Stack** [Usulan]

- Backend: FastAPI (Python), WebSocket, `google-genai` SDK.
- Frontend: React (Vite), three.js dengan VRM, WebAudio API.
- Data: file JSON/JSONL lokal (tanpa database pada MVP).

## 9. Integrasi Gemini (Google AI Studio)

### Peran model

| Peran | Tugas | Kelas model yang disarankan [Usulan] | Output |
|---|---|---|---|
| `parser` | Tema dan clock ke JSON | Flash (multimodal untuk gambar clock) | JSON sesuai skema |
| `persona` | Ucapan Persona A dan B | Flash | `{text, emotion}` |
| `supervisor` | Deteksi drift, koreksi, update ledger | Flash atau Flash-Lite, temperature rendah | Verdict JSON |
| `emotion_music` | Klasifikasi emosi pesan pendengar, function calling musik | Flash-Lite | JSON + tool call |
| `judge` | Penilai konsistensi persona untuk eksperimen | Model berbeda dari `persona` agar tidak bias terhadap tulisannya sendiri | Skor JSON |
| `tts` | Suara dua penyiar (jika `TTS_PROVIDER=gemini`) | Model TTS Gemini | Audio PCM |

Choi et al. menemukan drift lebih terlihat pada model besar, jadi ukuran model persona adalah variabel yang layak diuji, bukan hanya diasumsikan.

### Konfigurasi (`.env`)

```
GEMINI_API_KEY=
GEMINI_MODEL_PARSER=
GEMINI_MODEL_PERSONA=
GEMINI_MODEL_SUPERVISOR=
GEMINI_MODEL_EMOTION=
GEMINI_MODEL_JUDGE=
GEMINI_MODEL_TTS=
TTS_PROVIDER=gemini        # gemini | elevenlabs
ELEVENLABS_API_KEY=
LLM_MODE=live              # live | mock
TTS_MODE=live              # live | mock
MUSIC_PROVIDER=mock        # mock | <api pilihan>
FAIL_INJECT=               # llm | tts | music (untuk uji fallback)
```

ID model sengaja dikosongkan: daftar model Gemini berubah cepat, jadi isi dari daftar model di AI Studio saat implementasi. Jangan hardcode ID di kode.

### Ketentuan pemakaian

- Gunakan **structured output** (JSON schema) untuk semua keluaran yang diparse mesin.
- **Rate limiter** per model (token bucket) dengan exponential backoff untuk HTTP 429. Batas free tier berbeda per akun dan per model, jadi cek di halaman rate limit AI Studio pada minggu pertama dan jadikan hasilnya angka konfigurasi.
- Free tier memakai kunci per proyek; batas berlaku per proyek, bukan per key.
- Catat semua panggilan (model, token, latensi) di log.

## 10. Skema data

### Clock

Contoh potongan dari `data/clock/clock-pagi-bener-live-1jam.json`:

```json
{
  "show": "Pagi Bener (AI Live TikTok)",
  "duration_min": 60,
  "time_signal_hour": 7,
  "time_markers_min": [15, 30, 45, 60],
  "slots": [
    { "id": "s02", "order": 2, "type": "time_signal", "label": "Time Signal Jam 7",
      "nominal_sec": 10, "source": "static_audio" },
    { "id": "s07", "order": 7, "type": "song", "label": "Lagu indo_hits",
      "nominal_sec": 180, "source": "music_api", "category": "indo_hits" },
    { "id": "s08", "order": 8, "type": "talk", "label": "Talk 1 - HITS News",
      "nominal_sec": 60, "source": "llm_conversation",
      "tema": { "title": "Talk 1 - HITS News", "mode": "scripted", "role": "news",
                "content": "Penyiar 1: ... / ... // Penyiar 2: ...", "guidance": null } },
    { "id": "s12", "order": 12, "type": "time_marker", "label": "07.15",
      "nominal_sec": 0, "source": "none", "target_min": 15 }
  ]
}
```

`type`: `smash | time_signal | jingle | psa | greetings_artis | image_mashup | smash_versi | spot_adlibs | song | talk | time_marker`.
`source`: `static_audio | tts | music_api | llm_conversation | none`.
`category` (khusus `song`): `indo_hits | indo | barat | korea`.
`tema.mode`: `scripted | improv | listener_content`. `tema.role`: `news | traffic | teaser | 3m | closing`.

### Kartu persona

```json
{
  "id": "persona_a",
  "name": "",
  "gender": "male",
  "voice": "",
  "speaking_style": "",
  "catchphrases": [],
  "topic_limits": [],
  "background_facts": [],
  "do_not": []
}
```

Dua persona fiktif ditulis pada minggu 1. Meniru penyiar HITS nyata hanya jika ada izin.

### Keluaran persona

```json
{ "text": "Halo, pagi semuanya / ...", "emotion": "happy" }
```

`emotion`: `neutral | happy | excited | sad | surprised | thoughtful | empathetic`. Dipetakan ke ekspresi VRM.

### Verdict supervisor

```json
{
  "drift_detected": false,
  "drift_types": [],
  "severity": 0,
  "evidence": "",
  "action": "forward",
  "correction_memory": {
    "persona_reminder": "",
    "conversation_summary": "",
    "facts_to_enforce": []
  },
  "ledger_updates": []
}
```

`drift_types`: `fabricated_detail | style_shift | topic_violation | contradiction | role_confusion`. `action`: `forward | regenerate`.

### Log giliran (JSONL)

```json
{
  "session_id": "", "condition": "C", "slot_id": "s07", "turn": 12,
  "persona": "A", "raw_reply": "", "verdict": {}, "regenerations": 0,
  "final_text": "", "emotion": "happy",
  "latency_ms": {"persona": 0, "supervisor": 0, "tts": 0},
  "models": {"persona": "", "supervisor": ""}
}
```

## 11. Struktur repositori

```
hits-ai-live/
  AGENTS.md                 # aturan untuk agen (bagian 14)
  docs/PRD.md
  backend/app/
    main.py                 # FastAPI + WebSocket
    config.py               # baca .env
    clock/                  # parser dan validator
    orchestrator/           # state machine
    conversation/           # supervisor, persona, memori, ledger
    llm/                    # klien Gemini, rate limiter, mode mock
    tts/                    # provider gemini, elevenlabs, cache
    music/                  # provider mock dan API
    logging/                # JSONL logger
  backend/tests/
  experiments/              # runner A/B/C, judge, ekspor CSV
  frontend/src/
    stage/                  # halaman /stage
    operator/               # panel operator
    audio/                  # WebAudio, ducking, antrean
    avatar/                 # three.js, VRM, lip-sync, ekspresi
  data/
    clock/  persona/  tema/  audio_static/  music_fallback/
```

## 12. Desain eksperimen skripsi [Usulan]

**Hipotesis:** percakapan antar LLM yang dimediasi supervisor mengurangi identity drift. [Keputusan]

**Kondisi uji**

- **A:** tanpa supervisor (dua LLM langsung berbicara).
- **B:** persona di-prompt ulang pada setiap giliran, tanpa supervisor. Kondisi ini penting agar perbaikan terbukti berasal dari mekanisme supervisor, bukan sekadar penyuntikan ulang persona.
- **C:** supervisor penuh (deteksi drift, koreksi memori, regenerasi).

**Prosedur**

- Simulasi teks saja (tanpa TTS dan avatar), diulang puluhan kali, dijalankan lewat FR-12.
- Satu sesi setara satu jam siaran; slot Talk adalah unit pengukuran.
- Catatan desain: rundown live 1 jam hanya punya 6 slot Talk (sekitar 16 menit bicara, kira-kira 40 sampai 60 giliran per sesi menurut estimasi kasar), sedangkan paper memakai 36 tema dengan tiga snapshot. Snapshot per slot hanya memberi 6 titik ukur, dan jeda musik antar slot membuat setiap slot pendek. Pertimbangkan snapshot tiap N giliran, atau rangkaian Tema yang lebih panjang untuk simulasi (misalnya menggabungkan beberapa jam clock). Putuskan bersama pembimbing.
- Ukuran sampel awal: sekitar 10 sesi per kondisi, sesuaikan dengan kuota.

**Metrik**

- Skor konsistensi persona oleh LLM-judge di beberapa snapshot (rubrik per jenis drift pada FR-3).
- Jumlah dan jenis drift yang terdeteksi per sesi, jumlah regenerasi, serta overhead latensi.
- Kuesioner gaya PsychoBench jika waktu cukup.
- Penilaian manusia dari beberapa orang (misalnya staf HITS).
- Uji statistik seperti paper rujukan (Friedman atau ANOVA dengan post-hoc).

Kalibrasi LLM-judge dengan sampel yang dinilai manusia sebelum dipercaya.

## 13. Jadwal 12 minggu (mulai Senin, 5 Oktober 2026) [Usulan]

**Fase 1 mencakup minggu 1 sampai 4**, ditambah runner eksperimen teks (FR-12) dan UI ringkas (Session Console, Persona Editor, Tema Library, TTS Lab). Minggu 5 sampai 12 adalah Fase 2 dan baru dikerjakan setelah Fase 1 selesai. Karena avatar, musik, dan TikTok ditunda, ada ruang untuk memperdalam eksperimen skripsi lebih awal.

| Minggu | Fokus | Hasil | FR |
|---|---|---|---|
| 1 | Scope, repo, kartu persona, parser Tema dan clock | JSON rundown, uji batas rate Gemini | FR-1 |
| 2 | Loop dua agen versi teks | Kondisi A berjalan, skema log siap | FR-3, FR-11 |
| 3 | Supervisor v1 | Kondisi B dan C berjalan | FR-3 |
| 4 | TTS dua suara | Tes naturalness ke 3 sampai 5 pendengar | FR-4 |
| 5 | Orchestrator dan UI operator | Sesi 15 menit versi audio saja | FR-2, FR-6, FR-8 |
| 6 | Musik berbasis emosi dan ducking | Keputusan lisensi musik | FR-7 |
| 7 | Avatar v1 | Dua VRM, lip-sync amplitudo, uji performa laptop | FR-5 |
| 8 | Avatar v2 | Ekspresi dari tag emosi, tata letak scene | FR-5, FR-9 |
| 9 | Integrasi end to end 15 menit | Perbaikan latensi, prefetch, fallback | FR-10 |
| 10 | TikTok LIVE Studio | Tes tangkap jendela dan audio, uji 30 menit | FR-9 |
| 11 | Rehearsal 1 jam penuh | Eksperimen A/B/C berjalan paralel | FR-12 |
| 12 | Hardening dan demo ke stakeholder | Draf hasil untuk skripsi dan laporan KP | semua |

Dari minggu 7, avatar dan simulasi eksperimen berjalan paralel. Jika jadwal mundur, pangkas avatar ke versi paling sederhana, bukan eksperimen skripsi.

## 14. Panduan vibe coding di Antigravity

### Prinsip kerja

1. Taruh `docs/PRD.md` dan `AGENTS.md` di root repo supaya agen memakainya sebagai konteks. Cek mekanisme file aturan (rules) yang didukung Antigravity pada versi yang kamu pakai.
2. Bangun per irisan vertikal (satu fitur dari backend sampai UI), bukan per lapisan.
3. Kembangkan semuanya dengan `LLM_MODE=mock` dan `TTS_MODE=mock` lebih dulu; baru ganti ke `live` setelah alurnya benar.
4. Satu fase per sesi agen. Minta agen menunjukkan rencana sebelum mengubah banyak file, dan jalankan tes sebelum lanjut.
5. Commit di tiap fase yang lulus AC.

### Contoh `AGENTS.md`

```markdown
# Aturan proyek HITS AI Live
- Baca docs/PRD.md sebelum mengerjakan tugas apa pun. Kerjakan hanya FR yang diminta.
- Semua model lewat antarmuka di backend/app/llm; ID model hanya dari .env.
- Semua keluaran LLM yang diparse harus memakai structured output + validasi pydantic.
- Jangan pernah menaruh API key di frontend atau repo.
- Setiap modul baru wajib punya mode mock dan minimal satu tes.
- Jangan menambah dependensi tanpa menyebut alasannya.
- Tulis log JSONL sesuai skema di PRD bagian 10.
- Komentar kode dan nama variabel dalam bahasa Inggris; teks UI dan prompt persona dalam bahasa Indonesia.
```

### Urutan prompt per fase

| Fase | Prompt awal ke agen (ringkas) |
|---|---|
| Minggu 1 | "Scaffold repo sesuai PRD bagian 11. Implementasikan FR-1: validator skema clock, parser docx ke JSON dengan Gemini structured output, dan klien Gemini dengan rate limiter serta mode mock." |
| Minggu 2 | "Implementasikan loop dua persona versi teks (kondisi A) dengan kartu persona dan logger JSONL sesuai bagian 10. Sertakan CLI untuk menjalankan satu slot Talk." |
| Minggu 3 | "Tambahkan supervisor (FR-3): verdict terstruktur, ledger fakta, regenerasi maksimal 2 kali. Tambahkan kondisi B dan C ke runner eksperimen." |
| Minggu 4 | "Implementasikan TTSProvider (gemini dan elevenlabs), pemecahan segmen berdasarkan `/` dan `//`, dan cache audio." |
| Minggu 5 | "Bangun orchestrator state machine dan panel operator (React) dengan WebSocket, serta audio engine dengan ducking." |
| Minggu 7 sampai 8 | "Buat halaman /stage dengan dua avatar VRM di three.js, lip-sync amplitudo dari AnalyserNode, ekspresi dari tag emosi, dan idle animation." |
| Minggu 9 | "Tambahkan prefetch giliran berikutnya, fallback, dan `FAIL_INJECT` untuk menguji kegagalan." |

Tinjau diff agen dengan teliti pada bagian supervisor dan skema log, karena itu yang menopang skripsi.

## 15. Risiko dan mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Lisensi musik di TikTok Live (11 lagu penuh, sekitar 33 dari 60 menit) | Live bisa bermasalah, berbeda dari siaran radio; API yang hanya memberi cuplikan tidak cukup | Tanyakan ke HITS sebelum minggu 6; cadangan: musik bebas royalti atau hanya rekomendasi tanpa memutar lagu |
| Performa laptop (MX250) | TikTok LIVE Studio, browser, dan 3D berjalan bersamaan | Uji beban dini; avatar seringan mungkin; mode kualitas rendah |
| Batas laju Gemini free tier | Siaran tersendat | Cek limit di minggu 1; rate limiter, prefetch, pertimbangkan tier berbayar untuk rehearsal dan eksperimen |
| Model di-deprecate atau alias berganti | Perilaku berubah di tengah proyek | ID model di `.env`, pin versi untuk eksperimen, catat model di log |
| Ketentuan free tier (data masukan dapat dipakai untuk perbaikan model, dan pemakaian komersial dibatasi) | Masalah privasi atau kepatuhan | Hanya kirim materi non-sensitif; cek ketentuan terbaru dan status program HITS |
| Latensi akibat supervisor | Jeda terasa | Prefetch; slot lagu dan jingle menutup jeda |
| Stabilitas 60 menit | Siaran mati di tengah | Fallback audio, uji rehearsal berulang, kill switch |
| Aturan konten AI TikTok | Live diblokir atau dilabeli | Konfirmasi ke HITS dan baca aturan terbaru sebelum minggu 10 |
| Kualitas suara bahasa Indonesia | Terdengar robotik | Tes naturalness minggu 4; ganti provider lewat `TTS_PROVIDER` |
| Lisensi model VRM | Tidak boleh dipakai untuk siaran | Pakai model buatan sendiri atau berlisensi jelas |
| Jadwal tidak muat | KP terlambat | Pangkas avatar, bukan eksperimen skripsi |

## 16. Keputusan terbuka

Selesaikan dalam 1 sampai 2 minggu pertama:

1. **Lisensi musik** dan sumber lagu bersama HITS (menentukan API musik yang dipakai).
2. **Akun TikTok** yang dipakai dan syarat live-nya.
3. **Persona fiktif atau meniru penyiar nyata** (usulan: fiktif).
4. **Anggaran API** untuk LLM dan TTS.
5. **Pustaka avatar 3D dan lip-sync.**
6. **Penyedia TTS:** Gemini TTS (satu key, mungkin gratis) atau ElevenLabs (keputusan sebelumnya, kualitas perlu diuji). Usulan: mulai dari Gemini TTS, putuskan setelah tes naturalness minggu 4.
7. **ID model Gemini** untuk tiap peran (cek AI Studio saat implementasi).
8. **Desain snapshot eksperimen** (bagian 12) bersama pembimbing.
9. **Blok clock yang dijadikan dasar** (usulan: 07.00 sampai 08.00) dan **jam tayang live sebenarnya** (menentukan rekaman time signal).
10. **Sumber audio dan naskah P.S.A**, serta apakah Greetings Artis dan Image/Mashup boleh dipakai di TikTok Live.

## 17. Definition of Done

### Fase 1 (conversational AI + TTS)

- [ ] Dua persona fiktif berbicara bergantian pada Tema `scripted` dan `improv` selama minimal 10 menit tanpa error.
- [ ] Supervisor menghasilkan verdict terstruktur tiap giliran, dan koreksi serta regenerasi tercatat di log.
- [ ] Kondisi A, B, dan C dapat dijalankan lewat runner eksperimen dan menghasilkan log sesuai skema.
- [ ] TTS menghasilkan suara pria dan wanita bahasa Indonesia; jeda `/` dan `//` terdengar; cache bekerja.
- [ ] Tes naturalness dengan 3 sampai 5 pendengar sudah dilakukan dan hasilnya menentukan provider TTS.
- [ ] Giliran berikutnya diproduksi lebih dulu (prefetch) sehingga jeda antar ucapan rata-rata 2 detik atau kurang.
- [ ] Kegagalan LLM atau TTS yang disimulasikan lewat `FAIL_INJECT` tidak menghentikan sesi.
- [ ] Session Console menampilkan transkrip, audio, verdict supervisor, dan latensi secara langsung.

### MVP penuh (Fase 2)

- [ ] Clock "Pagi Bener" dan Tema ter-parse ke JSON valid.
- [ ] Sesi 1 jam berjalan sesuai clock di mode live, dua kali berturut-turut, tanpa crash.
- [ ] Dua suara natural, lulus tes naturalness.
- [ ] Dua avatar dengan lip-sync dan ekspresi, minimal 30 FPS di laptop target.
- [ ] Rekomendasi musik berdasarkan emosi berjalan dengan fallback.
- [ ] `/stage` tertangkap TikTok LIVE Studio (video dan audio) dan diuji live minimal 30 menit.
- [ ] Fallback terbukti lewat `FAIL_INJECT`.
- [ ] Log dan runner eksperimen menghasilkan data kondisi A/B/C.
- [ ] Demo ke stakeholder HITS terlaksana dan draf laporan KP serta hasil awal skripsi tersedia.
