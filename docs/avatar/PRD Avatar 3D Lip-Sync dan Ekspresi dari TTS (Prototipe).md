# PRD: Avatar 3D Lip-Sync dan Ekspresi dari TTS (Prototipe)

|  |  |
| --- | --- |
| **Versi** | 0.1 (draft, prototipe terpisah) |
| **Tanggal** | 11 Oktober 2026 |
| **Pemilik** | Muhammad Favian Jiwani |
| **Status** | Perencanaan |
| **Hubungan dengan proyek lain** | Terpisah dari repo HITS AI Live. Hasilnya dipakai nanti sebagai modul avatar (FR-5 PRD HITS AI Live) |
| **Alat build** | Vibe coding (Antigravity) |

Label: **\[Keputusan\]** sudah diputuskan, **\[Usulan\]** boleh diubah.

---

## 1. Ringkasan

Proyek ini adalah **prototipe kecil** untuk membuktikan satu hal: dua karakter 3D (satu pria, satu wanita) bisa digerakkan **sepenuhnya oleh sinyal AI**, tanpa manusia dan tanpa kamera face tracking. Sinyal masukannya hanya dua:

1. **Audio hasil TTS**, yang menggerakkan mulut (lip-sync).
2. **Tag emosi** (dari LLM atau dipilih manual saat uji), yang menggerakkan mimik wajah.

Ditambah animasi idle prosedural (kedip, napas, gerak kepala) agar karakter terlihat hidup. Prototipe ini sengaja **tidak** memuat LLM, orkestrator siaran, musik, atau TikTok. Semua itu ada di proyek HITS AI Live dan akan disambungkan setelah prototipe terbukti.

## 2. Latar belakang dan masalah

- HITS AI Live saat ini hanya menampilkan lingkaran inisial sebagai penanda siapa yang bicara. PRD HITS AI Live menaruh avatar 3D sebagai Fase 2 (FR-5).
- Pendekatan VTuber biasa membutuhkan manusia sebagai sumber gerak (kamera dan tracking). Di proyek ini sumber geraknya adalah audio dan teks hasil AI.
- Risiko teknis avatar (performa laptop, kualitas lip-sync, kompatibilitas model) sebaiknya diuji **terpisah dan cepat**, sebelum diintegrasikan ke sistem yang lebih besar.

## 3. Tujuan, non-tujuan, dan pertanyaan yang ingin dijawab

### Tujuan

- **G1.** Dua karakter VRM (pria dan wanita) tampil dalam satu scene three.js. \[Keputusan\]
- **G2.** Mulut hanya bergerak saat karakter itu berbicara, selaras dengan audio TTS. \[Keputusan\]
- **G3.** Ekspresi wajah berubah sesuai tag emosi dengan transisi halus. \[Keputusan\]
- **G4.** Karakter terlihat hidup saat diam dan saat mendengarkan lawan bicara (idle, kedip, menoleh, mengangguk). \[Usulan\]
- **G5.** Berjalan minimal 30 FPS di laptop target. \[Usulan\]
- **G6.** Menghasilkan keputusan berbasis data: metode lip-sync mana yang cukup baik, dan apakah avatar layak diintegrasikan. \[Keputusan\]

### Non-tujuan

- LLM, generasi dialog, supervisor, eksperimen identity drift.
- Orkestrator clock, musik, ducking, TikTok LIVE Studio.
- Membuat model 3D dari nol (memakai VRoid Studio atau model berlisensi jelas).
- Animasi tubuh penuh dan motion capture.
- Kualitas visual setara studio animasi.

### Pertanyaan yang dijawab prototipe

| # | Pertanyaan | Cara menjawab |
| --- | --- | --- |
| Q1 | Apakah lip-sync berbasis amplitudo cukup natural untuk siaran? | Uji dengar-lihat oleh 3 sampai 5 orang (bagian 9) |
| Q2 | Apakah estimasi viseme dari audio memberi peningkatan berarti dibanding amplitudo? | Bandingkan Level 1 vs Level 2 |
| Q3 | Apakah 2 model VRM + three.js stabil 30 FPS di laptop target (GPU MX250) bersamaan dengan aplikasi capture? | Ukur FPS pada tiga pengaturan kualitas |
| Q4 | Apakah satu tag emosi per giliran cukup, atau perlu emosi per kalimat? | Uji pada naskah uji dengan perubahan suasana |
| Q5 | Apakah audio dari provider TTS yang dipakai (Edge TTS) bisa dianalisis tanpa masalah lintas origin? | Uji audio dari server terpisah |

## 4. Pengguna

- **Pengembang (Favian):** menjalankan prototipe, menyetel parameter lewat panel debug, merekam hasil.
- **Penilai:** 3 sampai 5 orang (teman, staf HITS) yang melihat rekaman atau demo langsung dan mengisi skor.

## 5. Ruang lingkup

| Area | Prototipe ini | Nanti (di HITS AI Live) |
| --- | --- | --- |
| Sumber audio | File audio lokal, lalu opsional TTS via endpoint kecil | Audio dari backend HITS AI Live |
| Sumber emosi | Dipilih manual atau dari file naskah uji | Field `emotion` dari output LLM |
| Karakter | 2 model VRM (pria, wanita) | Sama |
| Halaman | Satu halaman uji dengan panel debug, plus mode bersih untuk capture | Rute `/stage` |
| Backend | Tidak wajib (Tahap A dan B). Opsional untuk TTS (Tahap C) | FastAPI yang sudah ada |

## 6. Tech stack \[Usulan\]

Versi pustaka perlu diverifikasi saat implementasi, karena ekosistemnya cepat berubah.

| Kebutuhan | Pilihan | Catatan |
| --- | --- | --- |
| Build tool | Vite | Ringan, sama dengan frontend HITS AI Live |
| UI | React atau vanilla TypeScript | React dipilih agar komponen bisa dipindah ke HITS AI Live. Untuk prototipe murni, vanilla juga cukup |
| 3D | three.js |  |
| Model karakter | VRM, dimuat dengan `@pixiv/three-vrm` | Ekspresi standar VRM 1.0: `happy`, `sad`, `angry`, `relaxed`, `surprised`, `aa`, `ih`, `ou`, `ee`, `oh`, `blink`, dan seterusnya |
| Pembuat model | VRoid Studio (gratis) atau model berlisensi | Cek lisensi untuk penggunaan siaran dan komersial |
| Audio | WebAudio API (`AudioContext`, `AnalyserNode`) |  |
| Panel debug | lil-gui atau Leva | Slider parameter secara langsung |
| Statistik performa | stats.js atau bawaan three.js | FPS dan waktu frame |
| TTS (opsional) | Edge TTS lewat skrip Python atau Node kecil | Tahap C |
| Estimasi viseme (Level 2) | Analisis spektrum sendiri atau pustaka lip-sync audio-ke-viseme | Evaluasi pustaka dan lisensinya saat Tahap D |

## 7. Kebutuhan fungsional

Prioritas: **P0** wajib, **P1** penting, **P2** opsional. AC = acceptance criteria.

### FR-1 Pemuatan dua model VRM (P0)

- Memuat dua berkas `.vrm` dari folder `public/models/` (`male.vrm`, `female.vrm`).
- Menempatkan keduanya berdampingan, menghadap kamera, dengan sedikit rotasi ke arah satu sama lain.
- Mendukung VRM 0.x dan 1.0 (nama ekspresi dinormalisasi lewat satu lapisan adaptor).
- Pencahayaan dan latar sederhana, kamera tetap. Rasio layar dapat dipilih (16:9 atau 9:16).
- **AC:** kedua karakter tampil tanpa error konsol, bayangan dan material (MToon) tampil benar.

### FR-2 Pemutar audio dan analisis (P0)

- Satu `AudioContext` global, dibuat setelah interaksi pengguna (mengatasi kebijakan autoplay browser).
- Setiap penyiar punya `AnalyserNode` sendiri. Audio giliran tertentu hanya dihubungkan ke analyser penyiar yang sedang bicara.
- Mendukung WAV dan MP3. Audio dimuat dengan `crossOrigin = 'anonymous'` agar analisis tidak kosong saat sumber berasal dari origin lain.
- Antrean giliran: giliran berikutnya baru mulai setelah event `ended` giliran sebelumnya.
- **AC:** saat audio penyiar A diputar, nilai level analyser A naik dan B tetap nol.

### FR-3 Lip-sync Level 1: amplitudo (P0)

- Hitung level RMS dari `AnalyserNode` per frame, terapkan ambang bawah (noise gate), pemulusan (attack cepat, release lebih lambat), dan skala.
- Petakan ke blendshape mulut `aa` (dan sedikit `oh`).
- Parameter dapat disetel di panel debug: gain, ambang, attack, release.
- **AC:** mulut menutup penuh dalam 150 ms setelah audio berhenti. Tidak ada gerak mulut saat senyap. Lag visual terhadap suara tidak terasa.

### FR-4 Lip-sync Level 2: estimasi viseme (P1)

- Dari spektrum audio, estimasi bentuk mulut dominan (a, i, u, e, o) dan campurkan ke blendshape `aa`, `ih`, `ou`, `ee`, `oh`.
- Dapat diaktifkan atau dimatikan dari panel debug untuk perbandingan A/B dengan Level 1.
- Tahap ini dikerjakan hanya setelah FR-3 lulus.
- **AC:** bentuk mulut bervariasi mengikuti bunyi, bukan hanya buka-tutup, tanpa kedutan (jitter) yang mengganggu.

### FR-5 Driver ekspresi dari tag emosi (P0)

- Memetakan tujuh emosi berikut ke bobot ekspresi VRM, dengan interpolasi halus (durasi transisi 200 sampai 400 ms):

| `emotion` | Ekspresi VRM (bobot awal, dapat disetel) |
| --- | --- |
| neutral | semua ekspresi 0 |
| happy | happy 0.7 |
| excited | happy 1.0, mata sedikit lebih lebar |
| surprised | surprised 0.9 |
| sad | sad 0.6 |
| thoughtful | relaxed 0.4, kepala miring, pandangan sedikit ke atas |
| empathetic | sad 0.3, relaxed 0.3, anggukan pelan |

- Ekspresi emosi tidak boleh menimpa mulut. Ekspresi wajah dan mulut digabung dengan batas total bobot agar mulut tidak terdistorsi saat ekspresi kuat.
- Emosi dapat dipilih lewat dropdown di panel debug dan lewat naskah uji (FR-8).
- **AC:** perpindahan emosi tidak melompat, dan mulut tetap terlihat normal pada semua emosi.

### FR-6 Animasi idle prosedural (P0)

- Kedip acak setiap 2 sampai 6 detik.
- Napas: gerak halus dada dan bahu.
- Gerak kepala kecil berbasis noise, sedikit lebih aktif saat berbicara.
- Gerak mata kecil (saccade), pandangan dapat diarahkan ke kamera atau ke lawan bicara.
- **AC:** karakter tidak pernah terlihat membeku selama lebih dari 2 detik.

### FR-7 Perilaku mendengarkan (P1)

- Saat penyiar lain berbicara: menoleh ke arah lawan bicara, mengangguk sesekali (interval acak), ekspresi mengikuti emosi lawan bicara dengan intensitas rendah.
- Saat giliran berganti: transisi pandangan yang halus.
- **AC:** pada rekaman dialog dua orang, penonton bisa menunjuk siapa yang sedang bicara dan siapa yang mendengarkan tanpa petunjuk teks.

### FR-8 Skenario uji dari naskah JSON (P0)

- Memuat berkas skenario berisi urutan giliran (skema pada bagian 8) dan memutarnya otomatis.
- Sediakan minimal tiga skenario uji: (a) dialog netral pendek, (b) dialog dengan perubahan emosi tajam, (c) dialog panjang 3 sampai 5 menit untuk uji stabilitas dan performa.
- Tombol putar, jeda, ulang, dan lompat ke giliran tertentu.
- **AC:** skenario (c) berjalan sampai selesai tanpa kebocoran memori yang terlihat (memori stabil di panel statistik).

### FR-9 Panel debug dan statistik (P0)

- Slider parameter lip-sync, bobot ekspresi, dan kekuatan idle.
- Pilihan Level lip-sync (1 atau 2).
- Pilihan kualitas: tinggi, sedang, rendah (pixel ratio, bayangan, antialias).
- Tampilan FPS, waktu frame, jumlah draw call, dan level audio masing-masing penyiar.
- Tombol sembunyikan panel untuk mode bersih (capture).
- **AC:** semua parameter berefek langsung tanpa memuat ulang halaman.

### FR-10 TTS lewat endpoint kecil (P1)

- Skrip kecil (Python atau Node) menerima `{text, voice}` dan mengembalikan audio, memakai Edge TTS (`id-ID-ArdiNeural` untuk pria dan `su-ID-TutiNeural` untuk wanita) sebagai default.
- Aktifkan CORS agar frontend di port lain dapat menganalisis audio.
- Cache audio berdasarkan hash teks dan suara.
- **AC:** mengetik teks di halaman lalu menekan tombol menghasilkan suara dan gerak mulut yang sinkron.

### FR-11 Perekaman hasil uji (P2)

- Rekam canvas dan audio ke berkas video untuk bahan penilaian (misalnya `MediaRecorder` dengan `captureStream`).
- **AC:** berkas video dapat diputar di perangkat lain untuk dinilai penilai.

### FR-12 Kontrak integrasi dengan HITS AI Live (P1)

- Modul avatar menerima event dengan bentuk yang sama seperti event `turn` di HITS AI Live, sehingga bisa dipindahkan tanpa perubahan besar:

```json
{ "persona": "persona_a", "emotion": "happy", "audio_url": "/audio/x.mp3", "playback_id": "1:3" }
```

- Modul mengirim balik event `ended` atau `error` setelah audio selesai, sama seperti mekanisme `playback_feedback` di HITS AI Live.
- **AC:** dengan adaptor tipis, event tiruan dari skenario JSON dapat diganti event WebSocket asli tanpa mengubah komponen avatar.

## 8. Skema data

### Skenario uji (`scenarios/*.json`)

```json
{
  "id": "emosi-tajam-01",
  "title": "Dialog dengan perubahan emosi",
  "characters": {
    "persona_a": { "name": "Raka", "model": "models/male.vrm", "voice": "id-ID-ArdiNeural" },
    "persona_b": { "name": "Salsa", "model": "models/female.vrm", "voice": "su-ID-TutiNeural" }
  },
  "turns": [
    { "persona": "persona_a", "text": "Pagi semuanya!", "emotion": "excited", "audio": "audio/s1_t1.mp3" },
    { "persona": "persona_b", "text": "Eh, tadi aku hampir telat banget.", "emotion": "surprised", "audio": "audio/s1_t2.mp3" }
  ]
}
```

- `audio` boleh berupa berkas lokal (Tahap A) atau dikosongkan agar dihasilkan oleh FR-10 dari `text` (Tahap C).
- `emotion`: `neutral | happy | excited | sad | surprised | thoughtful | empathetic` (sama dengan HITS AI Live).

### Konfigurasi avatar (`avatar.config.json`)

```json
{
  "quality": "medium",
  "lipsync": { "level": 1, "gain": 1.4, "gate": 0.02, "attackMs": 40, "releaseMs": 120 },
  "expression": { "transitionMs": 300, "maxCombinedWeight": 1.0 },
  "idle": { "blinkMinSec": 2, "blinkMaxSec": 6, "headSway": 0.3, "breath": 0.4 }
}
```

## 9. Metrik keberhasilan dan evaluasi

| Metrik | Target |
| --- | --- |
| FPS dengan 2 karakter di laptop target | 30 FPS atau lebih pada setidaknya satu pengaturan kualitas, saat aplikasi capture ikut berjalan |
| Mulut diam saat tidak ada audio | 100% frame senyap tanpa gerak mulut |
| Penutupan mulut setelah audio berhenti | 150 ms atau kurang |
| Skor lip-sync (skala 1 sampai 5, 3 sampai 5 penilai) | Rata-rata 3,5 atau lebih untuk Level 1 \[Usulan\] |
| Skor mimik wajah | Rata-rata 3,5 atau lebih \[Usulan\] |
| Skor keseluruhan "terlihat hidup" | Rata-rata 3,5 atau lebih \[Usulan\] |
| Stabilitas | Skenario 5 menit tanpa crash dan tanpa lonjakan memori yang terus naik |

**Prosedur penilaian**

- Rekam tiga skenario (FR-8), masing-masing dengan Level 1 dan Level 2 (bila ada).
- Penilai melihat tanpa tahu level yang dipakai (uji buta sederhana) dan mengisi formulir skor 1 sampai 5 untuk lip-sync, mimik, dan keseluruhan, plus komentar bebas.
- Putuskan: apakah avatar layak diintegrasikan ke HITS AI Live, dan Level lip-sync mana yang dipakai.

## 10. Struktur repositori \[Usulan\]

```
avatar-lipsync-proto/
  AGENTS.md
  docs/PRD.md
  public/
    models/          # male.vrm, female.vrm (jangan commit bila lisensi membatasi)
    audio/           # audio uji
  scenarios/         # skenario uji JSON
  src/
    scene/           # setup three.js, kamera, cahaya, loader VRM
    audio/           # AudioContext, antrean, analyser
    lipsync/         # level1 (amplitudo), level2 (viseme)
    expression/      # pemetaan emosi, transisi
    idle/            # kedip, napas, gerak kepala, mata
    listening/       # perilaku mendengarkan
    debug/           # panel debug, statistik
    adapter/         # kontrak event untuk HITS AI Live
  tts-server/        # opsional, endpoint Edge TTS (Tahap C)
```

## 11. Tahapan kerja \[Usulan\]

Estimasi kasar untuk satu orang dengan bantuan agen coding. Sesuaikan dengan jadwal skripsi dan KP.

| Tahap | Isi | Hasil | FR |
| --- | --- | --- | --- |
| A | Scene, muat 2 VRM, audio lokal, lip-sync amplitudo, panel debug | Dua karakter, mulut bergerak mengikuti audio | FR-1, 2, 3, 9 |
| B | Ekspresi dari emosi, idle, skenario JSON | Karakter hidup dan berekspresi, skenario uji berjalan | FR-5, 6, 8 |
| C | Endpoint TTS, input teks langsung, perilaku mendengarkan | Ketik teks menjadi suara dan gerak | FR-10, 7 |
| D | Lip-sync viseme, perekaman, uji performa dan uji penilai | Data keputusan Q1 sampai Q5 | FR-4, 11 |
| E | Adaptor kontrak event untuk HITS AI Live | Siap diintegrasikan | FR-12 |

Tahap A dan B sudah cukup untuk demo awal. Jika waktu terbatas, tahap D dipangkas ke perbandingan Level 1 saja.

## 12. Risiko dan mitigasi

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Audio lintas origin menghasilkan sinyal kosong pada analyser | Mulut tidak bergerak | `crossOrigin='anonymous'` dan header CORS di server TTS. Uji sejak Tahap A dengan audio dari server terpisah |
| Autoplay browser memblokir audio | Tidak ada suara | Buat `AudioContext` setelah klik pengguna, sediakan tombol "Mulai" |
| Perbedaan nama ekspresi VRM 0.x dan 1.0 | Ekspresi tidak muncul | Lapisan adaptor nama ekspresi, uji dengan model VRoid yang dipakai |
| Performa laptop (MX250) saat capture ikut berjalan | FPS rendah | Tiga pengaturan kualitas, model low-poly, batasi pixel ratio dan bayangan |
| Lip-sync amplitudo terlihat kaku | Skor rendah | Penyetelan attack/release, tambah Level 2, gaya karakter yang lebih stylized |
| Edge TTS tidak resmi dan dapat berubah | Audio uji gagal | Simpan audio uji ke berkas, siapkan cadangan ElevenLabs atau Gemini TTS |
| Edge TTS tidak memberi data viseme | Level 3 (viseme dari TTS) tidak tersedia | Gunakan Level 2 (estimasi dari audio). Provider dengan event viseme hanya dievaluasi jika perlu |
| Lisensi model VRM membatasi siaran atau komersial | Tidak boleh dipakai | Buat model sendiri di VRoid atau pakai model berlisensi jelas, catat lisensi tiap model |
| Satu tag emosi per giliran terlalu kasar | Mimik tidak sesuai isi | Uji Q4, pertimbangkan emosi per kalimat pada output LLM |
| Pustaka berubah atau usang | Kode tidak jalan | Pin versi di `package.json`, catat versi yang diuji |

## 13. Keputusan terbuka

1. **Sumber model**: membuat sendiri di VRoid Studio atau memakai model berlisensi jelas (dan siapa yang membuat karakter pria dan wanita).
2. **React atau vanilla TypeScript** untuk prototipe (usulan: React agar mudah dipindahkan).
3. **Pustaka atau metode Level 2** (analisis spektrum sendiri atau pustaka audio-ke-viseme) dan lisensinya.
4. **Spesifikasi laptop target** dan aplikasi capture yang akan berjalan bersamaan.
5. **Rasio layar** utama: 16:9 atau 9:16.
6. **Daftar penilai** dan format formulir skor.
7. **Apakah emosi per kalimat** perlu masuk skema output LLM di HITS AI Live (tergantung hasil Q4).

## 14. Panduan vibe coding

### Prinsip kerja

1. Taruh `docs/PRD.md` dan `AGENTS.md` di root repo.
2. Kerjakan per tahap (bagian 11), satu tahap per sesi agen. Minta rencana sebelum agen mengubah banyak file.
3. Mulai dengan audio lokal dan skenario JSON, tanpa backend, agar pengujian cepat dan tidak memakai kuota.
4. Commit tiap tahap yang lulus AC.
5. Verifikasi versi `three` dan `@pixiv/three-vrm` di dokumentasi sebelum menulis kode yang bergantung pada API tertentu.

### Contoh `AGENTS.md`

```markdown
# Aturan proyek avatar-lipsync-proto
- Baca docs/PRD.md sebelum mengerjakan tugas. Kerjakan hanya FR yang diminta.
- Tidak ada LLM, backend siaran, atau musik di proyek ini.
- Semua parameter gerak harus bisa disetel lewat panel debug dan avatar.config.json.
- Audio harus dimuat dengan crossOrigin='anonymous'. Satu AudioContext global.
- Mulut hanya boleh bergerak dari sinyal audio karakter yang sedang berbicara.
- Jangan menambah dependensi tanpa menyebut alasannya.
- Komentar kode dan nama variabel dalam bahasa Inggris; teks UI dalam bahasa Indonesia.
- Catat lisensi setiap model VRM dan aset di docs/ASSETS.md.
```

### Prompt awal per tahap

| Tahap | Prompt awal ke agen (ringkas) |
| --- | --- |
| A | "Scaffold Vite + three.js. Implementasikan FR-1, FR-2, FR-3, FR-9: muat dua VRM, pemutar audio dengan AnalyserNode per karakter, lip-sync amplitudo dengan parameter di panel debug." |
| B | "Tambahkan FR-5, FR-6, FR-8: pemetaan 7 emosi ke ekspresi VRM dengan interpolasi, animasi idle prosedural, dan pemutar skenario dari JSON." |
| C | "Tambahkan FR-10 dan FR-7: endpoint Edge TTS dengan CORS dan cache, input teks di UI, serta perilaku mendengarkan." |
| D | "Tambahkan FR-4 (estimasi viseme, bisa dimatikan), FR-11 (perekaman), dan mode kualitas rendah. Siapkan formulir skor penilaian." |
| E | "Tambahkan lapisan adaptor sesuai FR-12 agar modul menerima event dengan bentuk yang sama seperti event `turn` di HITS AI Live." |

## 15. Definition of Done

- [ ] Dua karakter VRM (pria dan wanita) tampil dan stabil di satu scene.
- [ ] Mulut bergerak mengikuti audio TTS hanya pada karakter yang berbicara, diam saat senyap.
- [ ] Ekspresi berubah halus sesuai tujuh tag emosi tanpa merusak bentuk mulut.
- [ ] Idle (kedip, napas, gerak kepala, mata) dan perilaku mendengarkan berjalan.
- [ ] Tiga skenario uji berjalan, termasuk skenario panjang 3 sampai 5 menit tanpa crash.
- [ ] FPS 30 atau lebih tercapai pada setidaknya satu pengaturan kualitas di laptop target.
- [ ] Panel debug dapat menyetel parameter secara langsung, dan mode bersih tersedia untuk capture.
- [ ] Evaluasi penilai dilakukan dan hasilnya menjawab Q1 sampai Q5.
- [ ] Keputusan tertulis: layak atau tidaknya integrasi ke HITS AI Live, dan Level lip-sync yang dipakai.
- [ ] Kontrak event untuk integrasi (FR-12) terdokumentasi dan diuji dengan event tiruan.
