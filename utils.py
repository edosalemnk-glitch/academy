"""Rendu simple du contenu des leçons (mini-markdown sécurisé)."""
import html
import re

from markupsafe import Markup


def _inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def render_content(text):
    """Convertit le texte d'une leçon en HTML.

    Syntaxe : '## Titre', '- liste', '> remarque', ``` bloc de code ```,
    **gras**, `code`. Tout le reste est échappé (pas de HTML brut).
    """
    if not text:
        return Markup("")
    out, para, items, code = [], [], [], None

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    def flush_items():
        if items:
            out.append("<ul>" + "".join("<li>" + _inline(i) + "</li>" for i in items) + "</ul>")
            items.clear()

    for raw in text.replace("\r\n", "\n").split("\n"):
        if code is not None:
            if raw.strip().startswith("```"):
                out.append("<pre><code>" + html.escape("\n".join(code), quote=False) + "</code></pre>")
                code = None
            else:
                code.append(raw)
            continue
        line = raw.rstrip()
        if line.strip().startswith("```"):
            flush_para(); flush_items()
            code = []
        elif not line.strip():
            flush_para(); flush_items()
        elif line.startswith("## "):
            flush_para(); flush_items()
            out.append("<h3>" + _inline(line[3:]) + "</h3>")
        elif line.startswith("> "):
            flush_para(); flush_items()
            out.append('<div class="callout">' + _inline(line[2:]) + "</div>")
        elif line.startswith("- "):
            flush_para()
            items.append(line[2:])
        else:
            flush_items()
            para.append(line.strip())
    if code is not None:
        out.append("<pre><code>" + html.escape("\n".join(code), quote=False) + "</code></pre>")
    flush_para(); flush_items()
    return Markup("".join(out))
