#!/bin/bash
# usage: wiki_export_fixed.sh <api-base-url-without-/api.php> <outdir> [api-path]
# CRLF-safe MediaWiki bulk exporter (native Windows jq emits \r\n!)
W="$1"; OUT="$2"; API="${3:-api.php}"
cd "$OUT" || exit 1
rm -f export_*.xml titles*.txt batch_*
APFROM=""
> titles_raw.txt
while :; do
  R=$(curl -s -m 60 -G "$W/$API" --data-urlencode "action=query" --data-urlencode "list=allpages" --data-urlencode "aplimit=500" --data-urlencode "format=json" --data-urlencode "apfrom=$APFROM")
  echo "$R" | jq -r '.query.allpages[]?.title' | tr -d '\r' >> titles_raw.txt
  APFROM=$(echo "$R" | jq -r '.continue.apcontinue // empty' | tr -d '\r')
  [ -z "$APFROM" ] && break
  sleep 1
done
sort -u titles_raw.txt | grep -v '^$' > titles.txt
rm -f titles_raw.txt
echo "titles: $(wc -l < titles.txt)"
split -l 40 titles.txt batch_
i=0
for f in batch_*; do
  i=$((i+1))
  TITLES=$(tr -d '\r' < "$f" | paste -sd'|')
  curl -s -m 120 -G "$W/$API" --data-urlencode "action=query" --data-urlencode "export=1" --data-urlencode "exportnowrap=1" --data-urlencode "titles=$TITLES" -o "export_$(printf %03d $i).xml"
  sleep 1
done
rm -f batch_*
PAGES=$(cat export_*.xml | grep -o '<page>' | wc -l)
echo "EXPORT COMPLETE: $i batches, $PAGES pages"
