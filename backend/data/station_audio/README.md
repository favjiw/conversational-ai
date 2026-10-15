# Station audio

Pre-recorded HITS Unikom Radio elements (jingles, bumpers, tapings, ...) that
clock slots with `"source": "static_audio"` play as-is. The announcers never
voice these through TTS; a slot whose file is missing is skipped.

The recordings belong to HITS and are not committed (`*.mp3` is gitignored).
Put them here under these names:

| File | Content | Length |
|---|---|---|
| `jingle-hits-unikom-radio.mp3` | Jingle HITS Unikom Radio | 0:18 |
| `bumper-before-update.mp3` | Bumper BU (Before Update) | 0:10 |
| `bumper-skema-pagi-bener.mp3` | Bumper Skema Pagi Bener | 0:23 |
| `taping-fbh-2026-08-02-cut01.mp3` | Taping FBH 02 Agt 2026, cut 01 | 0:52 |
| `taping-pentas-2026-08-01-cut01.mp3` | Taping Pentas 01 Agt 2026, cut 01 | 2:10 |

Reference a file from a clock slot with `"asset": "<file name>"`.

Used in the current rundown (`clock-pagi-bener-live-1jam.json`): the jingle at
Jingle Alamat HITS (s03, temporary) and every Jingle HITS (s19, s28, s37), and
Bumper Skema before the SKEMA Talk (s39). `bumper-before-update.mp3` and the
two tapings are not placed yet: News/Traffic are not in the 1-hour draft, and
where tapings go is still open.
