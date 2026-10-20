"""Uji ujung-ke-ujung Talk berbasis durasi: durasi Talk, jeda antar-giliran, komentar dibacakan.

Prasyarat: backend jalan di :8000 (mis. konfigurasi ``backend-edge`` di .claude/launch.json: TTS Edge,
rekomendasi aktif untuk moderasi komentar). Tutup semua tab /stage. Skrip ini tersambung sebagai
stage dan mengonfirmasi setiap audio setelah durasinya habis (seolah benar-benar diputar), jadi jeda
antar-giliran terukur seperti di live.

    python scripts/e2e_talk_duration.py [--until s13] [--timeout 1200]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict

import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/session?role=stage"

COMMENTS = [
    ("budi_bdg", "halo kak salam dari bandung, lagi otw kampus nih"),
    ("sari_maba", "kak aku maba juga, ospek minggu depan deg2an"),
    ("andi", "kak puterin hati2 dijalan tulus dong"),
    ("barca_fan", "visca barca!!"),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--until", default="s13", help="hentikan rundown setelah slot ini selesai")
    parser.add_argument("--timeout", type=float, default=1200)
    args = parser.parse_args()

    turns: dict[str, list[dict]] = defaultdict(list)
    points: dict[str, list[str]] = defaultdict(list)
    reads: list[dict] = []
    done = asyncio.Event()
    session: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(60):
            rec = (await client.get(f"{BASE}/health")).json()["recommender"]
            if rec["status"] != "loading":
                break
            await asyncio.sleep(2)
        log(f"rekomendasi: {rec['status']}")

        async with websockets.connect(WS, max_size=None) as ws:
            async def ack(data: dict, after: float) -> None:
                await asyncio.sleep(after)
                await ws.send(json.dumps({"action": "playback_feedback", "data": {
                    "session_id": data.get("session_id"), "generation": data.get("generation"),
                    "playback_id": data["playback_id"], "state": "ended"}}))

            async def reader() -> None:
                async for raw in ws:
                    msg = json.loads(raw)
                    kind, data = msg.get("type"), msg.get("data", {})
                    now = time.perf_counter()
                    if kind == "turn":
                        turns[data["slot_id"]].append({"t": now, "dur": data.get("duration_sec") or 0,
                                                       "who": data.get("persona_name"), "text": data.get("text", "")})
                    elif kind == "theme_change" and data.get("slot_id"):
                        points[data["slot_id"]].append(data["title"])
                    elif kind == "comment_read":
                        reads.append(data)
                        log(f"komentar dibacakan: @{data['username']} di {data['slot_id']}")
                    elif kind == "clock_slot_started":
                        log(f"slot {data['slot_id']} ({data['label']}) mulai")
                    elif kind == "clock_slot_completed" and data.get("slot_id") == args.until:
                        done.set()
                    elif kind == "status" and data.get("state") in ("finished", "idle") \
                            and session.get("id") and data.get("session_id") == session["id"]:
                        done.set()
                    if data.get("playback_id"):
                        # Stage tiruan: giliran dianggap selesai diputar setelah durasinya habis.
                        after = data.get("duration_sec") if kind == "turn" else 1.0
                        asyncio.create_task(ack(data, float(after or 1.0)))

            reader_task = asyncio.create_task(reader())
            res = await client.post(f"{BASE}/api/clock/start", json={"demo_music_sec": 5})
            session["id"] = res.json().get("session_id", "")
            log(f"rundown mulai: {res.json()}")
            for user, text in COMMENTS:
                r = await client.post(f"{BASE}/api/comments", json={"username": user, "text": text})
                log(f"POST @{user}: {r.json()['comment']['status']}")
                await asyncio.sleep(12)  # jeda untuk batas token/menit Groq
            try:
                await asyncio.wait_for(done.wait(), timeout=args.timeout)
            except asyncio.TimeoutError:
                log("timeout")
            await client.post(f"{BASE}/api/clock/stop")
            reader_task.cancel()
        snapshot = (await client.get(f"{BASE}/api/comments")).json()

    print("\n== Talk per slot ==")
    for slot_id, items in turns.items():
        if len(items) < 3:
            continue
        spoken = sum(i["dur"] for i in items)
        # Jeda = mulai giliran n+1 dikurangi akhir audio giliran n.
        gaps = [b["t"] - (a["t"] + a["dur"]) for a, b in zip(items, items[1:])]
        print(f"{slot_id}: {len(items)} giliran, audio {spoken:.0f} s, wall {items[-1]['t'] + items[-1]['dur'] - items[0]['t']:.0f} s, "
              f"jeda rata2 {sum(gaps) / len(gaps):.2f} s, maks {max(gaps):.2f} s")
        print(f"   poin: {points.get(slot_id, [])}")
        print(f"   pertama: {items[0]['who']}: {items[0]['text'][:160]}")
        print(f"   terakhir: {items[-1]['who']}: {items[-1]['text'][:200]}")
    print("\n== Komentar ==")
    for c in reversed(snapshot["comments"]):
        print(f"@{c['username']:<10} {c['status']:<9} {c['slot_id'] or '-':<4} {c['note']}")
    print(f"\ncomment_read events: {[r['username'] for r in reads]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
