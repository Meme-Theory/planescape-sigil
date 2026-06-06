#!/bin/bash
W="https://forgottenrealms.fandom.com"
OUT="C:/sandbox/Planescape/content/wikis/forgotten-realms-wiki"
cd "$OUT" || exit 1
> titles.txt
for CAT in "Planescape" "Planescape sourcebooks" "Planes of existence" "Outer planes" "Inner planes" "Transitive planes" "Sigil" "Locations in Sigil" "Inhabitants of Sigil" "Portals" "Layers of the Abyss" "Celestial paragons" "Archdevils" "Demon lords" "Modrons" "Githyanki" "Githzerai" "Yugoloths"; do
  CMCONT=""
  while :; do
    R=$(curl -s -m 60 -G "$W/api.php" --data-urlencode "action=query" --data-urlencode "list=categorymembers" --data-urlencode "cmtitle=Category:$CAT" --data-urlencode "cmlimit=500" --data-urlencode "cmtype=page" --data-urlencode "format=json" --data-urlencode "cmcontinue=$CMCONT")
    echo "$R" | jq -r '.query.categorymembers[]?.title' >> titles.txt
    CMCONT=$(echo "$R" | jq -r '.continue.cmcontinue // empty')
    [ -z "$CMCONT" ] && break
    sleep 1
  done
  sleep 1
done
sort -u titles.txt | grep -v '^$' > titles_u.txt
echo "unique titles: $(wc -l < titles_u.txt)"
split -l 40 titles_u.txt batch_
i=0
for f in batch_*; do
  i=$((i+1))
  TITLES=$(paste -sd'|' "$f")
  curl -s -m 120 -G "$W/api.php" --data-urlencode "action=query" --data-urlencode "export=1" --data-urlencode "exportnowrap=1" --data-urlencode "titles=$TITLES" -o "export_$(printf %03d $i).xml"
  sleep 1.5
done
rm -f batch_*
echo "FR WIKI EXPORT COMPLETE: $i batches"
