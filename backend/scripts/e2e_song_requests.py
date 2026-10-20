"""Uji ujung-ke-ujung rekomendasi lagu: komentar lewat endpoint → slot lagu di rundown 1 jam.

Prasyarat: backend jalan di :8000 dengan RECOMMENDER_ENABLED=true (mis. konfigurasi ``backend-rec``
di .claude/launch.json: TTS mock, LLM persona live). Tutup semua tab /stage: skrip ini tersambung
sebagai stage (pemutar audio) dan langsung mengonfirmasi setiap audio selesai.

    python scripts/e2e_song_requests.py [--talk-turns 1] [--timeout 1200]

Komentar diambil dari DEMO_COMMENTS hits-song-recommender. Tiga komentar pertama dikirim sebelum
rundown mulai, sisanya setelah lagu request pertama diputar (supaya kasus cooldown nyata).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/session?role=stage"
GAP_SEC = 15.0  # jeda antar-komentar: batas Groq gratis 8.000 token/menit

BEFORE_START = [
    ("tulus_fans", "kak puterin hati2 dijalan nya tulus dong 🥺🙏"),  # eksplisit, ada di katalog
    ("genius_lover", "req lathi weird genius dong kak 🔥"),  # tidak ada di katalog → lagu mirip
    ("anak_rantau", "lg excited bgt nungguin kakak pulang dr rantau, lagu apa ya yg cocok?? 😆"),  # mood
]
AFTER_FIRST_REQUEST = [
    ("telat_live", "kak puterin hati hati di jalan lagi dong, td telat masuk live"),  # cooldown
    ("bandung_01", "halo kak salam dari bandung 👋"),  # bukan request
    ("troll_99", "lagu buat orang2 b*doh kayak si admin, dasar t*l*l"),  # moderasi
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def post_comments(client: httpx.AsyncClient, comments: list[tuple[str, str]]) -> None:
    for i, (user, text) in enumerate(comments):
        if i:
            await asyncio.sleep(GAP_SEC)
        res = await client.post(f"{BASE}/api/comments", json={"username": user, "text": text})
        log(f"POST @{user}: {res.status_code} {res.json()['comment']['status']}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--talk-turns", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=1200)
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(60):
            rec = (await client.get(f"{BASE}/health")).json()["recommender"]
            if rec["status"] != "loading":
                break
            await asyncio.sleep(2)
        log(f"rekomendasi: {rec}")
        if rec["status"] != "ready":
            log("Rekomendasi tidak siap; jalankan backend dengan RECOMMENDER_ENABLED=true")
            return 1

        played: list[dict] = []
        first_request_aired = asyncio.Event()
        finished = asyncio.Event()
        session: dict[str, str] = {}

        async with websockets.connect(WS, max_size=None) as ws:
            async def reader() -> None:
                async for raw in ws:
                    msg = json.loads(raw)
                    kind, data = msg.get("type"), msg.get("data", {})
                    if kind == "clock_music":
                        t = data["track"]
                        played.append({"slot": data["slot_id"], "category": data.get("category"), **t})
                        who = f" (request @{t['requested_by']})" if t.get("requested_by") else ""
                        log(f"♪ {data['slot_id']:<4} [{t.get('rec_source') or '-'}] {t['title']} — {t['artist']}{who}")
                        if t.get("rec_source") == "comment":
                            first_request_aired.set()
                    elif kind == "comment":
                        log(f"komentar @{data['username']}: {data['status']} | {data['note']}")
                    elif (kind == "status" and data.get("state") in ("finished", "idle")
                          and session.get("id") and data.get("session_id") == session["id"]):
                        # Hanya akhir sesi rundown ini (status lama saat tersambung diabaikan).
                        finished.set()
                    if data.get("playback_id"):
                        # Stage tiruan: audio dianggap langsung selesai diputar.
                        await ws.send(json.dumps({"action": "playback_feedback", "data": {
                            "session_id": data.get("session_id"), "generation": data.get("generation"),
                            "playback_id": data["playback_id"], "state": "ended",
                        }}))

            reader_task = asyncio.create_task(reader())
            await post_comments(client, BEFORE_START)
            res = await client.post(f"{BASE}/api/clock/start",
                                    json={"demo_music_sec": 1, "talk_turns_per_slot": args.talk_turns})
            session_id = res.json().get("session_id")
            session["id"] = session_id
            log(f"rundown mulai: {res.json()}")

            async def later_comments() -> None:
                await first_request_aired.wait()
                await post_comments(client, AFTER_FIRST_REQUEST)

            later = asyncio.create_task(later_comments())
            try:
                await asyncio.wait_for(finished.wait(), timeout=args.timeout)
            except asyncio.TimeoutError:
                log("timeout: rundown dihentikan")
                await client.post(f"{BASE}/api/clock/stop")
            later.cancel()
            reader_task.cancel()

        snapshot = (await client.get(f"{BASE}/api/comments")).json()

    print("\n== Lagu per slot ==")
    for p in played:
        who = f"@{p['requested_by']}" if p.get("requested_by") else ""
        print(f"{p['slot']:<4} {p['category']:<9} {p.get('rec_source') or '-':<9} {p['title']} — {p['artist']} {who}")
    print("\n== Status komentar ==")
    for c in reversed(snapshot["comments"]):
        song = f"{c['song']['title']} — {c['song']['artist']}" if c.get("song") else "-"
        total = c.get("timings", {}).get("total")
        print(f"@{c['username']:<13} {c['status']:<11} {c['slot_id'] or '-':<4} {c['intent'] or '-':<14} "
              f"{song:<40} {f'{total:.2f}s' if total is not None else '-':>7} | {c['note']}")
    print(f"\nLog: backend/logs/{session_id}.music.jsonl")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
