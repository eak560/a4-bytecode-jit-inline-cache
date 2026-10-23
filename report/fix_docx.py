"""Post-process the docx-js output: add the fontTable relationship docx-js omits."""
import shutil
import sys
import zipfile

src = sys.argv[1]
tmp = src + ".tmp"
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "word/_rels/document.xml.rels" and b"fontTable" not in data:
            data = data.replace(b"</Relationships>", b'<Relationship Id="rIdFontTable1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/></Relationships>')
        zout.writestr(item, data)
shutil.move(tmp, src)
