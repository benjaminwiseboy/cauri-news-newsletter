"""Ré-applique le CSS canonique (newsletter-template.html) à un numéro DÉJÀ généré
et republie le brouillon formaté — SANS rappeler le LLM (donc gratuit).

Pratique pour itérer sur le style sans regénérer le contenu.
Usage : python restyle.py YYYY-MM-DD [--no-publish]
"""
import sys

import config
from agents import publish
from agents.write import _enforce_style, _fix_body, derive_meta, french_date

day = sys.argv[1] if len(sys.argv) > 1 else None
if not day:
    print("Usage : python restyle.py YYYY-MM-DD [--no-publish]")
    sys.exit(1)

html_path = config.OUT_DIR / day / f"newsletter-brvm-{day}.html"
html = html_path.read_text(encoding="utf-8")
template = config.TEMPLATE_PATH.read_text(encoding="utf-8")

restyled = _fix_body(_enforce_style(html, template), french_date(day))
html_path.write_text(restyled, encoding="utf-8")
print(f"[restyle] CSS ré-appliqué à {html_path.name}")

if "--no-publish" not in sys.argv:
    subject, preview = derive_meta(restyled)  # dérivé du HTML (pas de LLM)
    url = publish.publish_post(
        f"Cauri News — {french_date(day)}", f"cauri-news-{day}",
        restyled, config.PUBLISH_STATUS, is_full_document=True,
        email_subject=subject, custom_excerpt=preview,
    )
    print(f"[restyle] republié : {url} | sujet={subject!r} preview={preview!r}")
