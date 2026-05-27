"""
PDF generator — layout identyczny z szablonami HTML.
Kolory i struktura zgodne z Brueggen Corporate Brand.
"""
import io
import base64
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, Image, HRFlowable,
)
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Brand colors (z szablonów HTML) ─────────────────────────────────
BRAND  = HexColor('#9b1c2e')   # nagłówki sekcji, tytuł, tekst zobowiązań
DARK   = HexColor('#5a0c1a')   # th w tabelach, wiersz "Podpis …"
BORDER = HexColor('#bbbbbb')   # obramowania tabel
CGRAY  = HexColor('#555555')   # mały tekst nagłówka strony
CFOOT  = HexColor('#444444')   # stopka

# ── Geometria strony ─────────────────────────────────────────────────
PAGE_W, PAGE_H = A4            # 595.3 × 841.9 pt
MARGIN = 14 * mm               # ≈ 39.7 pt  (14 mm ze wszystkich stron)
CW     = PAGE_W - 2 * MARGIN   # ≈ 515.9 pt szerokość kolumny treści

# ── Ścieżka do logo ──────────────────────────────────────────────────
LOGO_PATH = os.path.join(os.path.dirname(__file__), 'static', 'img', 'brueggen_logo.jpg')

# ── Rejestracja fontów ───────────────────────────────────────────────
_FONTS_OK = False

# Bundled Liberation Sans fonts (metrics-compatible with Arial, SIL OFL)
_BUNDLED_FONTS = os.path.join(os.path.dirname(__file__), 'static', 'fonts')

def _reg_fonts():
    global _FONTS_OK
    if _FONTS_OK:
        return
    WIN = r'C:\Windows\Fonts'
    LIN = '/usr/share/fonts/truetype/liberation'
    # (name, windows_file, liberation_file)
    pairs = [
        ('Arial',            'arial.ttf',    'LiberationSans-Regular.ttf'),
        ('Arial-Bold',       'arialbd.ttf',  'LiberationSans-Bold.ttf'),
        ('Arial-Italic',     'ariali.ttf',   'LiberationSans-Italic.ttf'),
        ('Arial-BoldItalic', 'arialbi.ttf',  'LiberationSans-BoldItalic.ttf'),
    ]
    for name, win_f, lib_f in pairs:
        for path in (
            os.path.join(WIN, win_f),
            os.path.join(LIN, lib_f),
            os.path.join(_BUNDLED_FONTS, lib_f),
        ):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                break
            except Exception:
                continue
    # Georgia Bold Italic — only needed for text logo fallback on Windows
    try:
        pdfmetrics.registerFont(TTFont('Georgia-BI', os.path.join(WIN, 'georgiaz.ttf')))
    except Exception:
        pass
    _FONTS_OK = True

# ── Stałe teksty zobowiązań ──────────────────────────────────────────
_OBLIG = [
    "Przyjmujący będzie korzystał z ww wyposażenia wyłącznie w celu realizacji zadań "
    "postawionych przez firmę Brueggen Polska Sp. z o.o.",
    "Przyjmujący jest świadomy, ze firma nie jest w stanie zapewnić poufności danych "
    "w skrzynce mailowej; cala korespondencja powinna mieć charakter służbowy.",
    "Przyjmujący zobowiązuje się dbać o powierzone wyposażenie: zabezpieczyć je przed "
    "kradzieżą, zgubieniem, zalaniem, pożarem, zniszczeniem oraz przed dostępem osób "
    "nieupoważnionych.",
    "Przyjmujący nie będzie dokonywał samodzielnie żadnych zmian w konfiguracji "
    "sprzętu i oprogramowania.",
    "Naprawy sprzętu wykonywane będą wyłącznie w autoryzowanych punktach serwisowych "
    "na podstawie przekazanych dokumentów.",
    "Z chwila zakończenia pracy przyjmujący zwróci cale wyposażenie w dobrym stanie "
    "do Działu IT.",
]

# ═══════════════════════════════════════════════════════════════════════
# Helpery
# ═══════════════════════════════════════════════════════════════════════

def _v(obj, attr, default=''):
    """Odczyt pola z modelu ORM lub słownika."""
    try:
        val = obj[attr]
    except (TypeError, KeyError):
        val = getattr(obj, attr, default)
    return val if val is not None else default


def _date_str(doc):
    d = _v(doc, 'doc_date', '')
    if hasattr(d, 'strftime'):
        return d.strftime('%d.%m.%Y')
    return str(d)


def _S(name='_', **kw):
    """Skrócony konstruktor ParagraphStyle."""
    base = dict(fontName='Arial', fontSize=9, leading=12,
                textColor=black, spaceAfter=0, spaceBefore=0)
    base.update(kw)
    return ParagraphStyle(name, **base)


def _sig_img(data_url, w, h):
    """Konwersja base64 data-URL → ReportLab Image (lub Spacer gdy brak)."""
    if not data_url:
        return Spacer(w, h)
    try:
        raw = base64.b64decode(data_url.split(',', 1)[-1])
        return Image(io.BytesIO(raw), width=w, height=h)
    except Exception:
        return Spacer(w, h)


# ── Styl nagłówka kolumny tabeli (ciemny) ────────────────────────────
_ST_TH = _S('th', fontName='Arial-Bold', fontSize=9, textColor=white, leading=11)

def _th(text):
    return Paragraph(text, _ST_TH)

def _td(text):
    return Paragraph(str(text), _S('td', fontSize=9, leading=11))


def _table_style_base():
    return [
        ('BACKGROUND',    (0, 0), (-1,  0), DARK),
        ('TEXTCOLOR',     (0, 0), (-1,  0), white),
        ('FONTNAME',      (0, 0), (-1,  0), 'Arial-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('GRID',          (0, 0), (-1, -1), 0.5, BORDER),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1,  0), 5),
        ('BOTTOMPADDING', (0, 0), (-1,  0), 5),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]


# ── Nagłówek sekcji (czerwone tło, biały tekst) ──────────────────────
def _sec_hdr(text):
    t = Table(
        [[Paragraph(text, _S('sh', fontName='Arial-Bold', fontSize=9.5, textColor=white))]],
        colWidths=[CW],
    )
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), BRAND),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 7),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 7),
        ('BOX',           (0, 0), (-1, -1), 0.5, BRAND),
    ]))
    return t


# ── Pole "Typ operacji" ───────────────────────────────────────────────
def _op_box(text):
    t = Table(
        [[Paragraph(text, _S('op', fontSize=9.5))]],
        colWidths=[CW],
    )
    t.setStyle(TableStyle([
        ('BOX',           (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 7),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 7),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════
# Blok nagłówka + tytułu (wspólny dla wszystkich typów)
# ═══════════════════════════════════════════════════════════════════════

def _header_block(title, date_str, operation):
    """Zwraca listę flowables: linia firmy, logo | tytuł H1 | wiersz intro."""
    elems = []

    # Logo: obraz JPEG lub tekst zastępczy
    LOGO_H = 33  # 44px (HTML) → 33pt (96 DPI)
    logo_cell = None
    if os.path.exists(LOGO_PATH):
        try:
            iw, ih = ImageReader(LOGO_PATH).getSize()
            logo_cell = Image(LOGO_PATH, width=iw * LOGO_H / ih, height=LOGO_H)
        except Exception:
            pass
    if logo_cell is None:
        lf = 'Georgia-BI' if _FONTS_OK else 'Arial-BoldItalic'
        logo_cell = Paragraph(
            f"<font name='{lf}' size='22' color='#9b1c2e'>Brüggen</font>",
            _S('hdr_r', alignment=TA_RIGHT),
        )

    # Wiersz: firma (lewo) | logo Brüggen (prawo)
    hdr = Table(
        [[
            Paragraph("Brueggen Polska Sp. z o.o. | Celejów 59, 08-470 Wilga",
                       _S('hdr_l', fontSize=7.5, textColor=CGRAY)),
            logo_cell,
        ]],
        colWidths=[CW * 0.65, CW * 0.35],
    )
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('ALIGN',         (1, 0), (1,  0),  'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elems.append(hdr)

    # H1 z podkreśleniem
    elems.append(Paragraph(
        title,
        _S('h1', fontName='Arial-Bold', fontSize=17, leading=21,
           textColor=BRAND, spaceBefore=2),
    ))
    elems.append(HRFlowable(width=CW, thickness=2, color=BRAND, spaceAfter=8))

    # Wiersz intro: lewo tekst, prawo "Wilga, dnia …"
    op_pl  = "przekazał"     if operation == 'wydanie' else "przyjął"
    op2_pl = "do użytkowania" if operation == 'wydanie' else "do zwrotu"
    intro = Table(
        [[
            Paragraph(
                f"W dniu {date_str}&nbsp; Dział IT Brueggen Polska Sp. z o.o. {op_pl}<br/>"
                f"{op2_pl} następujące wyposażenie.",
                _S('il', fontName='Arial-Italic', fontSize=9, leading=13),
            ),
            Paragraph(
                f"Wilga, dnia {date_str}",
                _S('ir', fontName='Arial-Italic', fontSize=9, leading=13,
                   alignment=TA_RIGHT),
            ),
        ]],
        colWidths=[CW * 0.70, CW * 0.30],
    )
    intro.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elems.append(intro)
    return elems


# ═══════════════════════════════════════════════════════════════════════
# Tabela sprzętu (Office / Produkcja)
# ═══════════════════════════════════════════════════════════════════════

def _equipment_table(items):
    col_w = [CW * 0.22, CW * 0.26, CW * 0.26, CW * 0.13, CW * 0.13]
    rows = [[
        _th("Sprzęt"),
        _th("Producent / Model"),
        _th("Nr seryjny"),
        _th("Ilość"),
        _th("Nr\nwewnętrzny"),
    ]]
    for item in (items or []):
        qty = _v(item, 'quantity', '')
        rows.append([
            _td(_v(item, 'equipment_type')),
            _td(_v(item, 'manufacturer_model')),
            _td(_v(item, 'serial_number')),
            _td(str(qty) if qty else ''),
            _td(_v(item, 'internal_number')),
        ])
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(_table_style_base()))
    return t


# ═══════════════════════════════════════════════════════════════════════
# Tabela telefonu
# ═══════════════════════════════════════════════════════════════════════

def _phone_table(items):
    ph = items[0] if items else {}
    col_w = [CW * 0.45, CW * 0.55]

    rows = [[_th("Pole"), _th("Wartość")]]

    # Only render rows that have a value
    for label, field in [
        ('Rodzaj telefonu',  'phone_type'),
        ('Nr IMEI (1)',      'imei'),
        ('Nr seryjny',       'serial_number'),
        ('Nazwa wewnętrzna', 'internal_name'),
        ('Nr telefonu',      'phone_number'),
        ('Nr karty SIM',     'sim_number'),
        ('Nr PIN telefonu',  'pin_phone'),
        ('Nr PIN karty SIM', 'pin_sim'),
    ]:
        val = _v(ph, field)
        if val:
            rows.append([_td(label), _td(val)])

    # Accessories row spans both columns; use ASCII brackets (font-safe)
    def acc_label(field, name):
        return ('[X] ' if _v(ph, field) else '[ ] ') + name

    acc_idx = len(rows)
    rows.append([
        Paragraph(
            '   '.join([
                acc_label('acc_foil',       'Folia/Szybka'),
                acc_label('acc_case',       'Etui'),
                acc_label('acc_charger',    'Ladowarka'),
                acc_label('acc_headphones', 'Sluchawki'),
            ]),
            _S('acc', fontSize=9, leading=11),
        ),
        Paragraph('', _S()),
    ])

    notes = _v(ph, 'notes')
    if notes:
        rows.append([_td('Pozostale / uwagi'), _td(notes)])

    style = _table_style_base() + [
        ('SPAN', (0, acc_idx), (1, acc_idx)),
    ]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle(style))
    return t


# ═══════════════════════════════════════════════════════════════════════
# Sekcja zobowiązań
# ═══════════════════════════════════════════════════════════════════════

def _obligations_block():
    elems = [Paragraph(
        "Zobowiązania przyjmującego:",
        _S('ot', fontName='Arial-Bold', fontSize=9.5, textColor=BRAND,
           spaceBefore=14, spaceAfter=4),
    )]
    for i, txt in enumerate(_OBLIG, 1):
        elems.append(Paragraph(
            f"{i}.  {txt}",
            _S(f'li{i}', fontSize=8.5, leading=11, leftIndent=14, spaceAfter=2),
        ))
    return elems


# ═══════════════════════════════════════════════════════════════════════
# Tabela "Dane osób" + podpisy — Office (4 kolumny)
# ═══════════════════════════════════════════════════════════════════════

def _people_table_office(doc):
    col_w = [CW * 0.25] * 4
    sig_w = CW * 0.24
    sig_h = 38

    st_sig_lbl = _S('sl', fontName='Arial-Bold', fontSize=9, textColor=white)

    rows = [
        # Nagłówek
        [_th("Przekazujący"), _th("Przyjmujący"),
         _th("Data wydania / zwrotu"), _th("Nazwa sieciowa")],
        # Dane
        [_td(_v(doc, 'issuer_name')), _td(_v(doc, 'receiver_name')),
         _td(_date_str(doc)),          _td(_v(doc, 'network_name'))],
        # Etykiety podpisów
        [Paragraph("Podpis przekazującego", st_sig_lbl),
         Paragraph("Podpis przyjmującego",  st_sig_lbl),
         Paragraph("", st_sig_lbl),
         Paragraph("", st_sig_lbl)],
        # Obrazy podpisów
        [_sig_img(_v(doc, 'sig_issuer'),   sig_w, sig_h),
         _sig_img(_v(doc, 'sig_receiver'), sig_w, sig_h),
         Paragraph("", _S()), Paragraph("", _S())],
    ]

    style = _table_style_base() + [
        ('BACKGROUND', (0, 2), (-1, 2), DARK),
        ('SPAN',       (2, 2), (3, 2)),   # colspan ostatnich 2 w wierszu etykiet
        ('SPAN',       (2, 3), (3, 3)),   # colspan ostatnich 2 w wierszu podpisów
        ('ALIGN',      (0, 3), (-1, 3), 'CENTER'),
        ('VALIGN',     (0, 3), (-1, 3), 'MIDDLE'),
    ]
    # Wymuszamy minimalną wysokość wiersza danych i podpisów
    t = Table(rows, colWidths=col_w, rowHeights=[None, 22, None, sig_h + 8])
    t.setStyle(TableStyle(style))
    return t


# ═══════════════════════════════════════════════════════════════════════
# Tabela "Dane osób" + podpisy — Produkcja / Telefon (3 kolumny)
# ═══════════════════════════════════════════════════════════════════════

def _people_table_3col(doc):
    col_w = [CW * 0.33, CW * 0.33, CW * 0.34]
    sig_w = CW * 0.32
    sig_h = 38

    st_sig_lbl = _S('sl3', fontName='Arial-Bold', fontSize=9, textColor=white)

    rows = [
        [_th("Przekazujący"), _th("Przyjmujący"), _th("Data wydania / zwrotu")],
        [_td(_v(doc, 'issuer_name')), _td(_v(doc, 'receiver_name')), _td(_date_str(doc))],
        [Paragraph("Podpis przekazującego", st_sig_lbl),
         Paragraph("Podpis przyjmującego",  st_sig_lbl),
         Paragraph("", st_sig_lbl)],
        [_sig_img(_v(doc, 'sig_issuer'),   sig_w, sig_h),
         _sig_img(_v(doc, 'sig_receiver'), sig_w, sig_h),
         Paragraph("", _S())],
    ]

    style = _table_style_base() + [
        ('BACKGROUND', (0, 2), (-1, 2), DARK),
        ('ALIGN',      (0, 3), (-1, 3), 'CENTER'),
        ('VALIGN',     (0, 3), (-1, 3), 'MIDDLE'),
    ]
    t = Table(rows, colWidths=col_w, rowHeights=[None, 22, None, sig_h + 8])
    t.setStyle(TableStyle(style))
    return t


# ═══════════════════════════════════════════════════════════════════════
# Główna funkcja — publiczne API
# ═══════════════════════════════════════════════════════════════════════

def generate_pdf(document, items):
    """Zwraca bajty PDF zgodne z szablonami HTML Brueggen."""
    _reg_fonts()

    doc_type  = _v(document, 'doc_type', 'office')
    operation = _v(document, 'operation', 'wydanie')
    date_str  = _date_str(document)
    items     = list(items) if items else []

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )

    story = []

    # ── Tytuł zależny od typu dokumentu ──────────────────────────
    if doc_type == 'office':
        title = "Protokół wydania / zwrotu sprzętu IT - Office"
    elif doc_type == 'produkcja':
        title = "Protokół wydania / zwrotu sprzętu IT – Produkcja"
    else:
        title = "Protokół wydania / zwrotu telefonu IT"

    # ── Nagłówek, logo, tytuł H1, wiersz intro ───────────────────
    story += _header_block(title, date_str, operation)

    # ── Typ operacji ──────────────────────────────────────────────
    op_pl = "Wydanie" if operation == 'wydanie' else "Zwrot"
    story.append(_sec_hdr("Typ operacji"))
    story.append(_op_box(op_pl))
    story.append(Spacer(1, 10))

    # ── Sprzęt / Telefon ──────────────────────────────────────────
    if doc_type == 'office':
        story.append(_sec_hdr("Sprzęt biurowy (Office)"))
        story.append(_equipment_table(items))
    elif doc_type == 'produkcja':
        story.append(_sec_hdr("Sprzęt produkcyjny"))
        story.append(_equipment_table(items))
    else:
        story.append(_sec_hdr("Dane telefonu"))
        story.append(_phone_table(items))

    # ── Zobowiązania ──────────────────────────────────────────────
    story += _obligations_block()
    story.append(Spacer(1, 12))

    # ── Dane osób + podpisy ───────────────────────────────────────
    story.append(_sec_hdr("Dane osób"))
    if doc_type == 'office':
        story.append(_people_table_office(document))
    else:
        story.append(_people_table_3col(document))

    # ── Stopka ────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "*Niepotrzebne skreślić",
        _S('fn', fontName='Arial-Italic', fontSize=8, textColor=CFOOT),
    ))

    pdf.build(story)
    return buf.getvalue()
