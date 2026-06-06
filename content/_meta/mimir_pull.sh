#!/bin/bash
cd C:/sandbox/Planescape/content/fan/mimir
for ep in posts pages categories tags; do
  P=1
  while :; do
    OUT="mimir_${ep}_$(printf %03d $P).json"
    curl -s -m 90 "https://mimir.net/wp-json/wp/v2/${ep}?per_page=100&page=${P}" -o "$OUT"
    CNT=$(jq 'if type=="array" then length else 0 end' "$OUT" 2>/dev/null || echo 0)
    if [ "$CNT" = "0" ] || [ -z "$CNT" ]; then rm -f "$OUT"; break; fi
    P=$((P+1))
    sleep 1
  done
  echo "$ep done: $(ls mimir_${ep}_*.json 2>/dev/null | wc -l) files"
done
echo "MIMIR PULL COMPLETE"
