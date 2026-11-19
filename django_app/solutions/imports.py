import datetime

import openpyxl
from docx import Document


def _text(value):
    if isinstance(value, str):
        return value.strip()
    return value or ''


def _cell_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str) and value.strip():
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
            try:
                return datetime.datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _cell_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('tak', 'true', '1', 'x', 'yes')
    return bool(value)


def _cell_environment(value):
    if isinstance(value, str):
        v = value.strip().lower()
        if 'test' in v:
            return 'test'
        if 'prod' in v:
            return 'prod'
    return 'prod'


def parse_updatelogs_xlsx(file_obj):
    """Parse an UpdateLogs.xlsx (official PDM template) into a list of dicts
    matching SolutionLog fields.

    Fixed column layout of the official template (sheet named ~'UpdateLog'),
    header on row 2, data from row 3:
      A LP | B Data rozpoczęcia aktualizacji | C Osoba odpowiedzialna |
      D Cel aktualizacji | E Opis aktualizacji |
      F Blokery/Problemy techniczne podczas procesowania aktualizacji lub jej wdrażania |
      G Środowisko | H Wdrożono? | I Data wdrożenia aktualizacji |
      J Informacja do użytkownika końcowego?
    """
    wb = openpyxl.load_workbook(file_obj, data_only=True)
    ws = None
    for name in wb.sheetnames:
        if 'updatelog' in name.lower().replace(' ', ''):
            ws = wb[name]
            break
    if ws is None:
        ws = wb[wb.sheetnames[0]]

    rows = []
    for raw in ws.iter_rows(min_row=3, values_only=True):
        if raw is None:
            continue
        row = list(raw) + [None] * (10 - len(raw))
        (_lp, start_date, responsible, goal, description, blockers,
         environment, deployed, log_date, notified) = row[:10]

        if not any([start_date, goal, description, log_date]):
            continue  # blank leftover template row

        rows.append({
            'update_start_date':  _cell_date(start_date),
            'responsible_person': _text(responsible),
            'goal':                _text(goal),
            'description':         _text(description),
            'blockers':            _text(blockers),
            'environment':         _cell_environment(environment),
            'deployed':            _cell_bool(deployed),
            'log_date':            _cell_date(log_date),
            'user_notified':       _cell_bool(notified),
        })
    return rows


def parse_checklist_docx(file_obj):
    """Parse a SolutionChecklist.docx and return the completed PDM step
    numbers (1-9), based on row order in the first table and the Word
    content-control checkbox state (w14:checked)."""
    doc = Document(file_obj)
    if not doc.tables:
        return []
    table = doc.tables[0]
    ns = '{http://schemas.microsoft.com/office/word/2010/wordml}'
    completed = []
    for i, row in enumerate(table.rows[1:], start=1):
        checked_elems = row._tr.findall(f'.//{ns}checked')
        if any(el.get(f'{ns}val') == '1' for el in checked_elems):
            completed.append(i)
    return completed
