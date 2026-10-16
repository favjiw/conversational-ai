# Assets dan Lisensi

## Model realistis GLB (aktif sejak 15 Okt 2026)

### `public/models/realistic/raka.glb` (Raka / Persona A) dan `public/models/realistic/salsa.glb` (Salsa / Persona B)
- **Model asli**: Microsoft Rocketbox `Male_Adult_06` (Raka) dan `Female_Adult_08` (Salsa), varian `*_facial.fbx`.
- **Sumber**: https://github.com/microsoft/Microsoft-Rocketbox (`Assets/Avatars/Adults/...`)
- **Lisensi**: MIT, Copyright (c) 2020 Microsoft. Teks lisensi disertakan di `public/models/realistic/LICENSE-Microsoft-Rocketbox.md`.
- **Karakter original** buatan studio Rocketbox, bukan pindaian wajah orang sungguhan.
- **Isi setelah konversi** (`frontend/scripts/convert_rocketbox.py`, Blender 5.2):
  - 52 blendshape ARKit dengan nama standar (`jawOpen`, ...);
  - 15 viseme Oculus (`viseme_sil` ... `viseme_U`);
  - rig Biped 3ds Max (`Bip01_*`);
  - sekitar 7.500 segitiga;
  - tekstur 1024 px WebP (color, normal, opacity).

  Shape key FACS/Headbox lain dibuang supaya file kecil.
- **Cara membuat ulang**: unduh `*_facial.fbx` dan tekstur `*_body_color`, `*_body_normal`, `*_head_color`, `*_head_normal`, `*_opacity_color` (`.tga`), lalu jalankan:
  `blender --background --factory-startup --python frontend/scripts/convert_rocketbox.py -- <fbx> <folder_tekstur> <m011|f008> <out.glb>`

### `public/models/test/arkit-test-head.glb`
- Model uji buatan sendiri (bola + silinder, 52 shape key ARKit) dari `frontend/scripts/make_arkit_test_head.py`. Tanpa lisensi pihak ketiga.

## Model VRM

### 1. `public/models/red-male.vrm` (Raka / Persona A - Aktif)
- **Model Asli**: Seed-san (`Seed-san.vrm`)
- **Sumber**: Repositori resmi [vrm-c/vrm-specification](https://github.com/vrm-c/vrm-specification/tree/master/samples/Seed-san)
- **Pembuat**: VirtualCast, Inc.
- **Lisensi**: [VRM Public License 1.0](https://vrm.dev/en/licenses/1.0/index)
- **Format**: VRM 1.0
- **Preset Blendshapes**: `aa`, `ih`, `ou`, `ee`, `oh`, `blink`, `blinkLeft`, `blinkRight`, `happy`, `angry`, `sad`, `relaxed`, `surprised`, `neutral`

### 2. `public/models/female.vrm` (Salsa / Persona B)
- **Model Asli**: VRM1 Constraint Twist Sample (`VRM1_Constraint_Twist_Sample.vrm`)
- **Sumber**: Repositori resmi [pixiv/three-vrm](https://github.com/pixiv/three-vrm/tree/dev/packages/three-vrm/examples/models)
- **Pembuat**: (c) 2022 pixiv Inc.
- **Lisensi**: [VRM Public License 1.0](https://vrm.dev/licenses/1.0/)
- **Format**: VRM 1.0
- **Preset Blendshapes**: `aa`, `ih`, `ou`, `ee`, `oh`, `blink`, `blinkLeft`, `blinkRight`, `happy`, `angry`, `sad`, `relaxed`, `surprised`, `neutral`

### 3. Model Cadangan: `public/models/AliciaSolid.vrm`
- **Sumber**: [vrm-c/UniVRM](https://github.com/vrm-c/UniVRM/tree/master/Tests/Models/Alicia_vrm-0.51)
- **Pembuat**: Dwango Co., Ltd.
- **Lisensi**: Niconico Character License (VRM 0.x reference model)

## Audio Uji

### 1. `public/audio/male_test.wav`
- Suara persona Raka (Microsoft David Desktop TTS).
- Teks: "Hello, my name is Raka. Nice to meet you. This is an automated 3D avatar lip sync prototype demonstration."

### 2. `public/audio/female_test.wav`
- Suara persona Salsa (Microsoft Zira Desktop TTS).
- Teks: "Hello everyone, I am Salsa. I can speak and synchronize my mouth movements with the speech audio."

### 3. `public/audio/scenarios/` (Skenario Uji FR-8)
- File `s1_t1.wav` s.d. `s1_t4.wav`: Dialog Netral Pendek (Microsoft David & Zira Desktop).
- File `s2_t1.wav` s.d. `s2_t7.wav`: Dialog Perubahan Emosi Tajam (Microsoft David & Zira Desktop).
- Dibuat secara lokal menggunakan Windows Speech API untuk keperluan prototipe pengujian responsivitas dan emosi avatar.


## Catatan Lisensi
Kedua model VRM utama menggunakan VRM Public License 1.0 resmi yang ditujukan untuk pengujian, kompatibilitas, dan pengembangan ekosistem VRM. Untuk siaran komersial produksi di masa depan, ganti dengan avatar kustom dari VRoid Studio.
