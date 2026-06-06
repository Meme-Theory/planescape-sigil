#!/bin/bash
# Two-level crawl of mimir.planewalker.com PSCS section for PDFs
M=C:/sandbox/Planescape/content/_meta/tmp
OUT=C:/sandbox/Planescape/content/fan/planewalker-pscs
cd "$OUT" || exit 1
BASE="https://mimir.planewalker.com"
curl -sL -m 60 "$BASE/sections/30-35-pscs" -o $M/pscs_section.html
# collect node/page links
grep -oE 'href="[^"]+"' $M/pscs_section.html | sed 's/href="//;s/"$//' | grep -vE '\.(css|js|png|jpg|gif|ico)|^#|^mailto' | grep -E '^/' | sort -u > $M/pscs_links.txt
echo "section links: $(wc -l < $M/pscs_links.txt)"
# fetch each, harvest pdf links
> $M/pscs_pdfs.txt
while IFS= read -r l; do
  curl -sL -m 60 "$BASE$l" | grep -oE 'href="[^"]+\.pdf"' | sed 's/href="//;s/"$//' >> $M/pscs_pdfs.txt
  sleep 1
done < $M/pscs_links.txt
sort -u $M/pscs_pdfs.txt > $M/pscs_pdfs_u.txt
echo "pdf links found: $(wc -l < $M/pscs_pdfs_u.txt)"
while IFS= read -r p; do
  case "$p" in http*) u="$p";; /*) u="$BASE$p";; *) u="$BASE/$p";; esac
  fn=$(basename "$u" | sed 's/%20/_/g')
  curl -sL -m 120 "$u" -o "$fn"
  sleep 1
done < $M/pscs_pdfs_u.txt
echo "PSCS CRAWL COMPLETE:"; ls -la
