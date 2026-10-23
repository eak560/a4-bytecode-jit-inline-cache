#!/bin/bash
# Export a .docx to PDF with Microsoft Word (macOS). Usage: export_pdf.sh in.docx out.pdf
IN="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUT="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
NAME="$(basename "$1")"
open -g -a "Microsoft Word" "$IN"
for i in $(seq 1 60); do
  n=$(osascript -e "with timeout of 10 seconds" -e "tell application \"Microsoft Word\" to get count of (documents whose name is \"$NAME\")" -e "end timeout" 2>/dev/null)
  [ "$n" = "1" ] && break
  sleep 2
done
osascript <<APPLESCRIPT
with timeout of 300 seconds
tell application "Microsoft Word"
  set d to document "$NAME"
  save as d file name "$OUT" file format format PDF
  close d saving no
end tell
end timeout
APPLESCRIPT
