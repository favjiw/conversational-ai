import json
from pathlib import Path

raw_themes = json.loads(Path(__file__).parent.joinpath("aron_themes.json").read_text(encoding="utf-8"))

id_translations = [
    ("Tamu Makan Malam Impian", "Kalau bisa milih siapa pun di dunia ini, siapa yang pengen banget lo undang buat makan malam bareng?"),
    ("Keinginan Menjadi Terkenal", "Pengen gak sih jadi orang terkenal? Terkenal di bidang apa dan dengan cara seperti apa?"),
    ("Latihan Bicara Sebelum Telepon", "Sebelum nelpon orang penting, suka latihan dulu gak apa yang mau diomongin? Kenapa tuh?"),
    ("Definisi Hari Sempurna", "Kira-kira hari yang sempurna buat lo itu kayak gimana sih dari pagi sampai malem?"),
    ("Bernyanyi Sendiri dan Bareng Orang Lain", "Kapan terakhir kali lo nyanyi sendiri pas lagi santai atau nyanyi di depan orang lain?"),
    ("Pilihan Usia 90 Tahun (Pikiran vs Fisik)", "Kalau bisa hidup sampai umur 90 tahun, lo lebih milih punya pikiran anak 30 tahun atau fisik anak 30 tahun selama 60 tahun terakhir?"),
    ("Firasat Rahasia Soal Kematian", "Pernah punya firasat atau intuisi rahasia gak kira-kira lo bakal berpulang seperti apa nanti?"),
    ("Tiga Kesamaan Kita Berdua", "Coba sebutin 3 hal kesamaan yang lo rasa kita berdua sama-sama punya!"),
    ("Hal Paling Lo Syukuri", "Sepanjang hidup lo sampai detik ini, hal apa yang paling lo syukuri?"),
    ("Hal yang Ingin Diubah dari Pola Asuh", "Kalau bisa muter waktu dan mengubah satu hal dari cara lo dibesarkan dulu, apa yang pengen diubah?"),
    ("Kisah Hidup Singkat dalam 4 Menit", "Coba ceritain garis besar kisah hidup lo yang paling berkesan dan ngebentuk lo jadi sekarang."),
    ("Kekuatan atau Bakat Impian", "Kalau besok pagi bangun tidur tiba-tiba dapet satu kemampuan atau kekuatan baru, pengen dapet apa?"),
    ("Pertanyaan ke Bola Kristal", "Kalau bola kristal bisa ngasih tau satu kebenaran mutlak soal diri lo, masa depan, atau apa pun, lo mau nanya apa?"),
    ("Mimpi Lama yang Belum Terwujud", "Ada gak satu impian lama yang pengen banget lo lakuin tapi belum kesampean sampai sekarang? Kenapa belum?"),
    ("Pencapaian Terbesar dalam Hidup", "Apa pencapaian atau momen paling membanggakan dalam hidup lo sejauh ini?"),
    ("Nilai Tertinggi dalam Persahabatan", "Buat lo pribadi, apa nilai atau kualitas yang paling lo hargai dari seorang sahabat?"),
    ("Memori Paling Indah dan Berharga", "Memori apa di masa lalu yang paling berharga dan selalu bikin lo tersenyum hangat pas diingat?"),
    ("Memori Paling Berat atau Buruk", "Momen atau memori apa yang paling berat atau kelam yang pernah lo lewatin tapi berhasil lo lewatin?"),
    ("Jika Hidup Tinggal Satu Tahun", "Kalau lo tau sisa hidup lo tinggal setahun lagi, ada gak gaya hidup atau kebiasaan lo sekarang yang bakal langsung lo ubah?"),
    ("Arti Persahabatan Sejati", "Sebenernya arti persahabatan sejati buat lo itu apa sih maknanya?"),
    ("Peran Cinta dan Kasih Sayang", "Seberapa besar peran cinta, afeksi, dan kasih sayang dalam ngejalanin hari-hari lo?"),
    ("Hal Positif dari Rekan Siaran", "Coba sebutin hal-hal positif atau sifat baik yang lo kagumi dari lawan siaran lo!"),
    ("Kehangatan Keluarga dan Masa Kecil", "Seberapa dekat dan hangat keluarga lo? Apakah ngerasa masa kecil lo bahagia?"),
    ("Hubungan dengan Ibu", "Gimana pandangan dan perasaan lo soal hubungan lo dengan ibu tercinta?"),
    ("Pernyataan Kebersamaan Kita", "Bikin 3 kalimat yang dimulai dengan kata 'Kita berdua saat ini...' yang beneran lo rasain."),
    ("Keinginan Punya Teman Berbagi", "Lengkapi kalimat ini: 'Gue pengen banget punya seseorang buat berbagi hal...'"),
    ("Hal Penting yang Perlu Diketahui Sahabat", "Kalau kita berdua mau jadi sahabat dekat seumur hidup, hal penting apa soal lo yang wajib banget diketahui?"),
    ("Hal yang Lo Sukai dari Partner Bicara", "Jujur-jujuran, apa yang paling lo sukai atau apresiasi dari partner lo sekarang?"),
    ("Momen Paling Memalukan dalam Hidup", "Ceritain satu momen paling memalukan atau konyol yang pernah kejadian di hidup lo!"),
    ("Kapan Terakhir Kali Menangis", "Kapan terakhir kali lo nangis? Pas sendirian atau pas di depan orang lain?"),
    ("Kesan Pertama yang Disukai", "Sebutin satu hal yang dari awal lo udah suka atau kagumi dari rekan lo!"),
    ("Hal yang Tabu Dijadikan Lelucon", "Menurut lo, hal apa sih yang terlalu serius dan gak pantas dijadiin bahan bercandaan?"),
    ("Penyesalan Kata yang Belum Tersampaikan", "Kalau hari ini hari terakhir lo, kata-kata apa yang paling lo sesali belum sempat lo ucapin ke seseorang?"),
    ("Barang Terakhir yang Diselamatkan saat Kebakaran", "Kalau rumah kebakaran dan semua orang aman, cuma ada waktu nyelamatin satu barang berharga, apa yang bakal lo ambil?"),
    ("Kehilangan yang Paling Mengguncang", "Dari semua orang terdekat, kepergian siapa yang paling bikin lo takut dan terpukul?"),
    ("Curhat Masalah dan Minta Masukan", "Curhatin satu kegelisahan atau masalah lo saat ini, dan minta saran tulus dari rekan lo.")
]

enriched = []
for item, (title_id, text_id) in zip(raw_themes, id_translations):
    set_num = item.get("set", "I")
    set_label = (
        "Set I: Eksplorasi Diri & Minat" if set_num == "I" else
        "Set II: Refleksi & Memori" if set_num == "II" else
        "Set III: Koneksi & Eksistensial"
    )
    enriched.append({
        "id": item["id"],
        "set": set_num,
        "set_label": set_label,
        "title": f"#{item['id']} {title_id}",
        "question_id": text_id,
        "question_en": item["text"],
        "guidance": f"Bahas santai dan seru: '{text_id}'. Dengarkan rekanmu, beri tanggapan hangat, dan selipkan guyonan khas siaran radio hits."
    })

out_path = Path(__file__).parent.joinpath("aron_themes_id.json")
out_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Generated {len(enriched)} enriched themes at {out_path}")