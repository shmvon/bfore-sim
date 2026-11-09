"""Maintenance of the translation files in translations/.

    python3 i18n_tools.py check          report missing translations and broken {placeholders}
    python3 i18n_tools.py sync           after editing en.xlsx: add/remove keys in all languages,
                                         keeping existing translations
    python3 i18n_tools.py new xx         create an empty file for a new language code xx

en.xlsx is the master: new texts are added there first (key, English, note),
then 'sync' copies them to every language file with an empty translation.
"""
import os
import re
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from i18n import TRANSLATIONS_DIR, FORMAT_DEFAULTS

PLACEHOLDER = re.compile(r'\{(\w+)\}')
HEADER_FILL = PatternFill('solid', fgColor='2B4B77')
HEADER_FONT = Font(bold=True, color='FFFFFF')
WRAP = Alignment(wrap_text=True, vertical='top')

FORMAT_HELP = {
    'language_name': 'Name of the language, written in the language itself (shown in the menu)',
    'decimal_separator': 'Decimal sign: . or ,',
    'thousands_separator': 'Sign between thousands, e.g. , or . or (space)',
    'currency_pattern': 'How amounts are written: {symbol} {amount} or {amount} {symbol}',
    'percent_pattern': 'How percentages are written: {value}% or {value} %',
    'confidence': 'Quality of the draft: high, medium or low (shown on the translations page; '
                  'once every text has the status reviewed, the page shows Reviewed)',
}

README = [
    "HOW TO EDIT THIS FILE",
    "",
    "1. Go to the sheet 'Texts'. Write your translation in the column 'Translation'.",
    "   The column 'English' shows the original text. Do not change the column 'key'.",
    "2. Words between curly brackets, such as {gains} or {round}, are filled in by the game",
    "   (a number, an amount or a percentage). Keep them exactly as they are, but you may",
    "   move them to another place in the sentence.",
    "3. **word** (two stars on each side) makes a word bold. Keep the stars around the word",
    "   that should be bold in your language.",
    "4. A new line inside a cell (Alt+Enter, on Mac Option+Enter) starts a new line on screen.",
    "5. Leave a cell empty if you are not sure: the English text is shown instead.",
    "6. In the column 'Status', write 'reviewed' once a text has been checked.",
    "7. The sheet 'Glossary' lists the key terms. Use the same term everywhere.",
    "8. The sheet 'Format' sets how numbers and amounts are written in your language.",
    "",
    "Save the file in Excel format (.xlsx) with the same name and send it back.",
]


def path(lang):
    return os.path.join(TRANSLATIONS_DIR, f'{lang}.xlsx')


def _header(ws, titles, widths):
    ws.append(titles)
    for i, (cell, width) in enumerate(zip(ws[1], widths)):
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        ws.column_dimensions[cell.column_letter].width = width
    ws.freeze_panes = 'A2'


def _style(ws):
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = WRAP


def _read_texts(lang):
    """{key: row dict} of the Texts sheet, in file order."""
    wb = load_workbook(path(lang), data_only=True)
    ws = wb['Texts']
    header = [str(c.value).strip().lower() for c in ws[1]]
    rows = {}
    for values in ws.iter_rows(min_row=2, values_only=True):
        row = {header[i]: ('' if values[i] is None else str(values[i])) for i in range(len(header))}
        if row.get('key'):
            rows[row['key']] = row
    return rows, wb


def _read_pairs(wb, sheet, cols):
    if sheet not in wb.sheetnames:
        return []
    return [tuple('' if v is None else v for v in r[:cols])
            for r in wb[sheet].iter_rows(min_row=2, values_only=True) if r and r[0]]


def write_language(lang, texts, formats=None, glossary=None):
    """Write translations/<lang>.xlsx.

    texts: list of (key, english, translation, note, status); for 'en' translation/status are ignored.
    formats: {setting: value}; glossary: list of (english term, translation, note).
    """
    os.makedirs(TRANSLATIONS_DIR, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Read me'
    ws.column_dimensions['A'].width = 100
    for line in README:
        ws.append([line])
    ws['A1'].font = Font(bold=True, size=13)

    ws = wb.create_sheet('Texts')
    if lang == 'en':
        _header(ws, ['key', 'English', 'Notes for translator'], [30, 80, 45])
        for key, english, _tr, note, _st in texts:
            ws.append([key, english, note])
    else:
        _header(ws, ['key', 'English', 'Translation', 'Notes for translator', 'Status'], [28, 60, 60, 35, 12])
        for key, english, translation, note, status in texts:
            ws.append([key, english, translation, note, status])
    _style(ws)

    ws = wb.create_sheet('Format')
    _header(ws, ['setting', 'value', 'explanation'], [22, 22, 70])
    formats = formats or {}
    for setting, default in list(FORMAT_DEFAULTS.items()) + [('confidence', '')]:
        if setting == 'confidence' and lang == 'en':
            continue
        value = formats.get(setting, default)
        if value == ' ':
            value = '(space)'
        ws.append([setting, value, FORMAT_HELP[setting]])

    ws = wb.create_sheet('Glossary')
    if lang == 'en':
        _header(ws, ['English term', 'Meaning in the game'], [30, 90])
        for term, _tr, note in glossary or []:
            ws.append([term, note])
    else:
        _header(ws, ['English term', 'Translation', 'Meaning in the game'], [30, 35, 70])
        for term, translation, note in glossary or []:
            ws.append([term, translation, note])
    _style(ws)
    wb.save(path(lang))


def master():
    rows, wb = _read_texts('en')
    glossary = [(g[0], '', g[1]) for g in _read_pairs(wb, 'Glossary', 2)]
    return rows, glossary


def languages():
    return sorted(f[:-5] for f in os.listdir(TRANSLATIONS_DIR)
                  if f.endswith('.xlsx') and f[:-5] not in ('en', 'countries') and not f.startswith('~$'))


def update_language(lang, translations=None, formats=None, glossary_terms=None, status='draft'):
    """Rebuild <lang>.xlsx from the master, keeping what is there and adding new translations."""
    en, en_glossary = master()
    old, old_formats, old_glossary = {}, {}, {}
    if os.path.exists(path(lang)):
        old, wb = _read_texts(lang)
        old_formats = {s: v for s, v, *_ in _read_pairs(wb, 'Format', 2)}
        old_glossary = {g[0]: g[1] for g in _read_pairs(wb, 'Glossary', 3)}
    translations = translations or {}
    texts = []
    for key, row in en.items():
        prev = old.get(key, {})
        tr = translations.get(key, prev.get('translation', ''))
        st = status if key in translations else prev.get('status', '')
        texts.append((key, row['english'], tr, row.get('notes for translator', ''), st))
    fmts = dict(old_formats)
    fmts.update(formats or {})
    terms = dict(old_glossary)
    terms.update(glossary_terms or {})
    glossary = [(term, terms.get(term, ''), note) for term, _, note in en_glossary]
    write_language(lang, texts, fmts, glossary)
    removed = [k for k in old if k not in en]
    return removed


def check():
    en, _ = master()
    problems = 0
    used = set()
    root = os.path.dirname(os.path.abspath(__file__))
    for folder in ('templates', '.'):
        for f in os.listdir(os.path.join(root, folder)):
            if f.endswith(('.html', '.py')):
                text = open(os.path.join(root, folder, f), encoding='utf-8').read()
                used.update(re.findall(r"\bt\('([a-z_]+\.[\w.]*[a-z0-9])'", text))
    for key in sorted(used - set(en)):
        print(f"en: key used in the code but missing in en.xlsx: {key}")
        problems += 1
    for lang in languages():
        rows, _ = _read_texts(lang)
        missing = [k for k in en if not rows.get(k, {}).get('translation', '').strip()]
        reviewed = sum(1 for r in rows.values() if r.get('status', '').strip().lower() == 'reviewed')
        print(f"{lang}: {len(en) - len(missing)}/{len(en)} translated, {reviewed} reviewed")
        for key, row in en.items():
            tr = rows.get(key, {}).get('translation', '')
            if not tr:
                continue
            if sorted(PLACEHOLDER.findall(tr)) != sorted(PLACEHOLDER.findall(row['english'])):
                print(f"  {lang} {key}: placeholders differ: {PLACEHOLDER.findall(row['english'])} vs {PLACEHOLDER.findall(tr)}")
                problems += 1
            if tr.count('**') % 2:
                print(f"  {lang} {key}: unpaired ** (bold marker)")
                problems += 1
            if len(tr) > 1.8 * len(row['english']) + 15:
                print(f"  {lang} {key}: much longer than English, check the layout")
    print('OK' if not problems else f'{problems} problem(s)')
    return problems


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'check':
        sys.exit(1 if check() else 0)
    elif cmd == 'sync':
        for lang in languages():
            removed = update_language(lang)
            print(f"{lang}: synced" + (f", removed {removed}" if removed else ''))
    elif cmd == 'new' and len(sys.argv) == 3:
        update_language(sys.argv[2])
        print(f"created {path(sys.argv[2])}")
    else:
        print(__doc__)
