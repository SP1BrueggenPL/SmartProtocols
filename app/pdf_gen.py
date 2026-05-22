import io
import base64
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# Font registration – use Windows Arial (supports Polish characters)
# ---------------------------------------------------------------------------
_FONTS_REGISTERED = False

WINDOWS_FONTS = 'C:\\Windows\\Fonts'

def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    try:
        pdfmetrics.registerFont(TTFont('Arial', os.path.join(WINDOWS_FONTS, 'arial.ttf')))
        pdfmetrics.registerFont(TTFont('Arial-Bold', os.path.join(WINDOWS_FONTS, 'arialbd.ttf')))
        pdfmetrics.registerFont(TTFont('Arial-Italic', os.path.join(WINDOWS_FONTS, 'ariali.ttf')))
        _FONTS_REGISTERED = True
        FONT = 'Arial'
        FONT_BOLD = 'Arial-Bold'
    except Exception:
        # Fallback to built-in Helvetica (no Polish diacritics but safe)
        FONT = 'Helvetica'
        FONT_BOLD = 'Helvetica-Bold'
    return FONT, FONT_BOLD


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BLUE = colors.HexColor('#1a4d8f')
LIGHT_BLUE = colors.HexColor('#dce8f7')
HEADER_GREY = colors.HexColor('#f0f4fa')
BORDER_COLOR = colors.HexColor('#a0b4d0')
TEXT_COLOR = colors.HexColor('#1a1a1a')

DOC_TYPE_LABELS = {
    'office': 'Office',
    'telefon': 'Telefon',
    'produkcja': 'Produkcja',
}

OPERATION_LABELS = {
    'wydanie': 'wydania',
    'zwrot': 'zwrotu',
}

OBLIGATIONS = [
    'Przyjmujący będzie korzystał z ww. wyposażenia wyłącznie w celu realizacji zadań '
    'postawionych przez firmę Brueggen Polska Sp. z o.o.',
    'Przyjmujący jest świadomy, że firma nie jest w stanie zapewnić poufności danych '
    'w skrzynce mailowej; cała korespondencja powinna mieć charakter służbowy.',
    'Przyjmujący zobowiązuje się dbać o powierzone wyposażenie: zabezpieczyć je przed '
    'kradzieżą, zgubieniem, zalaniem, pożarem, zniszczeniem oraz przed dostępem osób '
    'nieupoważnionych.',
    'Przyjmujący nie będzie dokonywał samodzielnie żadnych zmian w konfiguracji '
    'sprzętu i oprogramowania.',
    'Naprawy sprzętu wykonywane będą wyłącznie w autoryzowanych punktach serwisowych '
    'na podstawie przekazanych dokumentów.',
    'Z chwilą zakończenia pracy przyjmujący zwróci całe wyposażenie w dobrym stanie '
    'do Działu IT.',
]


def _styles(font, font_bold):
    normal = ParagraphStyle(
        'normal', fontName=font, fontSize=9, leading=13, textColor=TEXT_COLOR
    )
    bold = ParagraphStyle(
        'bold', fontName=font_bold, fontSize=9, leading=13, textColor=TEXT_COLOR
    )
    small = ParagraphStyle(
        'small', fontName=font, fontSize=7.5, leading=11, textColor=TEXT_COLOR
    )
    bullet = ParagraphStyle(
        'bullet', fontName=font, fontSize=8.5, leading=13, textColor=TEXT_COLOR,
        leftIndent=12, firstLineIndent=-12
    )
    heading = ParagraphStyle(
        'heading', fontName=font_bold, fontSize=11, leading=16,
        textColor=BLUE, spaceAfter=4
    )
    return normal, bold, small, bullet, heading


def _sig_image(b64_data, width=55*mm, height=22*mm):
    """Convert base64 signature PNG to a reportlab Image."""
    if not b64_data:
        return None
    try:
        # Strip data-url prefix if present
        if ',' in b64_data:
            b64_data = b64_data.split(',', 1)[1]
        data = base64.b64decode(b64_data)
        return Image(io.BytesIO(data), width=width, height=height)
    except Exception:
        return None


def _table_style_base():
    return [
        ('FONTNAME', (0, 0), (-1, 0), 'Arial-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('LEADING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HEADER_GREY]),
    ]


def generate_pdf(document, items):
    """Generate a PDF for the given document and return bytes."""
    fonts = _register_fonts()
    font, font_bold = fonts if fonts else ('Helvetica', 'Helvetica-Bold')
    normal, bold, small, bullet, heading = _styles(font, font_bold)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    content_width = A4[0] - 30*mm
    story = []

    # -----------------------------------------------------------------------
    # HEADER
    # -----------------------------------------------------------------------
    header_data = [[
        Paragraph('<b>Brueggen Polska Sp. z o.o.</b><br/>Celejów 59, 08-470 Wilga', bold),
        Paragraph(
            f'<b>Protokół wydania / zwrotu sprzętu IT<br/>'
            f'{DOC_TYPE_LABELS.get(document["doc_type"], "")}</b>',
            ParagraphStyle('hdr', fontName=font_bold, fontSize=12, leading=16,
                           textColor=BLUE, alignment=1)
        ),
        Paragraph(
            f'<b>Nr: {document["doc_number"]}</b><br/>'
            f'Data: {document["doc_date"]}',
            ParagraphStyle('hdr_right', fontName=font, fontSize=9, leading=13,
                           textColor=TEXT_COLOR, alignment=2)
        ),
    ]]
    header_table = Table(header_data, colWidths=[content_width * 0.3, content_width * 0.4, content_width * 0.3])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5*mm))

    # -----------------------------------------------------------------------
    # Operation type badge
    # -----------------------------------------------------------------------
    op_label = 'WYDANIE' if document['operation'] == 'wydanie' else 'ZWROT'
    op_bg = colors.HexColor('#d4edda') if document['operation'] == 'wydanie' else colors.HexColor('#fff3cd')
    op_text_color = colors.HexColor('#155724') if document['operation'] == 'wydanie' else colors.HexColor('#856404')

    op_data = [[Paragraph(f'Typ operacji: <b>{op_label}</b>', ParagraphStyle(
        'op', fontName=font_bold, fontSize=10, textColor=op_text_color
    ))]]
    op_table = Table(op_data, colWidths=[content_width])
    op_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), op_bg),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(op_table)
    story.append(Spacer(1, 4*mm))

    # -----------------------------------------------------------------------
    # Intro paragraph
    # -----------------------------------------------------------------------
    op_verb = 'przekazał' if document['operation'] == 'wydanie' else 'przyjął'
    op_noun = 'użytkowania' if document['operation'] == 'wydanie' else 'zwrotu'
    story.append(Paragraph(
        f'W dniu <b>{document["doc_date"]}</b> Dział IT Brueggen Polska Sp. z o.o. '
        f'<b>{op_verb}</b> do <b>{op_noun}</b> następujące wyposażenie:',
        normal
    ))
    story.append(Spacer(1, 4*mm))

    # -----------------------------------------------------------------------
    # Equipment table
    # -----------------------------------------------------------------------
    if document['doc_type'] == 'telefon':
        _add_phone_table(story, items, content_width, font, font_bold, normal)
    else:
        _add_equipment_table(story, items, document['doc_type'], content_width, font, font_bold)

    story.append(Spacer(1, 5*mm))

    # -----------------------------------------------------------------------
    # Obligations
    # -----------------------------------------------------------------------
    story.append(Paragraph('Warunki korzystania z wyposażenia:', heading))
    for i, obl in enumerate(OBLIGATIONS, 1):
        story.append(Paragraph(f'{i}. {obl}', bullet))
    story.append(Spacer(1, 5*mm))

    # -----------------------------------------------------------------------
    # Person data + signatures
    # -----------------------------------------------------------------------
    story.append(Paragraph('Dane osób i podpisy:', heading))
    _add_signatures_table(story, document, content_width, font, font_bold, normal, small)

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        '<i>* Niepotrzebne skreślić</i>',
        ParagraphStyle('footnote', fontName=font, fontSize=7.5, textColor=colors.grey)
    ))

    doc.build(story)
    return buf.getvalue()


def _add_equipment_table(story, items, doc_type, content_width, font, font_bold):
    type_label = 'Sprzęt biurowy (Office)' if doc_type == 'office' else 'Sprzęt produkcyjny (Produkcja)'

    col_w = [
        content_width * 0.22,  # Sprzęt
        content_width * 0.28,  # Producent/Model
        content_width * 0.22,  # Nr seryjny
        content_width * 0.10,  # Ilość
        content_width * 0.18,  # Nr wewnętrzny
    ]

    header = ['Sprzęt', 'Producent / Model', 'Nr seryjny', 'Ilość', 'Nr wewnętrzny']
    rows = [header]

    if items:
        for item in items:
            rows.append([
                item['equipment_type'] or '',
                item['manufacturer_model'] or '',
                item['serial_number'] or '',
                str(item['quantity'] or 1),
                item['internal_number'] or '',
            ])
    else:
        for _ in range(4):
            rows.append(['', '', '', '', ''])

    ts = _table_style_base()
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(ts))
    story.append(t)


def _add_phone_table(story, items, content_width, font, font_bold, normal):
    item = items[0] if items else {}

    def val(key):
        if hasattr(item, '__getitem__'):
            try:
                return item[key] or ''
            except (KeyError, IndexError):
                return ''
        return ''

    col_w = [content_width * 0.38, content_width * 0.62]

    def row(label, value=''):
        return [
            Paragraph(f'<b>{label}</b>', ParagraphStyle(
                'lbl', fontName=font_bold, fontSize=8.5, leading=12
            )),
            Paragraph(str(value), ParagraphStyle(
                'val', fontName=font, fontSize=8.5, leading=12
            )),
        ]

    accessories = []
    if val('acc_foil'):
        accessories.append('Folia/Szybka')
    if val('acc_case'):
        accessories.append('Etui')
    if val('acc_charger'):
        accessories.append('Ładowarka')
    if val('acc_headphones'):
        accessories.append('Słuchawki')
    acc_str = ', '.join(accessories) if accessories else '—'

    rows = [
        [Paragraph('<b>Pole</b>', ParagraphStyle('h', fontName=font_bold, fontSize=8.5, textColor=BLUE)),
         Paragraph('<b>Wartość</b>', ParagraphStyle('h', fontName=font_bold, fontSize=8.5, textColor=BLUE))],
        row('Rodzaj telefonu', val('phone_type')),
        row('Nr IMEI', val('imei')),
        row('Nr seryjny', val('serial_number')),
        row('Nazwa wewnętrzna', val('internal_name')),
        row('Nr telefonu', val('phone_number')),
        row('Nr karty SIM', val('sim_number')),
        row('Nr PIN telefonu', val('pin_phone')),
        row('Nr PIN karty SIM', val('pin_sim')),
        row('Akcesoria', acc_str),
        row('Uwagi', val('notes')),
    ]

    ts = [
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HEADER_GREY]),
        ('BACKGROUND', (0, 1), (0, -1), HEADER_GREY),
    ]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle(ts))
    story.append(t)


def _add_signatures_table(story, document, content_width, font, font_bold, normal, small):
    col_w = content_width / 2 - 2*mm

    issuer_sig = _sig_image(document['sig_issuer'], width=col_w * 0.8, height=20*mm)
    receiver_sig = _sig_image(document['sig_receiver'], width=col_w * 0.8, height=20*mm)

    sig_placeholder = Paragraph(
        '<br/><br/><br/>',
        ParagraphStyle('sp', fontName=font, fontSize=8)
    )

    def person_cell(label, name, sig_img):
        cell_content = [
            Paragraph(f'<b>{label}</b>', ParagraphStyle(
                'lbl', fontName=font_bold, fontSize=9, textColor=BLUE
            )),
            Paragraph(name or '', normal),
            Spacer(1, 3*mm),
            Paragraph('Podpis:', small),
            sig_img if sig_img else sig_placeholder,
        ]
        return cell_content

    # Person data table (2 columns side by side)
    person_data = [[
        Paragraph('<b>Przekazujący</b>', ParagraphStyle('h', fontName=font_bold, fontSize=9, textColor=BLUE)),
        Paragraph('<b>Przyjmujący</b>', ParagraphStyle('h', fontName=font_bold, fontSize=9, textColor=BLUE)),
    ], [
        [
            Paragraph(document['issuer_name'] or '', normal),
            Spacer(1, 2*mm),
            Paragraph('Podpis:', small),
            issuer_sig if issuer_sig else Spacer(1, 22*mm),
        ],
        [
            Paragraph(document['receiver_name'] or '', normal),
            Spacer(1, 2*mm),
            Paragraph('Podpis:', small),
            receiver_sig if receiver_sig else Spacer(1, 22*mm),
        ],
    ]]

    if document['network_name']:
        person_data.append([
            Paragraph(f'Nazwa sieciowa: <b>{document["network_name"]}</b>', normal),
            Paragraph('', normal),
        ])

    ts = [
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    t = Table(person_data, colWidths=[content_width / 2, content_width / 2])
    t.setStyle(TableStyle(ts))
    story.append(t)

    if document['signed_at']:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f'<i>Podpisano: {document["signed_at"][:16].replace("T", " ")}</i>',
            ParagraphStyle('ts', fontName=font, fontSize=7.5, textColor=colors.grey)
        ))
