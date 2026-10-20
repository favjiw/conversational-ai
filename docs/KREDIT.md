# Kredit Komponen Pihak Ketiga

## Modul rekomendasi lagu: hits-song-recommender

- Pembuat: **Iam** (rekan kerja praktek di HITS UNIKOM RADIO).
- Repo: https://github.com/ffromme/hits-song-recommender
- Dipakai sebagai git submodule di `external/hits-song-recommender` (dikunci per commit) dan dipasang
  dengan `pip install -e external/hits-song-recommender --no-deps`.
- Kode rekan tidak diedit di repo ini. Penyesuaian ada di adapter `backend/app/music/recommender.py`.
  Usulan perubahan untuk repo rekan dicatat di `docs/CATATAN-PROGRES.md`.
- Isi modul: klasifikasi intent komentar (LLM), pencarian lagu (fuzzy match + vector search ChromaDB
  dengan embedding `intfloat/multilingual-e5-small`), rerank + `host_line` (LLM), katalog 102 lagu
  berlabel mood.

## Lainnya

- Model avatar dan lisensinya: `docs/avatar/ASSETS.md`.
- Audio pratinjau lagu: Deezer API publik (pratinjau 30 detik).
