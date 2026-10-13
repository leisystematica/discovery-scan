#!/bin/bash
# reviewsite_index_scan.sh - H-A second source via search-index over public review sites.
# ENABLED 2026-10-13: owner approved ("also yes extend the scan to trustpilot/ sitejabber",
# wamid.HBgLMTMxMDk5MDU3NjUVAgASGBQzQTdBREM5NkRBQTYxNjk4QUUwOQA=, Oct 13 9:59am).
# Reads public search-index results only; never touches trustpilot/sitejabber servers.
# In-window (<=30d) -> pain_log.md (promotion-eligible). Older/null-date -> research/h-a-reviewsite-context.md (durable context).
cd "$(dirname "$0")"
SEEN=seen_reviewsites.json
[ -f "$SEEN" ] || echo "[]" > "$SEEN"
CUTOFF=$(date -d "30 days ago" +%Y-%m-%d)
NEW=0; CTX=0
run_query () {
  local q="$1"
  tools web_search --query "$q" --include-domain trustpilot.com --limit 8 --json 2>/dev/null > /tmp/rsq.json || return
  tools web_search --query "$q" --include-domain sitejabber.com --limit 5 --json 2>/dev/null > /tmp/rsq2.json || cp /dev/null /tmp/rsq2.json
  jq -s 'add // []' /tmp/rsq.json /tmp/rsq2.json > /tmp/rsqb.json 2>/dev/null || cp /tmp/rsq.json /tmp/rsqb.json
  while IFS=$'\t' read -r pd url hl; do
    case "$url" in *trustpilot.com/review/*|*trustpilot.com/users/*|*sitejabber.com/reviews/*) ;; *) continue;; esac
    grep -q "\"$url\"" "$SEEN" && continue
    jq --arg u "$url" '. + [$u]' "$SEEN" > "$SEEN.tmp" && mv "$SEEN.tmp" "$SEEN"
    pain="no"; wtp="no"
    echo "$hl" | grep -iEq "expensive|rip.?off|price (hike|increase|creep)|per (user|staff|calendar|location)|commission|fee|locked|trapped|cancel|switch|leaving|alternative|clunky|buggy|glitch|support (is|was) (bad|terrible|non)|charged|billing|not very happy|weak|many issues" && pain="context"
    echo "$hl" | grep -iEq "i'?d pay|would pay|paying \$?[0-9]+|\$[0-9]+/(mo|month)|willing to pay" && wtp="yes"
    [ "$pain" = "no" ] && continue
    title=$(echo "$hl" | cut -c1-110)
    if [[ -n "$pd" && ! "$pd" < "$CUTOFF" ]]; then
      echo "${pd} | reviewsite-idx | $url | $title | not extracted | WTP: $wtp | search-index" >> ../pain_log.md
      NEW=$((NEW+1)); echo "SIGNAL: ${pd} | $url | ${title:0:80}"
    else
      echo "${pd:-????-??-??} | $url | $title" >> ../research/h-a-reviewsite-context.md
      CTX=$((CTX+1)); echo "CONTEXT: ${pd:-null} | $url | ${title:0:60}"
    fi
  done < <(jq -r '.[]? | [.published_date // "", .url, ((.highlights // []) | join(" ") | gsub("[\n|]"; " ") | .[0:220])] | @tsv' /tmp/rsqb.json 2>/dev/null)
  sleep 1
}
run_query "mindbody trustpilot expensive OR price OR increase"
run_query "mindbody trustpilot switch OR leaving OR cancel"
run_query "vagaro trustpilot complaint OR problem OR expensive"
run_query "booksy trustpilot fee OR boost OR complaint"
run_query "fresha trustpilot commission OR fee OR complaint"
run_query "glossgenius trustpilot reviews"
run_query "boulevard software trustpilot reviews"
run_query "momence trustpilot reviews"
echo "review-site index scan complete: $NEW in-window signals, $CTX context items"
