# PRD: HITS AI Live v1.1 — Naturalness Percakapan (Live Mode)

Pemilik: Muhammad Favian Jiwani · Tanggal: 10 Oktober 2026 · Repo: `favjiw/conversational-ai` · Mitra: HITS Unikom Radio

Melengkapi: `PRD-KP-HITS-AI-Live.md` v1.0 dan `PRD-Identity-Drift-Measurement.md` v1.0. Label: **\[Keputusan\]** sudah diputuskan, **\[Usulan\]** boleh diubah.

## 1. Ringkasan dan latar belakang

Percakapan dua penyiar AI (Raka dan Salsa) pada Live Mode terdengar kurang natural. Analisis sesi `session_eea08943` (Condition A, 48 giliran, `gemini-3.5-flash-lite`, temperature 0.7) terhadap transcript on-air HITS Unikom Radio (50 menit 45 detik, ASR mentah) menunjukkan pola berikut:

| Pola pada sesi LLM | Angka |
| --- | --- |
| Salsa membuka giliran dengan "Bener banget" atau "Wah seru tuh" | 22 dari 24 giliran ("Bener banget" saja: 14) |
| "Gimana nih menurut lo" | 14 dari 48 giliran |
| "Stay tuned bareng kita" | 13 dari 48 giliran |
| Menyapa "sobat pendengar" atau "kalian" (tanpa ada yang menjawab) | 29 dari 48 giliran |
| "hahaha" ditulis literal (dibaca apa adanya oleh TTS) | 26 dari 48 giliran |
| Trigram terbanyak ("gimana nih menurut") | 14 kali dari sekitar 1.400 token (sekitar 1%); transcript on-air sekitar 0,15% |

Temuan kualitatif: struktur giliran selalu setuju, isi satu kalimat, lalu ajakan ke pendengar; giliran genap sering hanya mengulang kalimat terakhir partner; kedua persona selalu setuju dan memilih hal yang sama (kopi, kuliner, Bandung); konteks dikarang ("setelah lagu" padahal tidak ada lagu, fakta "jomblo akut" yang tidak ada di kartu persona); tema berat (firasat kematian) dijadikan lelucon.

Transcript on-air berbeda: bertumpu pada isi nyata (berita gempa BMKG, kuis, PSA lalu lintas, iklan), penyiar punya pendapat dan anekdot sendiri, ajakan interaksi konkret dan hanya sekali per segmen, ritme giliran bervariasi.

PRD ini hanya menangani satu hal: membuat percakapan langsung antara dua LLM (tanpa supervisor, Condition A) menghasilkan ucapan yang lebih natural, dengan transcript on-air HITS sebagai acuan.

## 2. Tujuan, non-tujuan, dan prinsip

### Tujuan

- **G1.** Menghilangkan pengulangan frasa dan struktur giliran yang seragam pada Live Mode.
- **G2.** Membuat kedua persona punya sudut pandang berbeda, termasuk boleh tidak setuju.
- **G3.** Mencegah konteks karangan (lagu, pendengar, cuaca, berita) yang tidak ada pada sesi.
- **G4.** Menyediakan alat ukur naturalness yang bisa dijalankan ulang pada log sesi mana pun dan pada transcript referensi.

### Non-tujuan

- Mengubah Experiment Mode (`backend/experiment/*`): prompt paper Choi et al. dan 36 tema Aron tetap apa adanya.
- Supervisor serta Condition B dan C: tidak ditambahkan dan tidak diubah; fokus hanya pada percakapan langsung dua LLM (Condition A).
- Avatar, musik berbasis emosi, otomasi TikTok.

### Prinsip

1. **Baseline dibekukan \[Keputusan\].** Prompt dan konfigurasi saat ini menjadi profil `baseline_v1` sebagai pembanding sebelum-sesudah.
2. **Perbaikan berupa profil baru `natural_v2` \[Usulan\]**, dipilih lewat konfigurasi dan dicatat di setiap log giliran.
3. **Tanpa supervisor \[Keputusan\].** Hanya dua LLM persona yang berbicara; tidak ada panggilan LLM tambahan, dan pemeriksaan tambahan murni berbasis kode.
4. **Variasi dikendalikan dari kode**, bukan hanya dari kalimat di prompt, karena model kecil menurut pada contoh di riwayat percakapan.

## 3. Metrik keberhasilan

Target bersifat **\[Usulan\]**; angka baseline untuk metrik yang belum diukur ditetapkan di milestone M1.

| Metrik | Baseline (`session_eea08943`) | Target `natural_v2` |
| --- | --- | --- |
| Porsi pembuka giliran terbanyak per persona | 58% ("Bener banget" pada Salsa) | 25% atau kurang |
| Frasa catchphrase per persona | sekitar 1 per giliran | 1 per 6 giliran atau kurang |
| Giliran yang menyapa pendengar atau diakhiri pertanyaan | 29 dari 48 (60%) | 20% atau kurang, hanya di giliran penutup tema |
| Porsi trigram terbanyak | sekitar 1% | 0,4% atau kurang (referensi on-air sekitar 0,15%) |
| "hahaha" tertulis | 54% giliran | 0 |
| Konteks karangan (lagu, pendengar, cuaca tanpa sumber) | 3 kasus pada 48 giliran | 0 pada tinjauan manual 5 sesi |
| Echo rate (giliran yang mengulang klausa terakhir partner) | diukur di M1 | turun lebih dari 50% dari baseline |
| Variasi panjang giliran (koefisien variasi jumlah kata) | diukur di M1 | naik dibanding baseline |
| Penilaian manusia (skala 1 sampai 5, 3 sampai 5 pendengar, buta profil) | belum ada | rata-rata `natural_v2` lebih tinggi dari `baseline_v1`, minimal 3,5 |

Catatan metrik: jangan memakai type-token ratio (TTR). Nilainya 0,27 di kedua teks tetapi bergantung panjang teks (1.400 vs 6.500 token), jadi tidak sebanding.

## 4. Akar masalah dan pemetaan ke kebutuhan

| Akar masalah (lokasi) | Dampak | FR |
| --- | --- | --- |
| `generate_aron_themes.py`: guidance berbunyi "beri tanggapan hangat, dan selipkan guyonan khas siaran radio hits" | Memerintahkan setuju dan melucu: sumber "Bener banget" dan "hahaha" | FR-2 |
| `main.py`: catchphrase default ("Bener banget!", "Wah seru tuh!", "Stay tuned bareng kita!", "Gimana nih menurut lo?") ada di system prompt `build_persona_system_prompt` | Frasa masuk riwayat lalu ditiru (self-reinforcing) | FR-3 |
| `build_persona_turn_prompt` hanya berisi "Sekarang giliranmu bicara" | Giliran tanpa tujuan komunikatif, model memilih jawaban paling aman | FR-4, FR-5 |
| `background_facts` tipis, `topic_limits` berisi "Kultur pop, Gaya hidup, Musik, Kota" dibaca sebagai daftar topik wajib, prompt "HANYA fakta ini yang boleh disebut" | Semua topik ditarik ke kopi, kuliner, Bandung | FR-6 |
| Konteks sesi tidak diberi tahu (tidak ada lagu, pendengar, cuaca, berita) | Konteks dikarang | FR-7 |
| Tema Aron dibacakan verbatim dan dirotasi tiap 6 giliran | Giliran 3 sampai 6 menjadi pengisi; tema berat dibawakan sebagai lelucon | FR-8 |
| Prompt "2-4 kalimat", aturan jeda `/`, teks "hahaha" dibaca TTS | Panjang seragam, ritme terpotong | FR-9 |
| Model `flash-lite` pada temperature 0.7, tanpa parameter anti-repetisi | Repetisi lebih mudah terjadi | FR-10 |
| Belum ada alat ukur naturalness | Perbaikan tidak bisa dibuktikan | FR-11, FR-12 |

## 5. Kebutuhan fungsional

Prioritas: **P0** wajib, **P1** penting, **P2** opsional.

### FR-1 Profil prompt (P0)

- Tambah `PROMPT_PROFILE=baseline_v1 | natural_v2` di `.env` dan `config.py`; field opsional `prompt_profile` pada `StartSessionRequest`.
- `baseline_v1` mereproduksi perilaku sekarang persis (system prompt, guidance Aron, persona default).
- Semua builder prompt di `conversation/engine.py` menerima profil dan memilih templat yang sesuai.
- **AC:** pada mode mock, `baseline_v1` menghasilkan prompt identik byte-per-byte dengan prompt sebelum perubahan (tes regresi).

### FR-2 Guidance tema baru (P0)

- `generate_aron_themes.py` menghasilkan field baru `guidance_v2`; `guidance` lama tetap untuk `baseline_v1`.
- Templat `guidance_v2`: sebutkan pertanyaan sebagai bahan obrolan, bukan kuis. Tanpa "tanggapan hangat" dan "guyonan". Contoh: "Jawab dengan pengalaman atau pendapat spesifik milikmu. Boleh tidak setuju atau menggoda partner. Jangan memuji pertanyaan atau mengulang ucapan partner."
- `load_aron_themes()` di `main.py` memilih `guidance` atau `guidance_v2` sesuai profil.
- **AC:** tidak ada kata "tanggapan hangat" dan "guyonan" pada `guidance_v2` (tes string).

### FR-3 Penjadwal catchphrase (P0)

- Pada `natural_v2`, daftar catchphrase dihapus dari system prompt.
- Kode menyuntikkan satu catchphrase ke prompt giliran dengan peluang 1/6, dengan cooldown 6 giliran per persona dan maksimal sekali per tema. Seed dicatat di log.
- **AC:** pada 100 giliran mock, tidak ada persona yang memakai catchphrase lebih dari sekali per 6 giliran.

### FR-4 Sampler dialog act (P0)

- Daftar dialog act **\[Usulan\]**: `anecdote` (cerita pengalaman spesifik), `opinion_diff` (berbeda pendapat dengan alasan), `new_fact` (tambah satu fakta atau detail baru), `personal_question` (tanya hal personal ke partner), `tease` (menggoda ringan), `short_react` (satu kalimat pendek), `transition` (pindah sub-topik), `wrap_up` (penutup tema, satu-satunya act yang boleh menyapa pendengar).
- Tiap giliran diundi satu act dengan aturan: tidak sama dua giliran berturut-turut, `wrap_up` hanya pada giliran terakhir tema, dan act dicatat di log.
- Prompt giliran memuat baris "Tugas giliran ini: ..." menggantikan "Sekarang giliranmu bicara".
- Panjang giliran ikut diundi (satu kalimat 8 sampai 15 kata, sedang, panjang sampai sekitar 60 kata); aturan "2-4 kalimat" dihapus pada `natural_v2`.
- **AC:** pada 50 giliran mock, tidak ada dua giliran berurutan dengan act sama, dan `wrap_up` hanya muncul di giliran terakhir tema.

### FR-5 Anti-repetisi (P0)

- Konteks: hitung pembuka (3 kata pertama) dan penutup (3 kata terakhir) dari 6 giliran terakhir, lalu tambahkan "Jangan membuka atau menutup dengan: ..." ke prompt.
- Pemeriksa leksikal ringan setelah generate: jika pembuka cocok dengan daftar larangan atau ada trigram yang muncul 3 kali atau lebih dalam 10 giliran terakhir, regenerasi maksimal 1 kali. Hitung di `TurnLog.regenerations` dan field baru `guard_regenerations`.
- Ini **bukan** supervisor: murni kode tanpa panggilan LLM tambahan, tidak menilai drift persona.
- Dampak kuota: regenerasi menambah panggilan; batas RPM default 5 di `main.py` perlu dicek ulang.
- **AC:** pada sesi mock berpola repetitif, pemeriksa memicu regenerasi dan sesi tetap selesai; jumlah regenerasi tercatat.

### FR-6 Persona yang lebih kaya (P0)

- Pindahkan definisi persona default dari `main.py` (terduplikasi di `start_session` dan `start_clock_session`) ke `data/persona/raka.json` dan `salsa.json`, dimuat lewat `load_persona`.
- Setiap persona punya 8 sampai 10 `background_facts` dengan detail spesifik dan selera yang **bertentangan** antar persona (contoh: Raka kopi hitam dan suka pedas; Salsa tim teh dan tidak suka pedas) **\[Usulan\]**.
- Ubah makna `topic_limits` pada prompt menjadi "Hindari topik" (bukan topik wajib); hapus "Kultur pop, Gaya hidup, Musik, Kota" sebagai pembatas.
- Ganti "HANYA fakta ini yang boleh disebut" dengan: "Fakta inti ini tetap. Detail kecil boleh diimprovisasi asal tidak bertentangan dengan fakta inti atau ucapanmu sebelumnya."
- Field opsional `opinions: list[str]` pada `PersonaCard` (kompatibel mundur).
- **AC:** kedua persona dimuat dari berkas; sesi mock `natural_v2` menunjukkan setidaknya satu giliran `opinion_diff` yang memakai selera berbeda.

### FR-7 Konteks sesi (P0)

- Tambahkan blok konteks ke prompt giliran: apakah ada lagu (dan lagu sebelumnya, jika slot sebelumnya lagu pada `ClockRunner`), apakah ada pendengar yang menjawab, dan bahwa cuaca, waktu, dan berita **tidak** tersedia kecuali diberikan lewat `tema.content`.
- Pada Live Mode tanpa lagu: larang "setelah lagu", "lagu tadi", dan "kita balik lagi setelah lagu".
- **AC:** pada 5 sesi live tanpa lagu, tinjauan manual menemukan 0 rujukan ke lagu atau cuaca tanpa sumber.

### FR-8 Tema berbasis isi dan keamanan siaran (P1)

- Tambah pustaka tema siaran `data/tema/*.json` berisi `content` nyata (berita, kuis, fakta) dengan mode `scripted`, `improv`, atau `listener_content`. `TALK_DEFAULT_TOPICS` di `clock_runner.py` (string statis) diganti agar membaca `tema.content` dari clock atau pustaka ini.
- Tema Aron tetap dipakai untuk Experiment Mode dan sebagai opsi Live Mode. Tandai tema sensitif `sensitive: true` (minimal #7, #18, #19, #24, #33, #35) dan lewati secara default pada Live Mode.
- `turns_per_theme` default menjadi 4 dan dapat dikonfigurasi; dialog act `wrap_up` menutup tema (lihat FR-4).
- **AC:** Live Mode tidak memilih tema `sensitive` kecuali diizinkan eksplisit; slot talk memakai `tema.content` bila ada.

### FR-9 Format keluaran dan TTS (P1)

- Prompt `natural_v2`: maksimal 2 penanda `/` dan 1 `//` per giliran; tidak menulis tawa tertulis ("hahaha", "hehe", "wkwk").
- `clean_text_for_tts` (`clock_runner.py`) juga menghapus tawa tertulis sebagai pengaman.
- Hasil sintesis diuji ulang dengan tes naturalness suara yang sudah ada (TTS Lab).
- **AC:** tes string pada `clean_text_for_tts` untuk "hahaha", "hehe", "wkwk".

### FR-10 Model dan sampling (P1)

- `LLMClient.generate` menerima parameter opsional `top_p`, `presence_penalty`, `frequency_penalty` yang diteruskan hanya jika bukan `None`. Dukungan per model **harus diverifikasi** di dokumentasi Gemini; jika tidak didukung, abaikan dengan peringatan log.
- Eksperimen kecil: `flash-lite` vs satu model lebih besar, temperature 0.7 vs 1.0, dengan profil `natural_v2`; pilih konfigurasi lewat metrik FR-11.
- Nilai default tetap lewat `.env` (jangan hardcode ID model).
- **AC:** `MockLLMClient` tetap deterministik; tes `test_llm.py` lulus.

### FR-11 Modul metrik naturalness (P0)

- Berkas baru `backend/experiment/naturalness.py` dan CLI: `python -m experiment.naturalness --session logs/session_X.jsonl [--reference data/reference/hits-sore.txt] --out report.md`.
- Metrik: porsi pembuka terbanyak per persona, jumlah dan porsi frasa (catchphrase) per giliran, porsi trigram terbanyak, distinct-2, echo rate, porsi giliran berakhir pertanyaan atau menyapa pendengar, tawa tertulis, variasi panjang giliran (rata-rata, minimum, maksimum, koefisien variasi), jumlah regenerasi.
- Keluaran CSV, JSON, dan Markdown, dengan label peringatan bila referensi tanpa label pembicara.
- **Tes regresi:** fixture `session_eea08943.jsonl` harus menghasilkan nilai yang sama dengan bagian 1 (22 dari 24 pembuka Salsa, 14 dari 48 "gimana nih menurut lo", dan seterusnya).
- **AC:** CLI berjalan pada log lama dan baru; tes regresi lulus.

### FR-12 Korpus referensi on-air (P1)

- Transkripsi ulang audio on-air dengan Whisper dan diarization, atau pelabelan manual, agar metrik per pembicara bisa dihitung; transcript ASR mentah hanya untuk metrik tingkat teks.
- Simpan hanya teks di `data/reference/` (audio tidak masuk repo). Konfirmasi izin penggunaan rekaman dan transcript ke HITS.
- **AC:** minimal 10 menit referensi berlabel pembicara; `--reference` menghasilkan perbandingan.

### FR-13 Logging dan perbaikan kecil (P1)

- `TurnLog` ditambah field dengan nilai default (kompatibel mundur): `prompt_profile`, `dialog_act`, `catchphrase_injected`, `guard_regenerations`, `seed`.
- Frontend dan tes membaca `latency_ms.total`, tetapi `LatencyMs` tidak punya field itu (tampil 0 ms). Tambahkan `total` sebagai jumlah `persona + supervisor + tts`.
- **AC:** log lama tetap bisa dibaca `SessionLogger.read_logs`; `latency_ms.total` terisi.

## 6. Berkas yang terdampak

| Berkas | Perubahan |
| --- | --- |
| `backend/app/conversation/engine.py` | Profil prompt, sampler dialog act, catchphrase scheduler, konteks sesi, pemeriksa anti-repetisi |
| `backend/app/main.py` | `prompt_profile`, persona dari berkas, pilih `guidance_v2`, `turns_per_theme` default 4, filter tema sensitif |
| `backend/app/data/generate_aron_themes.py` dan `aron_themes_id.json` | Field `guidance_v2` dan `sensitive` |
| `backend/app/schemas.py` | Field baru `TurnLog`, `LatencyMs.total`, `PersonaCard.opinions` |
| `backend/app/config.py` dan `.env.example` | `PROMPT_PROFILE`, parameter sampling |
| `backend/app/llm/client.py` | `top_p`, `presence_penalty`, `frequency_penalty` opsional |
| `backend/app/orchestrator/clock_runner.py` | `tema.content` menggantikan `TALK_DEFAULT_TOPICS`, `clean_text_for_tts` untuk tawa |
| `backend/app/data/persona/*.json`, `backend/app/data/tema/*.json` | Berkas baru |
| `backend/experiment/naturalness.py` dan `backend/tests/` | Modul metrik, tes regresi, tes profil |

Experiment Mode (`backend/experiment/runner.py`, `snapshot.py`, dan prompt paper) **tidak diubah**.

## 7. Rencana pengujian dan evaluasi

1. **Unit test:** seluruh AC di atas; `MockLLMClient` dan semua tes yang ada tetap lulus.
2. **Evaluasi otomatis:** untuk tiap konfigurasi (profil × model × temperature), jalankan minimal 5 sesi × 48 giliran dengan seed berbeda; hitung metrik FR-11 dan bandingkan dengan baseline dan referensi.
3. **Evaluasi manusia:** 3 sampai 5 pendengar menilai cuplikan transkrip atau audio secara buta (acak `baseline_v1` vs `natural_v2`), skala 1 sampai 5 untuk naturalness dan satu pertanyaan "mana yang lebih mirip penyiar sungguhan".
4. **Pemeriksaan konsistensi persona:** pada `natural_v2`, ukur ulang pelanggaran fakta inti dengan tinjauan manual (persona sekarang lebih longgar, lihat risiko R1).
5. Satu sesi dengan satu seed tidak cukup untuk klaim; semua klaim diambil dari agregat beberapa sesi.

## 8. Milestone \[Usulan\]

Tenggat skripsi: sebelum UTS semester 7 (akhir Desember 2026). Perkiraan dua sampai tiga minggu.

| Milestone | Isi | Selesai jika |
| --- | --- | --- |
| M1 | FR-1 (baseline beku), FR-11 (metrik), FR-13 | Tes regresi baseline lulus; angka baseline untuk semua metrik tercatat |
| M2 | FR-2, FR-3, FR-6, FR-7 | Prompt `natural_v2` berjalan pada sesi live; 0 konteks karangan pada 5 sesi |
| M3 | FR-4, FR-5, FR-9 | Variasi act, panjang, dan pembuka terukur membaik |
| M4 | FR-8, FR-10, FR-12 | Pustaka tema, perbandingan model, referensi berlabel |
| M5 | Evaluasi bagian 7 | Laporan perbandingan `baseline_v1` vs `natural_v2` dan penilaian manusia |

## 9. Risiko

- **R1. Naturalness vs konsistensi persona.** Melonggarkan "HANYA fakta ini" bisa menambah fabricated\_detail. Mitigasi: fakta inti tetap dan tinjauan manual terhadap pelanggaran fakta inti.
- **R2. Overfitting pada satu sesi.** Mitigasi: evaluasi multi-sesi, multi-seed.
- **R3. Referensi on-air berkualitas rendah dan tanpa label pembicara.** Mitigasi: FR-12; gunakan hanya untuk metrik tingkat teks sebelum dilabeli.
- **R4. Kuota API dan latensi.** Regenerasi pemeriksa dan sampling tambahan menambah panggilan; batas RPM default 5. Mitigasi: batas 1 regenerasi, pantau di log.
- **R5. Metrik bisa "dikelabui".** Pembuka berbeda belum tentu lebih natural. Mitigasi: wajib disertai penilaian manusia.
- **R6. Hak atas rekaman on-air.** Mitigasi: minta izin HITS; simpan teks saja.
- **R7. Tema sensitif.** Mitigasi: flag `sensitive` dan filter default.

## 10. Keputusan terbuka

1. Apakah profil `baseline_v1` dipertahankan setelah `natural_v2` stabil, atau dihapus?
2. Daftar dialog act dan peluang catchphrase (1/6) final.
3. Konfigurasi model dan temperature yang dipilih setelah evaluasi.
4. Izin HITS untuk transcript dan audio on-air, serta siapa yang melabeli pembicara.
5. Daftar tema sensitif final dan apakah ada tema siaran nyata yang siap dari HITS.

## 11. Definition of Done

- [ ] `baseline_v1` menghasilkan prompt identik dengan sebelum perubahan (tes regresi lulus).
- [ ] Modul `naturalness` berjalan dan fixture `session_eea08943` menghasilkan angka bagian 1.
- [ ] `natural_v2` memenuhi seluruh target bagian 3 pada agregat minimal 5 sesi per konfigurasi.
- [ ] 0 konteks karangan (lagu, pendengar, cuaca tanpa sumber) pada tinjauan manual.
- [ ] Tema sensitif tidak terpilih secara default pada Live Mode.
- [ ] Penilaian manusia buta menunjukkan `natural_v2` lebih tinggi dari `baseline_v1`.
- [ ] Semua tes lama lulus; Experiment Mode tidak berubah perilaku; log lama tetap terbaca.
