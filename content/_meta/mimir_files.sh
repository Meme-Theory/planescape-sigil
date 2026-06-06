#!/bin/bash
M=C:/sandbox/Planescape/content/_meta/tmp
NB=C:/sandbox/Planescape/content/fan/mimir-netbooks
MF=C:/sandbox/Planescape/content/fan/mimir/files
mkdir -p "$NB" "$MF"
# 1) all PDFs from netbooks page
grep -oE 'https?://mimir\.net/[^"'"'"' ]+\.pdf' $M/netbooks.html | sort -u > $M/nb_pdfs.txt
echo "netbook pdfs: $(wc -l < $M/nb_pdfs.txt)"
cd "$NB"
while IFS= read -r u; do curl -sL -m 180 "$u" -O; sleep 0.7; done < $M/nb_pdfs.txt
# 2) all pdf/zip links across the whole wp-json corpus, minus ones we already have
cd C:/sandbox/Planescape/content/fan/mimir
cat mimir_posts_*.json mimir_pages_*.json 2>/dev/null | jq -r '.[]?.content.rendered // empty' | grep -oE 'https?://mimir\.net/[^"'"'"' ]+\.(pdf|zip)' | sort -u > $M/corpus_files.txt
comm -23 $M/corpus_files.txt $M/nb_pdfs.txt > $M/corpus_new.txt
echo "corpus extra files: $(wc -l < $M/corpus_new.txt)"
cd "$MF"
while IFS= read -r u; do curl -sL -m 180 "$u" -O; sleep 0.7; done < $M/corpus_new.txt
echo "MIMIR FILES COMPLETE: netbooks=$(ls "$NB" | wc -l) extras=$(ls "$MF" | wc -l)"
