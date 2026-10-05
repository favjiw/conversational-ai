# PRD: HITS AI Live — Percakapan Dua Penyiar AI (Condition A)

| | |
|---|---|
| **Versi** | 1.0 (Fokus: Conversational AI LLM-to-LLM + TTS, Single-Page UI) |
| **Tanggal** | 5 Oktober 2026 |
| **Pemilik** | Muhammad Favian Jiwani |
| **Mitra** | HITS Unikom Radio |
| **Status** | Implementasi Aktif |
| **Model AI** | Google Gemini API (LLM) + ElevenLabs / Gemini (TTS) |
| **Desain UI** | Single Page Studio (`design/code.html`) |

---

## 1. Ringkasan & Fokus Saat Ini

HITS AI Live adalah aplikasi web single-page interaktif untuk menyiarkan percakapan dua penyiar AI (Penyiar 1 pria, Penyiar 2 wanita) yang saling berbincang secara dua arah (LLM-to-LLM). 

Proyek ini berfokus pada **Kondisi A (Baseline: Percakapan Langsung Antara 2 Agent tanpa Supervisor)** sesuai rujukan eksperimen *Identity Drift in Conversations of LLM Agents* (Choi et al., 2025; Aron et al., 1997):
- **Percakapan Dua Arah:** Agent A dan Agent B bergantian merespons tema yang diberikan serta melihat riwayat perkataan lawan bicaranya.
- **Tanpa Supervisor / Intervensi Drift:** Model dibiarkan berinteraksi alami berdasarkan persona awal dan konteks percakapan.
- **Single Page UI Sesuai Desain:** Satu halaman utama terpadu tanpa tab terpisah, mencakup:
  1. Header Status Live
  2. Control Bar: Tema & Persona kedua penyiar (langsung editable inline di halaman), Durasi Siaran, Tombol Mulai/Berhenti Live
  3. Announcer Stage: Kartu Penyiar 1 dan Penyiar 2 dengan indikator giliran bicara dan waveform audio
  4. Transkrip Otomatis: Scrollable timeline giliran bicara real-time
  5. Footer Status Koneksi Engine

---

## 2. Tujuan & Lingkup

### Tujuan
- **G1.** Percakapan AI dengan AI secara natural bergantian tanpa jeda kaku.
- **G2.** Karakter persona dan tema dapat diedit langsung di control bar sebelum/saat siaran.
- **G3.** Output audio TTS untuk dua suara berbeda (pria & wanita) diputar berurutan mengikuti giliran.
- **G4.** Transkrip tampil secara real-time dan log percakapan tersimpan secara otomatis (JSONL).
- **G5.** UI single-page bersih, presisi sesuai desain di `design/code.html`.

### Non-Tujuan
- Supervisor LLM / Drift Mitigator (ditiadakan, fokus Condition A murni).
- Multi-halaman (tidak ada tab terpisah seperti Persona Editor, TTS Lab, Tema Library, Runner terpisah).
- Integrasi avatar 3D VRM (cukup avatar indikator lingkaran sesuai desain).
- Otomasi TikTok LIVE Studio.
- Clock/Orchestrator complex (hanya single conversation session).

---

## 3. Desain Percakapan (Kondisi A)

- **Agent 1 (Penyiar 1 / Raka):** Merespons tema dan membuka percakapan / membalas giliran sebelumnya.
- **Agent 2 (Penyiar 2 / Salsa):** Merespons tema dengan melihat riwayat ucapan Agent 1 dan membalas.
- **Temperature:** Default 0.7 (sesuai standar simulasi percakapan Choi et al.).
- **Format Output Tiap Giliran:** JSON terstruktur `{ "text": "...", "emotion": "neutral|happy|excited|sad|surprised|thoughtful|empathetic" }`.
- **Format Tanda Jeda:** Menggunakan `/` (jeda pendek) dan `//` (jeda panjang) untuk ritme siaran radio.

---

## 4. Kebutuhan Fungsional

### FR-1: Single Page Control & Live Management
- Input Tema percakapan (editable langsung).
- Form persona Penyiar 1 (Nama, Persona & Gaya Bicara).
- Form persona Penyiar 2 (Nama, Persona & Gaya Bicara).
- Timer durasi siaran berjalan.
- Tombol Aksi: Mulai Live / Berhenti Live.

### FR-2: Conversation Engine (Condition A)
- Siklus giliran percakapan:
  1. Slot dimulai dengan tema aktif.
  2. Penyiar 1 menghasilkan balasan berbasis tema + riwayat percakapan.
  3. Penyiar 2 membaca konteks dan membalas ucapan Penyiar 1.
  4. Proses berlanjut bolak-balik sampai tombol berhenti ditekan atau batas giliran tercapai.
- Setiap giliran menghasilkan audio via TTS (ElevenLabs / Gemini TTS).

### FR-3: Announcer Stage & Indikator Giliran
- Dua kartu penyiar berdampingan (Penyiar 1 kiri, Penyiar 2 kanan).
- Status aktif: "Sedang Berbicara" dengan ring sorotan dan animasi waveform.
- Status standby: "Menunggu giliran" / standby abu-abu saat lawan bicara sedang aktif.

### FR-4: Transkrip Real-Time
- Timeline daftar percakapan terurut dengan indikator nama penyiar, waktu menit:detik, dan teks ucapan.
- Indikator turn in-progress (dot animation / "sedang berbicara...").
- Auto-scroll ke pesan terbaru.

### FR-5: Text-to-Speech & Pemutaran Audio
- Suara pria untuk Penyiar 1 dan suara wanita untuk Penyiar 2.
- Pemutaran audio berurutan (turn-locking via audio queue di client).

### FR-6: Session Logging
- Menyimpan setiap percakapan ke file log JSONL di `logs/{session_id}.jsonl`.

---

## 5. Arsitektur Teknis

```
Frontend (React + Tailwind CSS, Single Page)
       │
       │ WebSocket / REST API
       ▼
Backend (FastAPI, Python)
       ├── ConversationEngine (Condition A)
       ├── Gemini API Client (LLM Flash)
       ├── TTS Provider (ElevenLabs / Gemini TTS)
       └── Session Logger (JSONL)
```

---

## 6. Definition of Done (DoD)
- [ ] UI single-page identik dengan rancangan `design/code.html`.
- [ ] Tema dan persona 1 & 2 dapat diedit langsung melalui Control Bar.
- [ ] Percakapan berjalan bergantian secara otomatis antara 2 LLM tanpa error.
- [ ] Audio TTS berputar sesuai giliran karakter yang aktif.
- [ ] Status visual stage (ring, badge, waveform) aktif secara tepat saat audio diputar.
- [ ] Log giliran tersimpan rapi dalam format JSONL.