#!/bin/bash
# reddit_index_scan.sh - Tier-2 Reddit coverage via search index (owner exception, route B).
# Runs the fixed vein query set, dedupes by URL, logs in-window (<=30d) threads to pain_log.md.
# Dates from the index are month-accurate estimates; logged with "reddit-idx" source tag.
cd "$(dirname "$0")"
SEEN=seen_reddit.json
[ -f "$SEEN" ] || echo "[]" > "$SEEN"
CUTOFF=$(date -d "30 days ago" +%Y-%m-%d)
NEW=0
run_query () {
  local q="$1"
  tools web_search --query "$q" --include-domain reddit.com --limit 10 --json 2>/dev/null > /tmp/riq.json || return
  jq -r '.[]? | [.published_date, .url, ((.highlights // []) | join(" ") | gsub("[\n|]"; " ") | .[0:220])] | @tsv' /tmp/riq.json 2>/dev/null | \
  while IFS=$'\t' read -r pd url hl; do
    [[ "$url" == *reddit.com/r/* ]] || continue
    grep -q "\"$url\"" "$SEEN" && continue
    jq --arg u "$url" '. + [$u]' "$SEEN" > "$SEEN.tmp" && mv "$SEEN.tmp" "$SEEN"
    [[ "$pd" < "$CUTOFF" ]] && continue   # out of 30-day window: seen but not logged
    pain="no"; wtp="no"
    echo "$hl" | grep -iEq "is there a tool|looking for|how do you|manually|spreadsheet|frustrat|nightmare|too expensive|rip.?off|complaint|problem|issue|leaving|switch|ditch|alternative|hate|clunky|confusing|overpriced|price (hike|increase|creep)" && pain="context"
    echo "$hl" | grep -iEq "i'?d pay|would pay|paying \$?[0-9]+|\$[0-9]+/(mo|month)|willing to pay" && wtp="yes"
    [ "$pain" = "no" ] && continue
    title=$(echo "$hl" | cut -c1-110)
    echo "${pd:-????-??-??} | reddit-idx | $url | $title | not extracted | WTP: $wtp | search-index" >> ../pain_log.md
    NEW=$((NEW+1))
    echo "SIGNAL: ${pd} | $url | ${title:0:80}"
  done
  sleep 1
}
run_query "mindbody leaving OR switching OR price increase OR alternative"
run_query "vagaro complaint OR problem OR expensive salon"
run_query "booksy business owner fees OR rip off OR complaint"
run_query "glossgenius problem OR missing feature OR expensive"
run_query "salon OR spa booking software too expensive OR frustrating owner"
run_query "fitness studio gym software complaint OR switching"
run_query "fresha OR acuity scheduling complaint business owner"
run_query "small business software is there a tool looking for"
# weekly rotation veins
[ -f reddit_queries_rotation.txt ] && while IFS= read -r q; do
  [[ "$q" =~ ^#|^$ ]] && continue
  run_query "$q"
done < reddit_queries_rotation.txt
echo "reddit-index scan complete: $NEW new signals"
