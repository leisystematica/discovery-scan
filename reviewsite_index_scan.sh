#!/bin/bash
# reviewsite_index_scan.sh - H-A second source via search-index over public review sites.
# STATUS: PREPARED 2026-10-12, NOT ENABLED. Awaits owner yes (same route-B technique she
# approved for Reddit Oct 7 9:32am, but the grant named Reddit specifically - do not run
# until she explicitly extends it to review sites).
# Reads public search-index results only; never touches trustpilot/sitejabber servers.
cd "$(dirname "$0")"
SEEN=seen_reviewsites.json
[ -f "$SEEN" ] || echo "[]" > "$SEEN"
CUTOFF=$(date -d "30 days ago" +%Y-%m-%d)
NEW=0
run_query () {
  local q="$1"
  tools web_search --query "$q" --include-domain trustpilot.com --include-domain sitejabber.com --limit 10 --json 2>/dev/null > /tmp/rsq.json || return
  while IFS=$'\t' read -r pd url hl; do
    [[ "$url" == *trustpilot.com/review/* || "$url" == *sitejabber.com/reviews/* ]] || continue
    grep -q "\"$url\"" "$SEEN" && continue
    jq --arg u "$url" '. + [$u]' "$SEEN" > "$SEEN.tmp" && mv "$SEEN.tmp" "$SEEN"
    [[ "$pd" < "$CUTOFF" ]] && continue
    pain="no"; wtp="no"
    echo "$hl" | grep -iEq "expensive|rip.?off|price (hike|increase|creep)|per (user|staff|calendar|location)|commission|fee|locked|trapped|cancel|switch|leaving|alternative|clunky|buggy|glitch|support (is|was) (bad|terrible|non)|charged|billing" && pain="context"
    echo "$hl" | grep -iEq "i'?d pay|would pay|paying \$?[0-9]+|\$[0-9]+/(mo|month)|willing to pay" && wtp="yes"
    [ "$pain" = "no" ] && continue
    title=$(echo "$hl" | cut -c1-110)
    echo "${pd:-????-??-??} | reviewsite-idx | $url | $title | not extracted | WTP: $wtp | search-index" >> ../pain_log.md
    NEW=$((NEW+1))
    echo "SIGNAL: ${pd} | $url | ${title:0:80}"
  done < <(jq -r '.[]? | [.published_date, .url, ((.highlights // []) | join(" ") | gsub("[\n|]"; " ") | .[0:220])] | @tsv' /tmp/rsq.json 2>/dev/null)
  sleep 1
}
run_query "mindbody reviews owner"
run_query "vagaro reviews salon owner"
run_query "booksy reviews business"
run_query "fresha reviews salon"
run_query "glossgenius reviews"
run_query "boulevard software reviews"
run_query "momence reviews studio"
echo "review-site index scan complete: $NEW new signals"
