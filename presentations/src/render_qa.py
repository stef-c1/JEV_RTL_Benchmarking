"""Render the deck for review: PDF next to the PPTX, one PNG per slide, and contact sheets.

Run: /users/micas/scuycken/no_backup/miniconda3/envs/mx_env/bin/python presentations/src/render_qa.py
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image

DEST = Path(__file__).resolve().parents[1]
PPTX = DEST / 'KEV_RTL_findings_20261015.pptx'
PDF = PPTX.with_suffix('.pdf')
QA = DEST / 'qa'
SLIDES = QA / 'slides'
PROFILE = Path('/tmp/claude-40729/soffice_profile_qa')


def main():
    PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.run(['soffice', f'-env:UserInstallation=file://{PROFILE}', '--headless', '--convert-to', 'pdf',
                    '--outdir', str(DEST), str(PPTX)], check=True, capture_output=True)
    assert PDF.exists()
    SLIDES.mkdir(parents=True, exist_ok=True)
    for old in list(SLIDES.glob('slide-*.png')) + list(QA.glob('contact_*.png')):
        old.unlink()
    subprocess.run(['pdftoppm', '-r', '110', '-png', str(PDF), str(SLIDES / 'slide')], check=True)
    pages = sorted(SLIDES.glob('slide-*.png'))
    for i, p in enumerate(pages, 1):
        p.rename(SLIDES / f'slide-{i:02d}.png')
    pages = sorted(SLIDES.glob('slide-*.png'))
    per_sheet, cols = 8, 2
    w, h = Image.open(pages[0]).size
    scale = 900 / w
    tw, th = int(w * scale), int(h * scale)
    gap = 24
    for sheet, start in enumerate(range(0, len(pages), per_sheet), 1):
        chunk = pages[start:start + per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        img = Image.new('RGB', (cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap), 'white')
        for k, p in enumerate(chunk):
            thumb = Image.open(p).convert('RGB').resize((tw, th), Image.LANCZOS)
            img.paste(thumb, (gap + (k % cols) * (tw + gap), gap + (k // cols) * (th + gap)))
        img.save(QA / f'contact_{sheet}.png')
    print(f'{len(pages)} pages rendered: {PDF.name}, {SLIDES}, {sheet} contact sheets')


if __name__ == '__main__':
    sys.exit(main())
