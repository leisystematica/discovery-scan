#!/usr/bin/env python3
"""scan_v2 - Lei Systematica pain scanner, plan B (route B approved 2026-10-07).
Tier-1 sources: HN (Algolia), Stack Exchange, App Store review RSS (no auth); Bluesky + YouTube Data API + Product Hunt GraphQL (accounts approved by owner 2026-10-07, keys in vault, creds in gitignored scanner/.env).
Tier-2 Reddit runs separately in-session via site-restricted search-index queries (owner exception granted).
Read-only; respects each source's API terms. Rebuilt 2026-10-09 after workspace loss (v2.3)."""
import json, os, re, sys, time, urllib.request, urllib.parse, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PAIN = re.compile(r"(is there a tool|any tool|looking for a (tool|app|software)|how do you (all )?(handle|manage|track|deal)|i do this manually|manually every|every week|spreadsheet|tedious|frustrat|nightmare|hate (doing|how)|wish there was|drives me crazy|waste(s)? (of )?time|takes (me )?hours|recommend (a|an|some)? ?(tool|app|software)|what do you use (for|to)|only use(s)? (it|them|the app) for|too expensive|bloated|overkill|paying for features|cheaper alternative|looking for an alternative|switched? (from|away))", re.I)
WTP = re.compile(r"(i'?d pay|would pay|happily pay|i will pay|willing to pay|pay for (a|an|this|something)|worth paying|paying for|charge me|spend money|budget for|take my money)", re.I)
UA = {"User-Agent": "LeiSystematica-discovery-scan/0.2 (read-only market research)"}

def load_env():
    env = {}
    ep = os.path.join(BASE, ".env")
    if os.path.exists(ep):
        for ln in open(ep):
            if "=" in ln and not ln.startswith("#"):
                k, v = ln.strip().split("=", 1); env[k] = v
    return env
ENV = load_env()
SE_SITES = ["workplace", "freelancing", "money", "law", "webmasters", "pm"]
APP_TERMS = [
    # trades / field service (strongest cluster - keep)
    "Jobber", "Housecall Pro", "Workiz", "ServiceTitan Mobile",
    # accounting / invoicing
    "QuickBooks Accounting", "Xero Accounting", "FreshBooks", "Wave Invoicing", "Invoice2go",
    # freelancer / client admin
    "HoneyBook", "Bonsai", "Dubsado",
    # salon / spa / beauty booking
    "Vagaro", "Booksy Biz", "GlossGenius", "Fresha for business",
    # fitness studios
    "Mindbody Business", "Glofox",
    # scheduling / appointments
    "Square Appointments", "Setmore", "Acuity Scheduling",
]
NOW = datetime.datetime.now(datetime.timezone.utc)
CUTOFF = (NOW - datetime.timedelta(days=30)).timestamp()

def get(url, as_json=True):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r) if as_json else r.read().decode("utf-8", "replace")

def seen():
    p = os.path.join(BASE, "seen_v2.json")
    return set(json.load(open(p))) if os.path.exists(p) else set()

def save_seen(s):
    json.dump(sorted(s), open(os.path.join(BASE, "seen_v2.json"), "w"))

def classify(text):
    t = re.sub(r"<[^>]+>", " ", text or "")[:4000]
    return bool(PAIN.search(t)), bool(WTP.search(t))

def line(date, source, link, pain, wtp, pop):
    pain = re.sub(r"\s+", " ", pain).strip()[:120]
    return f"{date} | {source} | {link} | {pain} | not extracted | WTP: {'yes' if wtp else 'no'} | {pop}"

def scan_hn(out, seen_ids):
    for q in ['"is there a tool"', '"I\'d pay for"', '"how do you handle"', '"I do this manually"']:
        url = "https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode({
            "query": q, "tags": "(story,comment)", "hitsPerPage": 30})
        try:
            for h in get(url).get("hits", []):
                oid = h.get("objectID")
                if not oid or oid in seen_ids or (h.get("created_at_i") or 0) < CUTOFF: continue
                seen_ids.add(oid)
                pain, wtp = classify((h.get("title") or "") + " " + (h.get("comment_text") or h.get("story_text") or ""))
                if pain:
                    link = f"https://news.ycombinator.com/item?id={h.get('story_id') or oid}"
                    out.append(line(h.get("created_at", "")[:10], "hn", link, h.get("title") or (h.get("comment_text") or "")[:120], wtp, f"{h.get('points') or '-'} pts / {h.get('num_comments') or '-'} comments"))
        except Exception as e: print(f"WARN hn {q}: {e}", file=sys.stderr)
        time.sleep(1)

def scan_se(out, seen_ids):
    for site in SE_SITES:
        for q in ["how do you handle", "is there a tool", "manually", "looking for software", "recommend a tool", "alternative to", "too expensive"]:
            url = "https://api.stackexchange.com/2.3/search/advanced?" + urllib.parse.urlencode({
                "order": "desc", "sort": "creation", "site": site, "q": q, "pagesize": 25, "filter": "withbody"})
            try:
                for it in get(url).get("items", []):
                    qid = f"{site}:{it.get('question_id')}"
                    if qid in seen_ids or (it.get("creation_date") or 0) < CUTOFF: continue
                    seen_ids.add(qid)
                    pain, wtp = classify((it.get("title") or "") + " " + (it.get("body") or ""))
                    if pain:
                        d = datetime.datetime.fromtimestamp(it["creation_date"], datetime.timezone.utc).strftime("%Y-%m-%d")
                        out.append(line(d, f"se:{site}", it.get("link", ""), it.get("title", ""), wtp, f"{it.get('score',0)} score / {it.get('answer_count',0)} answers"))
            except Exception as e: print(f"WARN se {site}: {e}", file=sys.stderr)
            time.sleep(1)

def scan_appstore(out, seen_ids):
    for term in APP_TERMS:
        try:
            res = get("https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": term, "entity": "software", "limit": 1, "country": "us"}))
            hits = res.get("results", [])
            if not hits: continue
            appid, name = hits[0]["trackId"], hits[0]["trackName"]
            entries = []
            for attempt in range(3):
                rv = get(f"https://itunes.apple.com/us/rss/customerreviews/id={appid}/sortby=mostrecent/json")
                entries = rv.get("feed", {}).get("entry") or []
                if entries: break
                time.sleep(2 + attempt * 2)
            for e in entries[:50]:
                rid = f"app:{appid}:{e.get('id',{}).get('label','')}"
                if rid in seen_ids: continue
                try:
                    if datetime.datetime.fromisoformat(e.get("updated",{}).get("label","").replace("Z","+00:00")).timestamp() < CUTOFF: continue
                except Exception: pass
                seen_ids.add(rid)
                text = (e.get("title", {}).get("label", "") + " " + e.get("content", {}).get("label", ""))
                pain, wtp = classify(text)
                if pain:
                    rating = e.get("im:rating", {}).get("label", "?")
                    out.append(line(e.get("updated", {}).get("label", "")[:10], f"appstore:{name}", e.get("link", {}).get("attributes", {}).get("href", f"https://apps.apple.com/app/id{appid}"), e.get("title", {}).get("label", ""), wtp, f"{rating} stars"))
        except Exception as e: print(f"WARN appstore {term}: {e}", file=sys.stderr)
        time.sleep(1)

def bsky_session():
    req = urllib.request.Request("https://bsky.social/xrpc/com.atproto.server.createSession",
        data=json.dumps({"identifier": ENV.get("BSKY_HANDLE",""), "password": ENV.get("BSKY_PASSWORD","")}).encode(),
        headers={"Content-Type": "application/json", **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("accessJwt")

def scan_bsky(out, seen_ids):
    try: jwt = bsky_session()
    except Exception as e:
        print(f"WARN bsky session: {e}", file=sys.stderr); return
    for q in ["is there a tool", "I would pay for", "how do you handle", "do this manually", "wish there was an app",
              "my small business software", "invoice my clients", "manage my clients", "schedule my employees", "track my time freelance",
              "paying for QuickBooks", "too expensive for my business", "only use it for"]:
        url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts?" + urllib.parse.urlencode({"q": q, "sort": "latest", "limit": 25})
        try:
            req = urllib.request.Request(url, headers={**UA, "Authorization": f"Bearer {jwt}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                posts = json.load(r).get("posts", [])
            for p in posts:
                uri = p.get("uri", "")
                if uri in seen_ids: continue
                seen_ids.add(uri)
                rec = p.get("record", {})
                created = rec.get("createdAt", "")
                try:
                    if datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp() < CUTOFF: continue
                except Exception: pass
                pain, wtp = classify(rec.get("text", ""))
                if pain:
                    rkey = uri.rsplit("/",1)[-1]; web = f"https://bsky.app/profile/{p.get('author',{}).get('handle','')}/post/{rkey}"
                    out.append(line(created[:10], "bluesky", web, rec.get("text", "")[:120], wtp, f"{p.get('likeCount',0)} likes / {p.get('replyCount',0)} replies"))
        except Exception as e: print(f"WARN bsky {q}: {e}", file=sys.stderr)
        time.sleep(1)

def yt_get(path, params):
    params = {**params, "key": ENV.get("YT_KEY") or ENV.get("YOUTUBE_KEY","")}
    return get("https://www.googleapis.com/youtube/v3/" + path + "?" + urllib.parse.urlencode(params))

def scan_youtube(out, seen_ids):
    # search.list costs 100 quota units each - keep queries few (10k/day free)
    queries = ["plumber software problem", "field service software complaint", "QuickBooks nightmare", "salon software problem", "cleaning business software",
               "booking software problem", "restaurant POS complaint", "Mindbody problems", "invoicing app small business", "freelance client management"]
    published_after = (NOW - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for q in queries:
        try:
            res = yt_get("search", {"part": "snippet", "q": q, "type": "video", "order": "date", "maxResults": 10, "publishedAfter": published_after})
            vids = res.get("items", [])
            for v in vids:
                vid = v.get("id", {}).get("videoId", "")
                if not vid or f"ytv:{vid}" in seen_ids: continue
                seen_ids.add(f"ytv:{vid}")
                sn = v.get("snippet", {})
                pain, wtp = classify((sn.get("title","")) + " " + (sn.get("description",""))[:300])
                if pain:
                    out.append(line(sn.get("publishedAt","")[:10], "youtube:video", f"https://www.youtube.com/watch?v={vid}", sn.get("title",""), wtp, f"ch: {sn.get('channelTitle','')[:30]}"))
            for v in vids[:3]:
                vid = v.get("id", {}).get("videoId", "")
                if not vid: continue
                try:
                    ct = yt_get("commentThreads", {"part": "snippet", "videoId": vid, "maxResults": 20, "order": "relevance"})
                    for c in ct.get("items", []):
                        cid = f"ytc:{c.get('id','')}"
                        if cid in seen_ids: continue
                        seen_ids.add(cid)
                        top = c.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                        pain, wtp = classify(top.get("textDisplay",""))
                        if pain:
                            out.append(line(top.get("publishedAt","")[:10], "youtube:comment", f"https://www.youtube.com/watch?v={vid}&lc={c.get('id','')}", top.get("textDisplay","")[:120], wtp, f"{top.get('likeCount',0)} likes"))
                except Exception as e: print(f"WARN yt comments {vid}: {e}", file=sys.stderr)
                time.sleep(1)
        except Exception as e: print(f"WARN yt {q}: {e}", file=sys.stderr)
        time.sleep(1)

def ph_gql(query):
    req = urllib.request.Request("https://api.producthunt.com/v2/api/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {ENV.get('PH_TOKEN','')}", **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def scan_producthunt(out, seen_ids):
    q = '{ posts(first: 20, order: NEWEST, topic: "saas") { edges { node { id name tagline description votesCount commentsCount createdAt url } } } }'
    try:
        for e in (ph_gql(q).get("data", {}).get("posts", {}) or {}).get("edges", []):
            n = e.get("node", {})
            pid = f"ph:{n.get('id','')}"
            if not n.get("id") or pid in seen_ids: continue
            seen_ids.add(pid)
            try:
                if datetime.datetime.fromisoformat(n.get("createdAt","").replace("Z","+00:00")).timestamp() < CUTOFF: continue
            except Exception: pass
            pain, wtp = classify((n.get("tagline","")) + " " + re.sub(r"<[^>]+>"," ",n.get("description") or "")[:400])
            if pain:
                out.append(line(n.get("createdAt","")[:10], "producthunt", n.get("url",""), f"{n.get('name','')} - {n.get('tagline','')}"[:120], wtp, f"{n.get('votesCount',0)} votes / {n.get('commentsCount',0)} comments"))
            cq = '{ post(id: "%s") { comments(first: 15) { edges { node { id body createdAt votesCount url } } } } }' % n.get("id","")
            try:
                cs = (ph_gql(cq).get("data", {}).get("post", {}) or {}).get("comments", {}).get("edges", [])
                for ce in cs:
                    cn = ce.get("node", {})
                    cid = f"phc:{cn.get('id','')}"
                    if cid in seen_ids: continue
                    seen_ids.add(cid)
                    try:
                        if datetime.datetime.fromisoformat(cn.get("createdAt","").replace("Z","+00:00")).timestamp() < CUTOFF: continue
                    except Exception: pass
                    pain, wtp = classify(cn.get("body",""))
                    if pain:
                        out.append(line(cn.get("createdAt","")[:10], "producthunt:comment", cn.get("url","") or n.get("url",""), cn.get("body","")[:120], wtp, f"{cn.get('votesCount',0)} votes"))
            except Exception as e2: print(f"WARN ph comments {n.get('id')}: {e2}", file=sys.stderr)
            time.sleep(1)
    except Exception as e: print(f"WARN ph posts: {e}", file=sys.stderr)

def main():
    out, s = [], seen()
    scan_hn(out, s); scan_se(out, s); scan_appstore(out, s)
    scan_bsky(out, s); scan_youtube(out, s); scan_producthunt(out, s)  # authenticated sources approved 2026-10-07
    if out:
        with open(os.path.join(BASE, "..", "pain_log.md"), "a") as f:
            for l in out: f.write(l + "\n")
    save_seen(s)
    print(f"scan_v2 complete: {len(out)} new signals")
    for l in out: print("SIGNAL:", l)

if __name__ == "__main__":
    main()
