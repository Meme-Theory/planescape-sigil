#!/bin/bash
# usage: fandom_export.sh <wiki-base-url> <outdir>
W="$1"; OUT="$2"
cd "$OUT" || exit 1
APFROM=""
> titles.txt
while :; do
  R=$(curl -s -m 60 -G "$W/api.php" --data-urlencode "action=query" --data-urlencode "list=allpages" --data-urlencode "aplimit=500" --data-urlencode "format=json" --data-urlencode "apfrom=$APFROM")
  echo "$R" | jq -r '.query.allpages[].title' >> titles.txt
  APFROM=$(echo "$R" | jq -r '.continue.apcontinue // empty')
  [ -z "$APFROM" ] && break
  sleep 1
done
echo "titles: $(wc -l < titles.txt)"
split -l 40 titles.txt batch_
i=0
for f in batch_*; do
  i=$((i+1))
  TITLES=$(paste -sd'|' "$f")
  curl -s -m 120 -G "$W/api.php" --data-urlencode "action=query" --data-urlencode "export=1" --data-urlencode "exportnowrap=1" --data-urlencode "titles=$TITLES" -o "export_$(printf %03d $i).xml"
  sleep 1
done
rm -f batch_*
echo "EXPORT COMPLETE: $i batches"
