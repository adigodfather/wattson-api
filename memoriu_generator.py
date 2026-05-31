# -*- coding: utf-8 -*-
"""
Generator memoriu tehnic instalatii electrice (.docx) pentru ZYNAPSE.

Construieste un document Word completat automat din datele cartusului de proiect.
Schelet functional: coperta + fisa proiectului + borderou + schelet memoriu.
Textul fix lung al sectiunilor tehnice este momentan un PLACEHOLDER
("[TEXT_FIX_MEMORIU_AICI]") — va fi inlocuit ulterior.

Returneaza bytes (.docx) — encodarea base64 se face in endpoint.
"""

import io

import requests
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

FONT_NAME = "Arial"

# Latimi tabel info (2 coloane) — total ~16cm, centrat pe pagina
COL_LEFT_W = Cm(5.5)
COL_RIGHT_W = Cm(10.5)
CELL_BG_GREY = "D9D9D9"


# =============================================================================
# HELPERS — font, shading, tabele, paragrafe
# =============================================================================

def _set_run_font(run, size=11, bold=False):
    """Forteaza Arial (ascii/hAnsi/cs) + dimensiune pe un run."""
    run.font.name = FONT_NAME
    run.font.size = Pt(size)
    run.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:ascii"), FONT_NAME)
    rfonts.set(qn("w:hAnsi"), FONT_NAME)
    rfonts.set(qn("w:cs"), FONT_NAME)
    return run


def _set_style_font(style, size=None, bold=None, color=None):
    """Aplica Arial (+ optional size/bold/color) pe un stil de document."""
    style.font.name = FONT_NAME
    if size is not None:
        style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:ascii"), FONT_NAME)
    rfonts.set(qn("w:hAnsi"), FONT_NAME)
    rfonts.set(qn("w:cs"), FONT_NAME)


def set_cell_bg(cell, color_hex):
    """Fundal celula (shading XML w:shd)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    tc_pr.append(shd)


def _set_table_fixed(table):
    """Layout fix (python-docx e capricios la latimi fara asta)."""
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)


def _blank(doc, n=1):
    for _ in range(n):
        doc.add_paragraph()


def _add_centered(doc, text, size=11, bold=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(p.add_run(text), size=size, bold=bold)
    return p


def _add_heading(doc, text, level=1, centered=False):
    """Heading pe stilul nativ (deja setat Arial) — cu override pe run pentru siguranta."""
    style = "Heading 1" if level == 1 else "Heading 2"
    p = doc.add_paragraph(style=style)
    if centered:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    size = 14 if level == 1 else 12
    _set_run_font(p.add_run(text), size=size, bold=True)
    return p


def _add_label_value(doc, label, value="", size=11):
    """Paragraf cu eticheta bold + valoare normala."""
    p = doc.add_paragraph()
    _set_run_font(p.add_run(label), size=size, bold=True)
    if value:
        _set_run_font(p.add_run(value), size=size, bold=False)
    return p


def _add_info_table(doc, rows, bg=CELL_BG_GREY):
    """Tabel 2 coloane centrat: stanga gri+bold (eticheta), dreapta bold (valoare).
    Seteaza atat latimea coloanelor cat si a fiecarei celule (python-docx capricios).
    """
    table = doc.add_table(rows=0, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.allow_autofit = False
    _set_table_fixed(table)

    # latimi pe coloane
    for col, w in zip(table.columns, (COL_LEFT_W, COL_RIGHT_W)):
        col.width = w

    for label, value in rows:
        cells = table.add_row().cells
        c_left, c_right = cells[0], cells[1]
        c_left.width = COL_LEFT_W
        c_right.width = COL_RIGHT_W
        set_cell_bg(c_left, bg)

        p_left = c_left.paragraphs[0]
        _set_run_font(p_left.add_run(label), size=11, bold=True)

        p_right = c_right.paragraphs[0]
        _set_run_font(p_right.add_run(value), size=11, bold=True)

    return table


def _try_add_logo(doc, logo_url):
    """Insereaza logo centrat (~5cm) daca url e nevid si download-ul reuseste.
    Esecul nu propaga eroare (logo optional)."""
    if not logo_url:
        return
    try:
        resp = requests.get(logo_url, timeout=10)
        resp.raise_for_status()
        stream = io.BytesIO(resp.content)
        doc.add_picture(stream, width=Cm(5))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        # logo optional — omite fara eroare
        pass


# =============================================================================
# SETUP DOCUMENT — font implicit, pagina A4, margini, stiluri heading
# =============================================================================

def _setup_document():
    doc = Document()

    # Font implicit Arial 11 (stilul Normal)
    _set_style_font(doc.styles["Normal"], size=11, bold=False,
                    color=RGBColor(0, 0, 0))

    # Heading 1: Arial 14 bold negru | Heading 2: Arial 12 bold negru
    _set_style_font(doc.styles["Heading 1"], size=14, bold=True,
                    color=RGBColor(0, 0, 0))
    _set_style_font(doc.styles["Heading 2"], size=12, bold=True,
                    color=RGBColor(0, 0, 0))

    # A4 portrait + margini (sus/jos/dreapta 2cm, stanga 2.5cm)
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.right_margin = Cm(2.0)
        section.left_margin = Cm(2.5)

    return doc


# =============================================================================
# PAGINI
# =============================================================================

def _page_coperta(doc, cp, cf):
    # 1. spatiere de sus
    _blank(doc, 4)

    # 2. logo (optional)
    _try_add_logo(doc, cf.get("firma_logo_url", ""))

    # 3-5. identitate firma
    _add_centered(doc, cf.get("firma_nume", ""), size=14, bold=True)
    _add_centered(
        doc,
        "Reg. Com. {}   ·   C.U.I. {}".format(
            cf.get("firma_reg_com", ""), cf.get("firma_cui", "")),
        size=9,
    )
    _add_centered(
        doc,
        "Tel. {}   ·   {}".format(
            cf.get("firma_tel", ""), cf.get("firma_email", "")),
        size=9,
    )

    # 6. spatiu mare
    _blank(doc, 6)

    # 7. titlu memoriu
    _add_centered(doc, "MEMORIU TEHNIC INSTALAȚII ELECTRICE",
                  size=16, bold=True)

    # 8. spatiu
    _blank(doc, 3)

    # 9. tabel date proiect
    _add_info_table(doc, [
        ("BENEFICIAR:", cp.get("beneficiar", "")),
        ("LUCRARE:", cp.get("titlu_proiect", "")),
        ("ADRESA:", cp.get("amplasament", "")),
        ("PROIECT:", "Nr. {}".format(cp.get("numar_proiect", ""))),
        ("FAZA:", cp.get("faza", "")),
    ])

    # 10. page break
    doc.add_page_break()


def _page_fisa(doc, cp, cf):
    # impins spre mijloc-sus
    _blank(doc, 4)
    _add_heading(doc, "I. FIȘA PROIECTULUI", level=1, centered=True)
    _blank(doc, 1)

    proiectant_val = (
        "{firma_nume}  Nr. Reg. ONRC: {reg}  CUI: {cui}  Tel.: {tel}  "
        "e-mail: {email}  {atestat}".format(
            firma_nume=cf.get("firma_nume", ""),
            reg=cf.get("firma_reg_com", ""),
            cui=cf.get("firma_cui", ""),
            tel=cf.get("firma_tel", ""),
            email=cf.get("firma_email", ""),
            atestat=cf.get("firma_atestat", ""),
        )
    )

    _add_info_table(doc, [
        ("FAZA DE PROIECTARE:", cp.get("faza", "")),
        ("LUCRARE:", cp.get("titlu_proiect", "")),
        ("AMPLASAMENT:", cp.get("amplasament", "")),
        ("BENEFICIAR:", cp.get("beneficiar", "")),
        ("VOLUM/OBIECT:", "INSTALAȚII ELECTRICE"),
        ("PROIECTANT DE SPECIALITATE:", proiectant_val),
    ])

    doc.add_page_break()


def _page_borderou(doc, planse):
    _add_heading(doc, "II. BORDEROU", level=1, centered=False)

    _set_run_font(doc.add_paragraph().add_run("PIESE SCRISE:"),
                  size=11, bold=True)
    for line in [
        "I. FIȘA PROIECTULUI",
        "II. BORDEROU",
        "III. MEMORIU TEHNIC INSTALAȚII ELECTRICE",
        "    2.1. Alimentarea cu energie electrică",
        "    2.5. Distribuția energiei electrice",
        "    2.6. Instalația de prize și forță",
        "IV. CERINȚE DE CALITATE ȘI CRITERII DE PERFORMANȚĂ",
    ]:
        _set_run_font(doc.add_paragraph().add_run(line), size=11, bold=False)

    _blank(doc, 1)
    _set_run_font(doc.add_paragraph().add_run("PIESE DESENATE:"),
                  size=11, bold=True)
    for pl in (planse or []):
        nr = pl.get("nr", "")
        titlu = pl.get("titlu", "")
        p = doc.add_paragraph()
        _set_run_font(p.add_run("{}  ".format(nr)), size=11, bold=True)
        _set_run_font(p.add_run(titlu), size=11, bold=False)

    doc.add_page_break()


def _page_memoriu(doc, cp):
    _add_heading(doc, "III. MEMORIU TEHNIC INSTALAȚII ELECTRICE", level=1)
    _add_heading(doc, "1. DATE GENERALE", level=2)

    _add_label_value(doc, "1.1. Denumirea lucrării: ",
                     cp.get("titlu_proiect", ""))
    _add_label_value(doc, "1.2. Adresa: ", cp.get("amplasament", ""))
    _add_label_value(
        doc,
        "1.3. Obiect: ",
        "Prezentul memoriu tehnic descrie soluțiile tehnice adoptate pentru "
        "realizarea instalațiilor electrice aferente obiectivului menționat "
        "mai sus.",
    )

    # TODO: text fix memoriu — se inlocuieste [TEXT_FIX_MEMORIU_AICI]
    # cu textul complet al sectiunilor tehnice (mesajul urmator).
    _set_run_font(doc.add_paragraph().add_run("[TEXT_FIX_MEMORIU_AICI]"),
                  size=11, bold=False)


# =============================================================================
# ENTRYPOINT
# =============================================================================

def build_memoriu_docx(data: dict) -> bytes:
    """Construieste memoriul .docx din datele cartusului si returneaza bytes."""
    data = data or {}
    cp = data.get("cartus_proiect") or {}
    cf = data.get("cartus_firma") or {}
    planse = data.get("planse") or []

    doc = _setup_document()
    _page_coperta(doc, cp, cf)
    _page_fisa(doc, cp, cf)
    _page_borderou(doc, planse)
    _page_memoriu(doc, cp)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
