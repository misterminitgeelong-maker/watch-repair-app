"""Package captured native screens into a local, searchable review gallery."""
from pathlib import Path
import argparse
import html
import json
import re
import shutil
import textwrap
import zipfile
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--revision", default="original", help="Review revision, e.g. v2; original preserves existing review notes")
parser.add_argument("--original-manifest", type=Path, help="Original gallery manifest used to retain image-number references by stable screen ID")
args = parser.parse_args()
revision = args.revision.strip()
if not revision:
    parser.error("--revision must not be blank")
original_images = {}
if args.original_manifest:
    original_records = json.loads(args.original_manifest.read_text(encoding="utf-8-sig"))
    original_images = {row["id"]: row.get("number", row.get("image", index)) for index, row in enumerate(original_records, 1)}
records = json.loads((args.source / "manifest.json").read_text(encoding="utf-8"))
patch = args.source / "manifest-patch.json"
if patch.exists():
    updates = {row["id"]: row for row in json.loads(patch.read_text(encoding="utf-8"))}
    records = [updates.pop(row["id"], row) for row in records] + list(updates.values())
bad = [row for row in records if row["status"] != "captured"]
if bad:
    raise SystemExit("Unresolved captures: " + ", ".join(row["id"] for row in bad))
section_order = list(dict.fromkeys(row["group"] for row in records))
records.sort(key=lambda row: section_order.index(row["group"]))
args.output.mkdir(parents=True, exist_ok=True)
screens = args.output / "screens"
screens.mkdir(exist_ok=True)
for index, row in enumerate(records, 1):
    row["number"] = index
    row["image"] = index
    row["revision"] = revision
    row["originalImage"] = original_images.get(row["id"], index if revision == "original" else None)
    row.setdefault("feedback", "")
    origin = args.source / row["file"]
    with Image.open(origin) as image:
        assert image.width >= 900 and image.height >= 1800, origin
    shutil.copy2(origin, screens / row["file"])
groups = list(dict.fromkeys(row["group"] for row in records))
data = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
storage_key = "mainspring-screen-review" if revision == "original" else f"mainspring-screen-review:{revision}"
revision_filename = re.sub(r"[^a-zA-Z0-9._-]+", "-", revision).strip("-.") or "revision"
notes_filename = "mainspring-screen-review-notes.json" if revision == "original" else f"mainspring-screen-review-{revision_filename}-notes.json"
page = r'''<!doctype html><html lang="en-AU"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mainspring Android screen review</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f4f6;color:#19212a;font:15px/1.5 system-ui,sans-serif}header{background:#fff;border-bottom:1px solid #ddd;padding:30px max(24px,calc((100vw - 1480px)/2))}h1{font-family:Georgia,serif;font-size:36px;line-height:1.15;margin:12px 0}p{max-width:850px;color:#52606d}.badge{font-size:12px;font-weight:700;letter-spacing:.08em;color:#b62b17;text-transform:uppercase}.toolbar{position:sticky;top:0;z-index:2;background:#fffefb;padding:16px 24px;box-shadow:0 2px 8px #0001}.toolbar-inner{max-width:1480px;margin:auto}input{font:inherit;padding:11px 14px;border:1px solid #c8ccd2;border-radius:8px;width:min(450px,100%)}.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}button{font:inherit;cursor:pointer}button.chip{border:1px solid #d4d8dd;background:white;border-radius:30px;padding:6px 13px}.chip[aria-pressed=true]{background:#b92c17;color:white;border-color:#b92c17}.meta{font-size:13px;color:#58636e;margin:10px 0 0}.grid{max-width:1528px;margin:auto;padding:24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(235px,1fr));gap:24px}.card{border-radius:12px;background:#fff;border:1px solid #d8dce0;overflow:hidden;box-shadow:0 3px 9px #00000008}.image-button{display:block;width:100%;border:0;padding:0;background:#e9eaed}.image-button img{display:block;width:100%;height:auto;aspect-ratio:9/20;object-fit:contain}.caption{padding:14px}.caption small{color:#b32a16;font-weight:700}.caption h2{font-size:16px;line-height:1.35;margin:6px 0}.caption p{font-size:12px;margin:6px 0}.feedback{width:100%;min-height:55px;margin-top:9px;padding:8px;border:1px solid #ddd;border-radius:6px;resize:vertical;font:13px system-ui}.review-actions{margin-top:12px;display:flex;gap:10px;flex-wrap:wrap}.review-actions button{background:#fff;border:1px solid #c8ccd2;padding:7px 12px;border-radius:6px}dialog{padding:0;border:0;background:#f9fafb;max-width:96vw;max-height:96vh;border-radius:10px;box-shadow:0 12px 80px #0007}dialog::backdrop{background:#101820dc}.lightbox-head{position:sticky;top:0;background:white;padding:12px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #ddd;z-index:1}.lightbox-head span{flex:1;font-weight:600}.lightbox-head button{padding:6px 10px;background:#fff;border:1px solid #ccc;border-radius:6px}.full-image{display:block;max-width:94vw;width:auto;max-height:none;height:auto;margin:auto}footer{padding:24px;text-align:center;color:#65717d;font-size:13px}@media(min-width:900px){dialog{width:min(650px,94vw)}.full-image{width:100%}}@media print{.toolbar,textarea,.review-actions{display:none}.grid{grid-template-columns:repeat(3,1fr);gap:10px}.card{break-inside:avoid;box-shadow:none}.caption h2{font-size:12px}header{padding:15px}h1{font-size:25px}}
</style><header><div class="badge">Android 1.1.0 · review before Google Play</div><h1>Mainspring, screen by screen</h1><p>Actual native Android screens captured in the phone simulator with synthetic shop records, using the default Mainspring appearance. Select a section or search, then click any screenshot to inspect it at full size. Use its image number when giving feedback.</p><p id="revision-note" hidden></p><p id="summary"></p><div class="review-actions"><button id="export">Export my review notes</button><button onclick="window.print()">Print gallery</button></div></header>
<div class="toolbar"><div class="toolbar-inner"><input id="search" type="search" placeholder="Find a screen, tab or form…" aria-label="Find screenshots"><div class="chips" id="groups"></div><div class="meta" id="count"></div></div></div><main class="grid" id="grid"></main><footer>Sample data only. No Google Play submission has been made. Messages, payments and destructive confirmations were not submitted for this review.</footer>
<dialog id="lightbox"><div class="lightbox-head"><button id="previous" aria-label="Previous screenshot">←</button><span id="image-title"></span><button id="next" aria-label="Next screenshot">→</button><button id="close">Close</button></div><img class="full-image" id="full-image" alt=""></dialog>
<script>const records=__DATA__;const revision=__REVISION__;const storageKey=__STORAGE_KEY__;const groups=[...new Set(records.map(r=>r.group))];let group='',filtered=records,active=0;let notes={};try{notes=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(e){}const $=id=>document.getElementById(id);$('summary').textContent=records.length+' labelled views across '+groups.length+' sections. Includes main screens, major tabs, forms and selected lower-page views.';
function imageLabel(row){return 'Image '+String(row.number).padStart(3,'0')+(revision!=='original'?' · '+(row.originalImage!=null?'original image '+row.originalImage:'new view'):'')}
if(revision!=='original'){$('revision-note').hidden=false;$('revision-note').textContent='Revision '+revision+': focused revised views. Original image references refer to the first gallery; new views have no original number. Your notes for this revision are saved separately.';document.title+=' · '+revision;document.querySelector('h1').textContent='Mainspring · '+revision+' review';$('summary').textContent=records.length+' revised views across '+groups.length+' sections. This gallery is a focused review, not the complete original screen set.'}
function renderGroups(){const host=$('groups');host.replaceChildren();['',...groups].forEach(name=>{const button=document.createElement('button');button.className='chip';button.textContent=name||'All screens';button.setAttribute('aria-pressed',String(group===name));button.onclick=()=>{group=name;renderGroups();render()};host.append(button)})}
function render(){const query=$('search').value.trim().toLowerCase();filtered=records.filter(r=>(!group||r.group===group)&&(!query||(r.title+' '+r.group+' '+r.id+' '+r.number+' '+(r.originalImage??'')).toLowerCase().includes(query)));$('count').textContent=filtered.length+' of '+records.length+' views';const host=$('grid');host.replaceChildren();filtered.forEach((row,index)=>{const card=document.createElement('article');card.className='card';const button=document.createElement('button');button.className='image-button';button.setAttribute('aria-label','Open '+imageLabel(row)+': '+row.title);const image=document.createElement('img');image.loading='lazy';image.src='screens/'+encodeURIComponent(row.file);image.alt=row.title;image.width=1080;image.height=2400;button.append(image);button.onclick=()=>open(index);const body=document.createElement('div');body.className='caption';const number=document.createElement('small');number.textContent=imageLabel(row)+' · '+row.group;const title=document.createElement('h2');title.textContent=row.title;const note=document.createElement('p');note.textContent=row.note;const feedback=document.createElement('textarea');feedback.className='feedback';feedback.placeholder='Your feedback on this view…';feedback.setAttribute('aria-label','Notes for '+imageLabel(row));feedback.value=notes[row.id]||'';feedback.oninput=()=>{notes[row.id]=feedback.value;try{localStorage.setItem(storageKey,JSON.stringify(notes))}catch(e){}};body.append(number,title,note,feedback);card.append(button,body);host.append(card)})}
function open(index){active=(index+filtered.length)%filtered.length;const row=filtered[active];$('image-title').textContent=imageLabel(row)+' · '+row.title;$('full-image').src='screens/'+encodeURIComponent(row.file);$('full-image').alt=row.title;if(!$('lightbox').open)$('lightbox').showModal();$('lightbox').scrollTop=0}
$('search').oninput=render;$('previous').onclick=()=>open(active-1);$('next').onclick=()=>open(active+1);$('close').onclick=()=>$('lightbox').close();document.addEventListener('keydown',event=>{if(!$('lightbox').open)return;if(event.key==='ArrowLeft')open(active-1);if(event.key==='ArrowRight')open(active+1)});$('export').onclick=()=>{const rows=records.filter(r=>notes[r.id]?.trim()).map(r=>({id:r.id,revision:r.revision,originalImage:r.originalImage,image:r.number,title:r.title,feedback:notes[r.id]}));const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(rows,null,2)],{type:'application/json'}));a.download=__NOTES_FILENAME__;a.click();URL.revokeObjectURL(a.href)};renderGroups();render();</script></html>'''
substitutions = {"__DATA__": data}
for token, value in (("__REVISION__", revision), ("__STORAGE_KEY__", storage_key), ("__NOTES_FILENAME__", notes_filename)):
    substitutions[token] = json.dumps(value, ensure_ascii=False).replace("</", "<\\/")
page = re.sub("|".join(substitutions), lambda match: substitutions[match.group()], page)
(args.output / "index.html").write_text(page, encoding="utf-8")
(args.output / "manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
def image_reference(row):
    label = f"{row['number']:03}"
    if revision != "original":
        label += f" (original image {row['originalImage']})" if row["originalImage"] is not None else " (new view)"
    return label

readme = ["# Mainspring Android screenshot review", "", "Google Play is held pending Sam's review.", "", f"{len(records)} actual native views, captured with synthetic localhost data. Open index.html for the searchable gallery; click a screenshot to view full size.", "", "Images cover distinct native screens, major tabs and forms. Android system pickers, live payment/provider websites and repeated confirmation permutations are outside this gallery."]
if revision != "original":
    readme += ["", f"Revision: {revision}. This focused gallery contains revised views, not the full original screen set. Original image numbers are matched by stable screen ID; unmatched screens are marked as new views. Browser notes are stored separately for this revision. Exports retain the screen ID, revision and original image reference."]
readme += ["", "| Image | Section | Screen |", "|---|---|---|"]
readme += [f"| {image_reference(r)} | {r['group']} | [{r['title']}](screens/{r['file']}) |" for r in records]
(args.output / "README.md").write_text("\n".join(readme), encoding="utf-8")
font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
selected = []
for group in groups:
    group_records = [row for row in records if row["group"] == group]
    selected.append(next((row for row in group_records if row["id"] == "shared-home"), group_records[0]) if group == "Home and business" else group_records[0])
selected += [row for wanted in ("mobile-route", "watch-detail") for row in records if row["id"] == wanted]
selected = selected[:12]
columns, cell_w, thumb_h = 4, 290, 575
rows = (len(selected) + columns - 1) // columns
sheet = Image.new("RGB", (columns * cell_w + 40, rows * (thumb_h + 80) + 105), "#f3f4f6")
draw = ImageDraw.Draw(sheet)
draw.text((22, 18), "Mainspring Android — review overview" + (f" · {revision}" if revision != "original" else ""), font=font, fill="#18212b")
draw.text((22, 53), f"{len(records)} full-size views in index.html · sample data · Play on hold", font=small, fill="#52606d")
for index, row in enumerate(selected):
    x, y = 20 + (index % columns) * cell_w, 100 + (index // columns) * (thumb_h + 80)
    with Image.open(screens / row["file"]) as image:
        image.thumbnail((cell_w - 18, thumb_h))
        sheet.paste(image, (x + (cell_w - 18 - image.width) // 2, y))
    title = f"{image_reference(row)} · {row['title']}"
    for line, text in enumerate(textwrap.wrap(title, width=32)[:3]):
        draw.text((x, y + thumb_h + 7 + line * 20), text, font=small, fill="#18212b")
sheet.save(args.output / "overview.jpg", quality=92)
pdf_file = args.output / "Mainspring-Android-screen-review.pdf"
pdf = canvas.Canvas(str(pdf_file), pagesize=A4, pageCompression=1)
pdf.setTitle("Mainspring Android - screen review before Google Play" + (f" - {revision}" if revision != "original" else ""))
pdf.setAuthor("Mainspring")
seen_groups = set()
def plain(value):
    return value.replace("·", " | ").replace("—", "-").replace("–", "-")
for row in records:
    width, height = A4
    pdf.setFillColorRGB(0.70, 0.15, 0.07)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(26, height - 25, "MAINSPRING ANDROID 1.1.0  |  REVIEW BEFORE GOOGLE PLAY")
    pdf.setFillColorRGB(0.10, 0.14, 0.18)
    pdf.setFont("Helvetica-Bold", 12)
    title_lines = textwrap.wrap(f"{image_reference(row)} - {plain(row['title'])}", width=76)
    for line, title in enumerate(title_lines[:2]):
        pdf.drawString(26, height - 44 - line * 15, title)
    with Image.open(screens / row["file"]) as image:
        maximum_height = height - 108
        scale = min((width - 52) / image.width, maximum_height / image.height)
        image_w, image_h = image.width * scale, image.height * scale
        pdf.drawImage(ImageReader(image), (width - image_w) / 2, 36, image_w, image_h)
    pdf.setFont("Helvetica", 8)
    pdf.setFillColorRGB(0.35, 0.40, 0.45)
    pdf.drawString(26, 16, "KNOWN ISSUE: Map area is blank in this simulator capture. Resolve before Play." if row.get("issue") else "Synthetic sample data. Google Play submission is held for review.")
    pdf.drawRightString(width - 26, 16, f"{row['number']} / {len(records)}")
    if row["group"] not in seen_groups:
        key = "group-" + str(len(seen_groups))
        pdf.bookmarkPage(key)
        pdf.addOutlineEntry(plain(row["group"]), key, level=0, closed=False)
        seen_groups.add(row["group"])
    key = row["id"]
    pdf.bookmarkPage(key)
    pdf.addOutlineEntry(f"{image_reference(row)} {plain(row['title'])}", key, level=1, closed=True)
    pdf.showPage()
pdf.save()
archive = args.output.parent / (args.output.name + ".zip")
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipout:
    for path in args.output.rglob("*"):
        if path.is_file() and path.suffix != ".pdf": zipout.write(path, args.output.name + "/" + path.relative_to(args.output).as_posix())
print(f"Packaged {len(records)} views across {len(groups)} sections: {args.output}")
