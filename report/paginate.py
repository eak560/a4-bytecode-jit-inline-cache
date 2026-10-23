"""Find the printed page of every heading in the exported PDF -> data/toc_pages.json.

A heading matches a PDF line only exactly; the contents page's own entries carry
dot leaders and page numbers, so they never match. Headings are searched in
document order. Printed page = 0-based PDF page index (the cover is unnumbered).

  python3 paginate.py A4_Final_Report.pdf
"""
import json
import subprocess
import sys

pdf = sys.argv[1]
headings = json.load(open("data/headings.json"))
info = subprocess.check_output(["pdfinfo", pdf], text=True)
n = int(next(l.split()[1] for l in info.splitlines() if l.startswith("Pages:")))
pages = [{l.strip() for l in subprocess.check_output(
    ["pdftotext", "-f", str(i + 1), "-l", str(i + 1), "-layout", pdf, "-"], text=True).splitlines()}
    for i in range(n)]

result, p = {}, 0
for _, text in headings:
    while p < n and text not in pages[p]:
        p += 1
    if p == n:
        sys.exit(f"heading not found in PDF: {text}")
    result[text] = p
json.dump(result, open("data/toc_pages.json", "w"), indent=1)
print(f"{len(result)} headings paginated, last on page {p}")
