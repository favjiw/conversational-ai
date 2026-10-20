# Keputusan Desain Sistem Penyiar AI HITS

Ringkasan keputusan dari diskusi perancangan (15 Oktober 2026). File ini adalah acuan untuk mereview dan mengembangkan kode. Jika kode bertentangan dengan file ini, laporkan dulu sebelum mengubah apa pun.

## 1. Tujuan proyek

Sistem penyiar AI untuk live streaming TikTok HITS Unikom Radio: dua penyiar AI (pria dan wanita) membawakan sesi live 1 jam secara otomatis berdasarkan rundown dan dokumen Tema dari produser.

- Prioritas saat ini: membangun sistem sesuai kebutuhan live streaming HITS.
- Uji coba live dilakukan di akun TikTok pribadi yang sudah bisa LIVE.
- Skripsi: rancang bangun sistem ini, dengan satu fokus riset, yaitu mekanisme AI-in-the-Loop (Supervisor) untuk menjaga konsistensi persona pada segmen Talk.
- Istilah yang dipakai: "arsitektur multi-LLM", bukan "multi-agent". Rundown dijalankan sebagai state machine berurutan; LLM persona tidak memilih alat atau menyusun rencana sendiri.

## 2. Fitur wajib

1. AI ngobrol dengan AI (dua penyiar AI).
2. Rekomendasi musik berdasarkan emosi (lagu dari API musik).
3. Karakter 3D untuk penyiar pria dan wanita, dengan lip-sync dan ekspresi dari audio TTS, dalam dua gaya yang bisa dipilih (keputusan 19 Okt 2026; sepasang penyiar selalu bergaya sama): **realistis** (GLB, rig, 52 blendshape ARKit, material PBR; halaman `/stage-3d-realistic`) dan **animasi/VTuber** (VRM; halaman `/stage-animation`). `/stage` memakai gaya default dari `avatar.config.json`.
4. Membaca komentar TikTok lalu berimprovisasi: sebutkan username dan isi komentarnya, lalu jadikan topik sementara di dalam Tema yang sedang dibahas.

Requirement penting: suara tidak boleh terdengar seperti robot penerjemah.

## 3. Alur kerja (alur kerja HITS tidak diubah)

Alur saat ini di HITS: produser membuat Tema, Tema diserahkan ke penyiar, penyiar berimprovisasi (tanpa naskah kecuali yang sudah ditulis di Tema), dan komentar penonton dibacakan lalu direspons. Sistem menggantikan penyiar; produser tetap bekerja seperti biasa.

### A. Sebelum live
1. Produser mengunggah dokumen Tema (.docx) ke halaman operator.
2. LLM mem-parsing Tema per segmen Talk dan memberi label jenisnya (lihat bagian 5).
3. Operator memeriksa hasil parsing sebelum live.
4. Rundown 1 jam disiapkan: slot Talk dihubungkan ke segmen Tema, slot lagu diisi dari API musik, dan aset audio statis disiapkan.

### B. Saat live
5. Rundown Engine menjalankan item satu per satu sesuai urutan: audio statis diputar, SPOT/ADLIBS dibacakan lewat TTS, lagu diputar, dan slot Talk diserahkan ke Conversation Engine.
6. Conversation Engine menangani Talk sesuai jenisnya (bagian 5). Talk selesai jika durasi slot habis dan semua isi wajib (misalnya pengingat ajakan) sudah disampaikan.
7. Komentar TikTok dikumpulkan ke antrean sepanjang live, disaring, lalu dibawa ke segmen Talk berikutnya sebagai pesan pendengar. Komentar tidak memotong lagu.
8. Per ucapan: teks, lalu Supervisor, lalu TTS, lalu avatar, lalu ditangkap TikTok LIVE Studio. Giliran berikutnya dibuat saat audio giliran sekarang masih diputar (pipelining), supaya tidak ada jeda kosong.
9. Operator bisa melewati item atau menghentikan sesi kapan saja.

### C. Setelah live
10. Simpan log transkrip, keputusan Supervisor, dan latensi per giliran (LLM persona, Supervisor, TTS). Log ini menjadi data eksperimen.

## 4. Rundown 1 jam

Mengikuti "Format Clock Pagi Bener" HITS dalam versi ringkas 1 jam, dengan urutan elemen asli dipertahankan. Menurut pembimbing, rundown live TikTok sama dengan rundown on-air.

- Kuartal 1: pembuka jam 06.00 (smash time signal, time signal, jingle alamat, P.S.A, greetings artis, image/mashup, ice breaking, bumper opening, Talk Opening, Talk Say Hi).
- Kuartal 2-4: pola standar (smash versi, 2x spot/adlibs, jingle HITS, lagu, Talk, lagu).
- Kuartal 4 diakhiri CLOSING.
- Notasi durasi (asumsi, belum dikonfirmasi ke HITS): ('n) = detik, (n) = menit.
- News dan Traffic Info bisa dimasukkan sebagai naskah tetap, karena naskahnya sudah ditulis produser di Tema. Status: belum diputuskan.
- Menerima telepon pendengar di luar ruang lingkup.

## 5. Tiga jenis segmen Talk dalam Tema

| Jenis | Contoh | Penanganan |
| --- | --- | --- |
| Naskah tetap | Traffic Info / SIM Keliling, HITS News, HITS Sport | Teks dibacakan bergantian lewat TTS. Tanpa LLM dan tanpa Supervisor. |
| Improvisasi dengan materi | Ice Breaking, Opening, Say Hi, 3M | Dua LLM bercakap dengan Supervisor. Bahan: materi Tema, pesan pendengar dari Tema, dan komentar TikTok. |
| Roleplay | SKEMA | Seperti improvisasi, tetapi Supervisor diberi tahu peran yang sedang aktif. |

Istilah: 3M = Mencoba Mengerti Mahasiswa (penyiar berperan sebagai "Pak Dosen Agung" dan "Asdos Akri"). SKEMA = segmen sketsa roleplay dengan karakter, kata yang harus dihindari, benang merah, dan alur per cut. Dalam naskah, tanda / berarti jeda pendek dan // berarti jeda panjang.

## 6. Supervisor (fokus riset skripsi)

- Menengahi setiap giliran pada segmen improvisasi dan roleplay: memeriksa identity drift, lalu meneruskan ucapan atau mengoreksinya dengan menyisipkan memori persona dan percakapan.
- Wajib mengetahui peran aktif per segmen. Pergantian peran yang diminta Tema (3M, SKEMA) bukan drift. Keluar dari peran atau memakai kata terlarang adalah pelanggaran.
- Juga memeriksa keamanan isi, termasuk kata terlarang dari Tema dan komentar penonton sebelum dibacakan.
- Eksperimen: kondisi A (dua LLM bercakap langsung, baseline) dibandingkan kondisi B (dengan Supervisor). Metrik: identity drift (kuesioner pada titik snapshot, mengikuti replikasi Choi et al. 2025) dan kealamian percakapan (dibandingkan dengan transcript on-air HITS dan dinilai penyiar HITS).

## 7. Keputusan teknologi

- LLM: model teks, yaitu Gemini Flash melalui Google AI Studio.
- Suara: TTS yang ekspresif, bukan model voice-to-voice. Kandidat utama Gemini TTS multi-speaker (maksimal 2 pembicara, mendukung bahasa Indonesia, gaya diatur lewat prompt dan tag seperti [laughs]); `gemini-3.1-flash-tts-preview` mendukung streaming. Audio dibuat per giliran, bukan per segmen. Alternatif berbayar: ElevenLabs.
- Alasan tidak memakai voice-to-voice: semua input sistem berupa teks (Tema, komentar); Supervisor harus mencegat teks sebelum audio dibuat; sesi Live API yang hanya audio dibatasi 15 menit.
- Teks LLM harus ditulis untuk diucapkan: kalimat pendek, gaya "gue/lu", ada sahutan dan tawa, tanpa markdown. Transcript on-air HITS dipakai sebagai contoh gaya di prompt.
- Avatar: dua gaya (GLB realistis dengan 52 blendshape ARKit, atau VRM anime), dirender three.js di halaman stage repo ini. Lip-sync kedua gaya berbasis viseme dari teks dan timestamp kata TTS (bentuk viseme model untuk GLB, lima vokal VRM untuk anime), cadangan dari amplitudo audio. Prototipe lama di repo char-3d diarsipkan.
- Komentar TikTok: library tidak resmi (misalnya TikTokLive untuk Python). Cadangan: komentar diinput manual oleh operator.

## 8. Risiko dan kepatuhan

- Pedoman TikTok Shop (17 September 2026) melarang "non-real-time verbal interaction such as AI-generated voices, audio recordings, or radio" dan animasi yang menutupi lebih dari 50% layar di LIVE jualan. Status untuk LIVE non-jualan belum jelas.
- Mitigasi: label "AI" di layar dan pengumuman di pembukaan, ada operator manusia, dan Supervisor ikut memeriksa keamanan isi.
- Tata letak live (keputusan 17 Okt 2026, menggantikan split kiri-kanan 15 Okt): kanvas portrait 9:16 (1080×1920) dengan dua panel bertumpuk seperti live HITS asli (atas penyiar pria, bawah penyiar wanita; urutan bisa ditukar lewat config) dan latar studio radio. Komposisi mengikuti zona aman TikTok: header 0–10%, bar bawah 93–100%, daftar komentar 65–91% tinggi × 0–70% lebar, margin sisi 5%; wajah atas di 22–28% tinggi, wajah bawah dinaikkan ke 55–60%. Avatar tetap memenuhi layar, jadi batas "tidak lebih dari 50% layar" untuk LIVE jualan tidak terpenuhi; risiko diterima karena live HITS bukan LIVE jualan, dan perlu ditinjau ulang bila status aturannya berubah.

## 9. Belum diputuskan

- Apakah News dan Traffic Info dimasukkan ke rundown 1 jam.
- Emosi yang dipakai untuk rekomendasi musik: emosi topik Talk atau emosi komentar penonton.
- Apakah Supervisor ikut berjalan saat live atau hanya dipakai di eksperimen (mempertimbangkan latensi).
- Bahan eksperimen: 36 pertanyaan Aron, Tema HITS, atau keduanya.
