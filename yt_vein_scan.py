#!/usr/bin/env python3
"""Targeted YouTube vein hunt for H-A (salon/fitness booking software pain).
Reuses scan_v2 machinery (classify, line, yt_get, dedupe via seen_v2.json)."""
import sys, datetime, time
sys.path.insert(0, '.')
from scan_v2 import classify, line, yt_get, seen, save_seen, NOW, CUTOFF

QUERIES = ["Mindbody review business owner", "Vagaro honest review salon", "salon booking software review owner",
           "leaving Mindbody switch", "Booksy business owner review", "GlossGenius review salon owner"]
out, s = [], seen()
for q in QUERIES:
    try:
        res = yt_get("search", {"part": "snippet", "q": q, "type": "video", "order": "date", "maxResults": 8,
                                "publishedAfter": (NOW - datetime.timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")})
        for v in res.get("items", [])[:3]:
            vid = v.get("id", {}).get("videoId", "")
            if not vid: continue
            try:
                ct = yt_get("commentThreads", {"part": "snippet", "videoId": vid, "maxResults": 30, "order": "relevance"})
                for c in ct.get("items", []):
                    cid = f"ytc:{c.get('id','')}"
                    if cid in s: continue
                    s.add(cid)
                    top = c.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                    try:
                        if datetime.datetime.fromisoformat(top.get("publishedAt","").replace("Z","+00:00")).timestamp() < CUTOFF: continue
                    except Exception: pass
                    pain, wtp = classify(top.get("textDisplay",""))
                    if pain:
                        out.append(line(top.get("publishedAt","")[:10], "youtube:comment",
                            f"https://www.youtube.com/watch?v={vid}&lc={c.get('id','')}",
                            top.get("textDisplay","")[:120], wtp, f"{top.get('likeCount',0)} likes / q:{q[:25]}"))
            except Exception as e:
                print(f"WARN comments {vid}: {e}", file=sys.stderr)
            time.sleep(1)
    except Exception as e:
        print(f"WARN search {q}: {e}", file=sys.stderr)
    time.sleep(1)
if out:
    with open("../pain_log.md", "a") as f:
        for l in out: f.write(l + "\n")
save_seen(s)
print(f"yt vein scan complete: {len(out)} new signals")
for l in out: print("SIGNAL:", l[:160])
