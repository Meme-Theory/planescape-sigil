#!/bin/bash
cd "C:/sandbox/Planescape/content/fan/planewalker-public-files/extracted" || exit 1
find . -name '*.zip' | while IFS= read -r z; do
  case "$z" in
    *WizardsEmailListArchives*) case "$z" in *planescape-l*) ;; *) continue ;; esac ;;
  esac
  d="${z%.zip}"
  mkdir -p "$d"
  unzip -o -q "$z" -d "$d" 2>/dev/null || python -m zipfile -e "$z" "$d" 2>/dev/null || echo "FAILED: $z"
done
echo "=== extraction done ==="
du -sh ./*/ 2>/dev/null
echo "total files now: $(find . -type f | wc -l)"
