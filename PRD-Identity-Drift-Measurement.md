# PRD: Modul Pengukuran Identity Drift untuk HITS AI Live (Condition A)

| | |
|---|---|
| **Versi** | 1.0 |
| **Tanggal** | 5 Oktober 2026 |
| **Pemilik** | Muhammad Favian Jiwani |
| **Repo** | `favjiw/conversational-ai` |
| **Melengkapi** | `PRD-KP-HITS-AI-Live.md` v1.0 (Condition A, LLM-to-LLM + TTS) |
| **Rujukan utama** | Choi et al. 2025, *Examining Identity Drift in Conversations of LLM Agents* (arXiv 2412.00804v2); Aron et al. 1997 (36 tema); Huang et al. 2023 (PsychoBench); Mendelson & Aboud 1999 (MFQ) |
| **Target implementasi** | Vibe coding (Antigravity), backend Python/FastAPI |

> **Catatan akses repo.** PRD ini disusun dari `PRD-KP-HITS-AI-Live.md` dan `.env.example`. Isi folder `backend/`, `frontend/`, `design/` tidak bisa dibaca saat penulisan, jadi seluruh "titik integrasi" (bagian 6) adalah asumsi yang harus dicocokkan dengan kode yang ada.

---

## 1. Ringkasan

Repo saat ini menjalankan dua penyiar AI yang berbincang (Condition A, tanpa supervisor) dan menyimpan log JSONL. Yang belum ada: **alat ukur** untuk memutuskan apakah identitas penyiar bergeser selama percakapan. PRD ini menambahkan modul *Experiment* yang mereplikasi alat ukur paper:

1. **Percakapan terstruktur 36 tema** (Aron et al.) antara dua agen LLM.
2. **Tiga snapshot** (setelah tema 12, 24, 36) tempat kedua agen mengisi **14 kuesioner psikologi (40 faktor)** berdasarkan riwayat percakapan.
3. **Uji statistik** antar snapshot (Friedman / rm-ANOVA + post-hoc Bonferroni) untuk menentukan faktor mana yang *drift*.
4. **Topic modeling (BERTopic)** pada utterance, ditambah indikator otomatis untuk pola "AI-refusal" dan kata ganti.
5. **Penyimpanan otomatis** seluruh log dan hasil ke file begitu eksperimen selesai.

Modul ini menjadi **baseline Condition A** untuk skripsi. Saat Condition B (supervisor) dibuat nanti, alat ukur yang sama dipakai tanpa perubahan.

## 2. Ruang lingkup

**Termasuk:** experiment runner (headless), snapshot & kuesioner, scoring, statistik, topic modeling, log, laporan CSV/Markdown, mode mock.

**Tidak termasuk:** supervisor/mitigasi drift, TTS dan UI live selama eksperimen, avatar, TikTok, penilai manusia. **LLM-as-judge** (ada `GEMINI_MODEL_JUDGE` di `.env.example`) hanya ekstensi opsional di luar paper, nonaktif secara default, dan hasilnya wajib diberi label "bukan bagian replikasi".

## 3. Live Mode vs Experiment Mode

Percakapan siaran tidak boleh dipakai langsung untuk pengukuran karena prompt dan format-nya berbeda dari paper. Buat mode terpisah:

| Aspek | Live Mode (sudah ada) | Experiment Mode (baru) |
|---|---|---|
| Tujuan | Siaran | Pengukuran |
| Tema | Bebas, dari control bar | **36 tema tetap**, urut, tiap tema dijawab sekali oleh tiap agen |
| System prompt | Persona penyiar | Prompt paper (bagian 5.2) + persona hanya bila kondisi persona |
| Output LLM | JSON `{text, emotion}` + penanda `/` `//` | **Teks polos**, tanpa emotion/jeda |
| TTS & UI | Ya | **Tidak** (headless) |
| Berhenti | Tombol / batas giliran | Setelah tema ke-36 |
| Bahasa | Indonesia | **Inggris** (lihat risiko R3) |
| Temperature percakapan | 0.7 | 0.7 |
| Temperature kuesioner | - | **0** |

## 4. Desain eksperimen

**Unit:** satu *conversation* = 36 tema x 2 agen = 72 utterance. Urutan per tema: Agent 1 menjawab, lalu Agent 2 menjawab dengan melihat jawaban Agent 1.

**Kondisi** (`condition_id`), seluruhnya konfigurabel di YAML:

| ID | Keterangan | Padanan paper |
|---|---|---|
| `rq1_<model>` | Tanpa persona, per model | RQ1 |
| `rq2_<model>_low` | Persona low-influence (ekstrovert, goal-oriented) | RQ2 |
| `rq2_<model>_high` | Persona high-influence (peka emosi, empatik) | RQ2 |
| `custom_raka_salsa` | Persona penyiar repo (Raka & Salsa) | Ekstensi untuk skripsi |

**Ukuran sampel.** Paper: 20 percakapan per model (RQ1), 10 per kelompok persona (RQ2), kuesioner diulang 10 kali. Sediakan dua profil:
- `full`: N=20 (RQ1) / 10 (RQ2), R=10.
- `pilot`: N=3, R=3 (untuk validasi pipeline dan demo).

**Model.** Paper memakai GPT, LLaMA 3.1, Mixtral, Qwen2. Dengan stack Gemini, efek ukuran parameter tidak dapat direplikasi persis karena ukuran model Gemini tidak dipublikasikan. Gunakan `models:` sebagai daftar `{id, provider, size_group}`; untuk Gemini isi `size_group: undisclosed` dan bandingkan tier (mis. varian ringan vs besar) sebagai *proxy*, dengan label jelas di laporan. Sediakan adapter provider OpenAI-compatible bila ingin menambah model open-source.

**Persona (RQ2).** Paper menyebut 20 persona per kelompok, dengan nama, gender, usia, dan deskripsi sifat, tetapi daftarnya tidak ada di PDF. Buat sendiri di `experiment/personas/{low,high}.yaml` dengan skema `{name, gender, age, description}`. Pasangkan persona yang mirip dalam satu percakapan (paper melakukannya untuk menghindari efek drift antar-persona beda). Cara persona disisipkan ke prompt tidak dijelaskan paper; asumsi: ditambahkan di akhir system prompt percakapan.

## 5. Kebutuhan fungsional

### FR-1: Konfigurasi eksperimen
- File YAML: `experiment_id`, `profile`, daftar `conditions`, `models`, `seed`, `temperature_conv` (0.7), `temperature_q` (0), `repeats` (R), `agents_measured` (default: `both`), `alpha` (0.05).
- Endpoint/CLI: `python -m experiment.run --config configs/pilot.yaml`.

### FR-2: Conversation runner
Alur per conversation:
1. Muat 36 tema dari `data/themes_aron1997.json` (ekstrak dari Appendix B.1 paper).
2. Untuk tema *t*: Agent 1 menjawab, lalu Agent 2.
3. Format pesan (Appendix B.2): jawaban agen itu sendiri berperan `assistant`, jawaban partner berperan `user`; tema disuplai sebagai `user` berformat `Question {t} : {tema}`. Riwayat dirender dari sudut pandang agen yang sedang menjawab.
4. Simpan tiap utterance segera setelah dihasilkan.

> **Perhatian data.** Teks Theme 34 di PDF rusak (terduplikasi dengan Theme 33). Ambil redaksi aslinya dari Aron et al. (1997) dan catat di `themes_aron1997.json` bahwa itu koreksi.

**5.2 System prompt percakapan (Appendix B.2):**
```
You are now sharing your thoughts on the question with your partner.
You only reply briefly to your thoughts only for a given question.
```

### FR-3: Snapshot & kuesioner
- Snapshot setelah tema 12, 24, 36 (riwayat dipotong sampai tema tersebut).
- Setiap snapshot: untuk tiap agen terukur, tiap kuesioner, tiap repeat 1..R, kirim satu panggilan LLM dengan temperature 0. Prompt (Appendix B.3):
```
Your name is assistant.
Considering the next conversation between user and assistant,
answer given descriptions.
------
[CHATHISTORY]
------
[Questionnaire Setup]
```
- `[Questionnaire Setup]` = butir dan panduan skor dari **PsychoBench** (repo resmi CUHK-ARISE/PsychoBench; periksa lisensi dan versi sebelum menyalin). Butir MFQ-FF diambil dari Mendelson & Aboud (1999). **Jangan mengarang butir kuesioner.** Simpan di `experiment/questionnaires/*.json` dengan skema `{id, items[], scale, reverse_items[], subscales{name: item_ids}, aggregation}`.
- Parser: ekstrak jawaban per butir; bila gagal, retry hingga 3 kali, lalu tandai `parse_ok=false` dan keluarkan dari analisis (hitung rasio gagal per kuesioner).

### FR-4: Scoring (40 faktor)

| Aspek (jumlah faktor) | Kuesioner -> faktor |
|---|---|
| Personality (12) | BFI: O, C, E, A, N. EPQ-R: E, P, N, L. DTDD: Machiavellianism, Psychopathy, Narcissism |
| Interpersonal (17) | BSRI: Masculine, Feminine. CABIN: R, I, A, S, E, C. ICB: Overall. ECR-R: Anxiety, Avoidance. MFQ-FF: Stimulating companionship, Help, Intimacy, Reliable alliance, Self-validation, Emotional security |
| Motivation (5) | GSE: Overall. LOT-R: Overall. LMS: Rich, Motivator, Important |
| Emotion (6) | EIS: Overall. WLEIS: Self-emotion, Others' emotion, Use of emotion, Regulation. Empathy: Overall |

Skor memakai aturan PsychoBench (butir reverse, agregasi subskala) secara otomatis, tanpa penilaian manual.

### FR-5: Analisis statistik
Untuk setiap `condition x agen x faktor`, bentuk tabel berpasangan skor pada snapshot 12, 24, 36 (kunci pasangan: `conv_id, agent, repeat`; paper tidak menjelaskan eksplisit unit sampelnya, ini asumsi yang perlu diverifikasi).
1. Uji normalitas (Shapiro-Wilk). Bila normal: **rm-ANOVA**; bila tidak: **Friedman**.
2. Post-hoc: Wilcoxon signed-rank dengan koreksi **Bonferroni** (3 perbandingan: 12-24, 24-36, 12-36). Untuk cabang ANOVA paper memakai Tukey, tetapi Tukey bawaan pingouin tidak untuk data berpasangan; gunakan paired t-test + Bonferroni dan catat sebagai **deviasi** di laporan.
3. Keluaran per faktor: statistik uji, p, selisih rata-rata Delta(12,24), Delta(24,36), Delta(12,36) beserta bintang signifikansi (format seperti Tabel 10-15 paper).
4. **Flag konsisten** = Friedman/ANOVA tidak signifikan **dan** tidak ada post-hoc signifikan (sesuai keterangan Tabel 3: tidak signifikan di kedua uji).
5. **Metrik utama:** jumlah faktor konsisten per aspek (dari 12/17/5/6) dan total (dari 40), per kondisi. Ini replikasi **Tabel 3**. Semakin kecil, semakin besar drift.

**Kasus degenerate.** Pada temperature 0, 10 pengulangan sering menghasilkan jawaban identik sehingga varians nol dan uji tidak terdefinisi. Tandai `degenerate=true`, jangan tampilkan p-value, hitung sebagai konsisten, dan laporkan jumlahnya terpisah. Catat juga variansi antar-repeat sebagai diagnostik.

### FR-6: Analisis kualitatif (topic modeling)
- BERTopic, unit = satu utterance, hanya jawaban hasil generate (tanpa prompt).
- Stop-word dihapus, embedding berbahasa Inggris, `min_topic_size=50`. Jalankan terpisah per kelompok (ukuran/tier, famili, persona low vs high). Ambil 10 topik teratas, petakan ke tema asli lewat tema mayoritas dokumen dalam topik, simpan kata representatif dan satu contoh kalimat.
- Dengan data pilot (N kecil) `min_topic_size=50` tidak layak; skala-kan dengan parameter `min_topic_size_pilot` dan beri peringatan di laporan.
- **Indikator otomatis suplemen** (bukan metrik formal paper, beri label "proxy"):
  - *AI-refusal rate*: proporsi utterance berpola "as an AI", "language model", "I don't have personal".
  - *Pronoun-form rate*: kemunculan "I've", "I'm", "I'd", "you're", "you've" per utterance, per snapshot window (tema 1-12, 13-24, 25-36). Dipakai sebagai proxy konten fiktif yang dihipotesiskan paper sebagai pemicu drift.

### FR-7: Logging & auto-save
Begitu satu conversation selesai dan begitu seluruh eksperimen selesai, tulis file ke disk tanpa aksi manual. Struktur:

```
logs/experiments/{experiment_id}/
  config.snapshot.yaml
  conversations/{condition_id}/conv_{nn}.jsonl
  questionnaires/{condition_id}/conv_{nn}.jsonl
  results/
    factor_scores.csv
    stats_by_factor.csv
    consistency_summary.csv      # replikasi Tabel 3
    topics_{group}.csv
    proxy_indicators.csv
    report.md
  manifest.json                  # versi, model, seed, waktu mulai/selesai, jumlah panggilan
```
Tulis JSONL secara inkremental (per baris) agar tidak hilang bila proses berhenti.

### FR-8: Ketahanan & uji
- Retry dengan exponential backoff untuk rate limit (Gemini free tier).
- **Resume**: eksperimen dapat dilanjutkan dari checkpoint (lewati conversation/snapshot yang sudah lengkap).
- Pakai `LLM_MODE=mock|live` dan `FAIL_INJECT=llm` yang sudah ada. Mode mock harus menghasilkan jawaban Likert deterministik dengan seed sehingga pipeline end-to-end bisa dites tanpa kuota API.
- Tambahkan skenario mock "drift sintetis" (skor naik tetap antar snapshot) untuk memverifikasi bahwa uji statistik memang mendeteksi drift.

### FR-9: Laporan
`report.md` otomatis: ringkasan konfigurasi, tabel konsistensi per aspek (replikasi Tabel 3), tabel statistik per faktor, topik teratas, indikator proxy, rasio gagal parse, jumlah kasus degenerate, dan daftar deviasi dari paper.

## 6. Arsitektur & titik integrasi (verifikasi dengan kode)

```
backend/
  experiment/
    run.py                  # CLI + endpoint
    config.py
    runner.py               # FR-2, memakai ConversationEngine bila bisa dipakai ulang
    snapshot.py             # FR-3
    questionnaires/*.json
    scoring.py              # FR-4
    stats.py                # FR-5 (pingouin, scipy, statsmodels, pandas)
    topics.py               # FR-6 (bertopic)
    proxies.py
    report.py               # FR-9
    data/themes_aron1997.json
    personas/{low,high}.yaml
  logs/experiments/...
```
- Gunakan kembali klien Gemini dan Session Logger yang sudah ada; yang baru hanya orkestrasi, kuesioner, dan analisis.
- Experiment Mode **tidak** boleh mengubah perilaku Live Mode.
- Frontend: tidak wajib. Bila ingin, cukup satu panel read-only "Hasil Eksperimen" yang membaca `results/*.csv`, di luar DoD.

## 7. Skema data

**Utterance** (`conversations/*.jsonl`):
`{experiment_id, condition_id, conv_id, theme_idx, agent (1|2), role, text, model, temperature, persona_id|null, ts, latency_ms, tokens_in, tokens_out}`

**Respons kuesioner** (`questionnaires/*.jsonl`):
`{experiment_id, condition_id, conv_id, agent, snapshot (12|24|36), questionnaire, repeat, raw_response, answers{item: value}, scores{factor: value}, parse_ok, retries, ts}`

## 8. Variabel environment tambahan
```
EXPERIMENT_PROFILE=pilot            # pilot | full
EXPERIMENT_OUT_DIR=logs/experiments
QUESTIONNAIRE_REPEATS=3             # override R
MAX_CONCURRENCY=2
GEMINI_MODEL_CONV=                  # model agen percakapan
GEMINI_MODEL_QUESTIONNAIRE=         # boleh sama dengan agen terukur
```
Catatan desain: kuesioner harus dijawab oleh **model yang sama** dengan agen yang diukur (self-report seperti paper).

## 9. Estimasi beban panggilan LLM

Per conversation = 72 (percakapan) + 3 snapshot x 14 kuesioner x R x A (agen terukur).

| Profil | N | R | A | Panggilan/conversation | Total per kondisi |
|---|---|---|---|---|---|
| pilot | 3 | 3 | 2 | 324 | **972** |
| full (RQ1) | 20 | 10 | 2 | 912 | **18.240** |

Asumsi satu panggilan per kuesioner per repeat (butir diberikan sekaligus). Profil `full` untuk satu kondisi saja sudah besar untuk free tier; jalankan `pilot` dulu, lalu naikkan bertahap dengan fitur resume.

## 10. Risiko & keputusan terbuka

- **R1. Validitas self-report.** Skor kuesioner adalah jawaban LLM terhadap kuesioner setelah membaca konteks panjang, sehingga perubahan skor bisa mencerminkan cara menjawab, bukan perilaku bicara. Catat sebagai keterbatasan; untuk skripsi pertimbangkan pembanding tambahan (proxy FR-6 atau judge opsional).
- **R2. Sumber butir kuesioner.** Butir dan skoring harus diambil dari PsychoBench/aslinya. Pastikan lisensi dan versi cocok dengan paper.
- **R3. Bahasa.** Kuesioner, tema, dan embedding BERTopic paper berbahasa Inggris. Jalankan eksperimen utama dalam bahasa Inggris. Versi Indonesia (siaran HITS) hanya ekstensi, dengan embedding multibahasa dan catatan bahwa instrumen tidak tervalidasi di sana.
- **R4. Temperature 0 -> degenerate** (lihat FR-5). Putuskan apakah tetap mengikuti paper (R=10 pada T=0) atau menambah varian T>0 sebagai analisis sensitivitas.
- **R5. Unit sampel uji statistik** tidak dijelaskan eksplisit di paper. Asumsi di FR-5; dokumentasikan sebagai deviasi bila berbeda.
- **R6. Jumlah kuesioner.** Teks utama paper menyebut 14, Appendix A menyebut 15; daftar aktual yang tercantum berjumlah 14 (40 faktor). PRD ini memakai 14.
- **R7. Tier Gemini bukan proxy sempurna** untuk parameter size; jangan mengklaim replikasi temuan "model besar lebih drift" tanpa label ini.

## 11. Milestone & Definition of Done

1. **M1 (kerangka):** config, themes, runner 36 tema, log JSONL inkremental, mode mock.
2. **M2 (pengukuran):** snapshot, 14 kuesioner + parser + scoring 40 faktor.
3. **M3 (analisis):** statistik, flag konsisten, tabel replikasi Tabel 3, kasus degenerate.
4. **M4 (kualitatif & laporan):** BERTopic, indikator proxy, `report.md`, auto-save lengkap.
5. **M5 (live pilot):** satu kondisi Gemini nyata, profil `pilot`.

**DoD**
- [ ] Mode mock menghasilkan 1 conversation dengan tepat 72 utterance, urut tema 1-36, agen 1 lalu agen 2.
- [ ] Jumlah baris respons kuesioner = 3 x 14 x R x A per conversation (di luar retry).
- [ ] 40 faktor muncul di `stats_by_factor.csv`; total count per aspek = 12/17/5/6.
- [ ] Skenario "drift sintetis" terdeteksi (faktor ditandai tidak konsisten); skenario "tanpa drift" ditandai konsisten.
- [ ] Log dan hasil tersimpan otomatis begitu eksperimen selesai, tanpa aksi manual; proses yang diputus dapat di-resume.
- [ ] `FAIL_INJECT=llm` tidak menjatuhkan seluruh eksperimen (retry lalu tandai gagal).
- [ ] `report.md` memuat daftar deviasi dari paper.
- [ ] Live Mode berjalan tanpa perubahan perilaku.
