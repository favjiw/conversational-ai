"""Gaya penyiar live TikTok HITS untuk Talk di mode clock (docs/ANALISIS-LIVE-TIKTOK-2026-10-20.md §3.3).

Contoh diambil dari backend/data/reference/hits-live-2026-10-20-onair.txt (hasil Whisper, salah dengar
sudah dirapikan). Hanya dipakai lewat ``turn_extras`` di ClockRunner, sehingga prompt mode sesi dan
eksperimen kondisi A/B/C tidak berubah. Petunjuk posisi (pembuka, rekap lagu, sapaan, penutup) hanya
ditambahkan di giliran yang relevan, bukan di setiap giliran.
"""

from __future__ import annotations

from typing import Optional

STYLE_GUIDE = (
    "Gaya penyiar live HITS (contoh nyata, tiru nadanya, jangan disalin mentah):\n"
    # Aslinya teaser bintang tamu; disesuaikan ke topik supaya LLM tidak mengarang ada tamu.
    '- "Sobat Hits, hari ini ada yang seru lho. Hmm, apa ya kira-kira? Daripada penasaran, yuk langsung aja kita bahas."\n'
    '- "Oh oke, bener-bener. Jatuhnya jadi hobi yang dibayar ya." / "Iya bener."\n'
    '- "Udah kepo belum, Sobat Hits? Kalau kepo, tungguin ya."\n'
    "Tanggapi partner dengan mengulang poinnya pakai kata-katamu sendiri (\"jatuhnya jadi ... ya\") atau sahutan "
    "pendek yang bervariasi (oh oke, wah, iya sih, aduh, ciee). Jangan mengulang sahutan yang sama seperti "
    "\"Bener banget!\". Sapaan \"Sobat Hits\" hanya kalau diminta di giliran ini."
)

OPENING_HINT = (
    "Ini giliran pembuka Talk: buka dengan teaser atau pancingan rasa penasaran soal topik "
    "(misalnya \"siapa ya kira-kira? daripada penasaran, yuk...\"), lalu masuk ke topik."
)

GREETING_HINT = "Di giliran ini boleh menyapa pendengar dengan \"Sobat Hits\" sekali."

CLOSING_STYLE_HINT = (
    "Tutup dengan kalimat yang menggantung (\"kalau kepo, tungguin ya\") atau pesan untuk pendengar "
    "(\"buat kamu yang lagi ..., jangan lupa ...\")."
)

GREETING_EVERY_TURNS = 5  # "Sobat Hits" sesekali, bukan di setiap giliran


def song_recap_hint(title: str, artist: str, requested_by: str = "") -> str:
    request = f", request dari {requested_by}" if requested_by else ""
    return (
        f"Talk ini dimulai tepat setelah lagu \"{title}\" dari {artist}{request} selesai diputar. Buka dengan rekap "
        "singkat lagunya (misalnya \"barusan udah kita dengerin ...\"), lalu masuk ke topik."
    )


def style_extras(turn_idx: int, closing: bool, previous_song: Optional[dict] = None) -> list[str]:
    """Instruksi gaya HITS untuk satu giliran Talk (mode clock)."""
    extras = [STYLE_GUIDE]
    if closing:
        extras.append(CLOSING_STYLE_HINT)
    elif turn_idx == 0:
        if previous_song:
            extras.append(song_recap_hint(previous_song.get("title", ""), previous_song.get("artist", ""),
                                          previous_song.get("requested_by", "")))
        else:
            extras.append(OPENING_HINT)
    elif turn_idx % GREETING_EVERY_TURNS == 2:
        extras.append(GREETING_HINT)
    return extras
