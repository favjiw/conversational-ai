# Rundown Live TikTok 1 Jam (DRAF v2.1, belum disetujui HITS/pembimbing)

Turunan dari `FORMAT-CLOCK-PAGI-BENER.md`. Isi Talk mengacu ke `STRUKTUR-TEMA-HITS.md`.
File clock yang dijalankan: `clock-pagi-bener-live-1jam.json` (version 0.3).

## Riwayat
- **v1 (15 Okt 2026):** urutan clock asli dipadatkan menjadi 1 jam. Berisi 11 lagu (±33 menit) dan 6 Talk (±16 menit, 1-3 menit per slot).
- **v2 (21 Okt 2026):** Talk dinilai terlalu singkat dibanding live TikTok HITS yang sedang berjalan, di mana satu blok Talk ±7-8 menit (lihat `ANALISIS-LIVE-TIKTOK-2026-10-20.md`). Aturan: waktu dari sesi yang duplikat atau berlebihan, terutama lagu, dialihkan ke Talk.
- **v2.1 (21 Okt 2026):** iklan (SPOT/ADLIBS) cukup sekali per kuartal. Tambahan ±3 menit dialihkan ke Talk.

## Prinsip
1. Lagu tidak diputar berturut-turut; satu lagu menjadi jeda antar-Talk. Jumlah lagu dikurangi dari 11 menjadi 5.
2. Say Hi dibagi menjadi 2 slot panjang. Teaser 3M menjadi penutup Talk 3, bukan slot sendiri.
3. SPOT/ADLIBS sekali per kuartal (kuartal 2-4).
4. Elemen identitas stasiun tetap dipertahankan.
5. Notasi: ('n) = detik, (n) = menit.

## Rundown v2.1 (id slot sesuai JSON)
**Kuartal 1, ±15,6 menit**
1. s01 SMASH TIME SIGNAL ('9)
2. s02 TIME SIGNAL ('10)
3. s03 JINGLE ALAMAT HITS ('18)
4. s04 P.S.A (1)
5. s05 GREETINGS ARTIS ('20)
6. s06 IMAGE / MASHUP ('32)
7. s07 ICE BREAKING ('30)
8. s08 SMASH ABIS TALK 1 ('5)
9. s09 BUMPER OPENING ('30)
10. s10 TALK 1 - OPENING (4)
11. s11 LAGU INDO HITS (3)
12. s13 TALK 2 - SAY HI ! (5)

**Kuartal 2, ±14,4 menit**
1. s16 SMASH VERSI ('5)
2. s17 SPOT/ADLIBS (1)
3. s19 JINGLE HITS ('18)
4. s22 LAGU BARAT (3)
5. s21 TALK 3 - SAY HI ! lanjutan + TEASER 3M (7)
6. s20 LAGU INDO (3)

**Kuartal 3, ±14,4 menit**
1. s25 SMASH VERSI ('5)
2. s26 SPOT/ADLIBS (1)
3. s28 JINGLE HITS ('18)
4. s30 TALK 4 - 3M (10)
5. s29 LAGU KOREA (3)

**Kuartal 4, ±15,8 menit**
1. s34 SMASH VERSI ('5)
2. s35 SPOT/ADLIBS (1)
3. s37 JINGLE HITS ('18)
4. s39 BUMPER SKEMA PAGI BENER ('23)
5. s40 TALK 5 - KONTEN / SKEMA (8)
6. s42 LAGU INDO (3)
7. s41 CLOSING (3)

Slot v1 yang dibuang: s12, s14, s18, s23, s27, s31, s32, s36, s38.

## Ringkasan
| | v1 | v2.1 |
| --- | --- | --- |
| Talk LLM-LLM | 6 slot, ±16 menit | 6 slot, ±37 menit (3-10 menit/slot) |
| Lagu | 11, ±33 menit | 5, ±15 menit |
| Iklan TTS | 6x | 3x |
| Total | ±60 menit | ±60 menit |

## Catatan
- v2.1 menyimpang dari keputusan awal bahwa "urutan elemen asli dipertahankan" (`KEPUTUSAN-DESAIN.md` bagian 4). Perlu disetujui HITS dan pembimbing.
- Talk harus berhenti berdasarkan durasi slot (`nominal_sec`), bukan jumlah giliran tetap.
