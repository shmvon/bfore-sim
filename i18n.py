"""Translations, country settings and number formatting.

All texts live in Excel files in the folder 'translations':
  translations/en.xlsx, fr.xlsx, ...   one file per language (sheets: Texts, Format, Glossary)
  translations/countries.xlsx          countries, their languages, currency and wage slider

Templates use  {{ t('key', name=value) }}.  In the Excel files, {name} marks where a
value from the game goes, and **word** makes a word bold. Empty translations fall
back to English. Edited files are picked up automatically (no restart needed).
"""
import os
import re
import time
import unicodedata
import uuid
import sqlite3
from datetime import datetime

from flask import Blueprint, abort, g, redirect, render_template, request, send_from_directory, session
from markupsafe import Markup, escape
from openpyxl import load_workbook

import config

TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations')
DEFAULT_LANG = 'en'
COOKIE = 'bst_visitor'
NON_EU = 'NONEU'
# display order of languages in the menu
LANG_ORDER = ['en', 'fr', 'de', 'nl', 'it', 'sv', 'es', 'ro',
              'pl', 'da', 'fi', 'lt', 'lv', 'et', 'pt', 'hr',
              'bg', 'cs', 'el', 'hu', 'sk', 'sl', 'mt', 'nb', 'is']
FORMAT_DEFAULTS = {
    'language_name': '',
    'decimal_separator': '.',
    'thousands_separator': ',',
    'currency_pattern': '{symbol} {amount}',
    'percent_pattern': '{value}%',
}

bp = Blueprint('i18n', __name__)

_texts = {}       # lang -> {key: text}
_formats = {}     # lang -> {setting: value}
_countries = {}   # code -> {name, languages, currency, eur_rate, default_wage, max_wage, wage_step}
_info = {}        # lang -> {confidence, total, translated, reviewed} for the translations page
CONFIDENCE_LEVELS = ('high', 'medium', 'low')
_stamp = None
_last_check = 0.0


# ---------------------------------------------------------------- loading

def _rows(ws):
    """Rows of a sheet as dicts keyed by the (lower-case) header of the first row."""
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip().lower() if h is not None else '' for h in next(rows, [])]
    for row in rows:
        yield {header[i]: row[i] for i in range(min(len(header), len(row)))}


def _cell(value):
    return '' if value is None else str(value).strip()


def _load_language(path, lang):
    wb = load_workbook(path, read_only=True, data_only=True)
    texts, fmt = {}, dict(FORMAT_DEFAULTS)
    info = {'confidence': '', 'total': 0, 'translated': 0, 'reviewed': 0}
    column = 'english' if lang == DEFAULT_LANG else 'translation'
    if 'Texts' in wb.sheetnames:
        for row in _rows(wb['Texts']):
            key, text = _cell(row.get('key')), _cell(row.get(column))
            if not key:
                continue
            info['total'] += 1
            if text:
                texts[key] = text
                info['translated'] += 1
                if _cell(row.get('status')).lower() == 'reviewed':
                    info['reviewed'] += 1
    if 'Format' in wb.sheetnames:
        for row in _rows(wb['Format']):
            setting = _cell(row.get('setting'))
            value = '' if row.get('value') is None else str(row.get('value'))
            if setting in FORMAT_DEFAULTS:
                fmt[setting] = value.replace('(space)', ' ')
            elif setting == 'confidence':
                info['confidence'] = value.strip().lower()
    wb.close()
    return texts, fmt, info


def _load_countries(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    countries = {}
    for row in _rows(wb['Countries']):
        code = _cell(row.get('code')).upper()
        if not code:
            continue
        countries[code] = {
            'code': code,
            'name': _cell(row.get('name')),
            'languages': [l.strip().lower() for l in _cell(row.get('languages')).split(',') if l.strip()],
            'currency': _cell(row.get('currency')) or '€',
            'eur_rate': float(row.get('eur_rate') or 1),
            'default_wage': float(row.get('default_wage') or 2000),
            'max_wage': float(row.get('max_wage') or 6000),
            'wage_step': float(row.get('wage_step') or 250),
        }
    wb.close()
    return countries


def _files():
    if not os.path.isdir(TRANSLATIONS_DIR):
        return []
    return sorted(f for f in os.listdir(TRANSLATIONS_DIR)
                  if f.endswith('.xlsx') and not f.startswith('~$'))


def reload_if_changed(force=False):
    """(Re)load all Excel files when one of them changed; checked at most every 5 seconds."""
    global _stamp, _last_check, _texts, _formats, _countries, _info
    now = time.time()
    if not force and now - _last_check < 5:
        return
    _last_check = now
    files = _files()
    stamp = tuple((f, os.path.getmtime(os.path.join(TRANSLATIONS_DIR, f))) for f in files)
    if stamp == _stamp and not force:
        return
    texts, formats, countries, info = {}, {}, {}, {}
    for f in files:
        path = os.path.join(TRANSLATIONS_DIR, f)
        name = f[:-5]
        try:
            if name == 'countries':
                countries = _load_countries(path)
            else:
                texts[name], formats[name], info[name] = _load_language(path, name)
        except Exception as e:  # a broken file must not take the site down
            print(f"I18N: could not read {f}: {e}")
            if name in _texts:
                texts[name], formats[name], info[name] = _texts[name], _formats[name], _info.get(name, {})
    _texts, _formats, _countries, _info, _stamp = texts, formats, countries, info, stamp
    print(f"I18N: loaded languages {sorted(_texts)} and {len(_countries)} countries")


# ---------------------------------------------------------------- languages and countries

def available_languages():
    langs = [l for l in LANG_ORDER if l in _texts]
    return langs + sorted(l for l in _texts if l not in LANG_ORDER)


def country_languages(code):
    """Languages offered for a country: its own languages that exist, plus English."""
    available = available_languages()
    country = _countries.get(code)
    if country is None or code == NON_EU or '*' in country['languages']:
        return available
    langs = [l for l in country['languages'] if l in available]
    if DEFAULT_LANG not in langs:
        langs.append(DEFAULT_LANG)
    return langs


def current_lang():
    return getattr(g, 'lang', DEFAULT_LANG)


def current_country():
    return getattr(g, 'country', None)


def country_info(code=None):
    code = code or current_country()
    return _countries.get(code) or {'code': None, 'name': '', 'languages': [], 'currency': '€',
                                    'eur_rate': 1.0, 'default_wage': 2000.0, 'max_wage': 6000.0,
                                    'wage_step': 250.0}


def country_name(code):
    key = 'country.' + code
    if key in _texts.get(current_lang(), {}) or key in _texts.get(DEFAULT_LANG, {}):
        return t(key)
    return _countries.get(code, {}).get('name', code)


def country_list():
    """Countries for the menu, sorted by their name in the current language, Non-EU last."""
    items = [{'code': c, 'label': country_name(c), 'value': _countries[c]['name']}
             for c in _countries if c != NON_EU]
    def sort_key(item):  # ignore accents, so that Österreich sorts under O
        text = unicodedata.normalize('NFKD', str(item['label']).lower())
        return ''.join(ch for ch in text if not unicodedata.combining(ch))
    items.sort(key=sort_key)
    if NON_EU in _countries:
        items.append({'code': NON_EU, 'label': country_name(NON_EU), 'value': _countries[NON_EU]['name']})
    return items


def language_list():
    langs = country_languages(current_country()) if current_country() else available_languages()
    return [{'code': l, 'label': _formats.get(l, {}).get('language_name') or l} for l in langs]


# ---------------------------------------------------------------- remembering the choice

def _prefs_db():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.PREFS_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS visitor_prefs
                    (visitor_id TEXT PRIMARY KEY, country TEXT, language TEXT, updated_at TEXT)''')
    return conn


def _load_prefs(visitor_id):
    if not visitor_id:
        return None
    try:
        conn = _prefs_db()
        row = conn.execute('SELECT country, language FROM visitor_prefs WHERE visitor_id = ?',
                           (visitor_id,)).fetchone()
        conn.close()
        return row
    except sqlite3.Error as e:
        print(f"I18N: could not read preferences: {e}")
        return None


def _save_prefs(visitor_id, country, lang):
    try:
        conn = _prefs_db()
        conn.execute('INSERT OR REPLACE INTO visitor_prefs VALUES (?, ?, ?, ?)',
                     (visitor_id, country, lang, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"I18N: could not save preferences: {e}")


def _resolve_locale():
    reload_if_changed()
    if request.endpoint == 'static':
        return
    country, lang = session.get('country'), session.get('lang')
    if country is None and lang is None:
        saved = _load_prefs(request.cookies.get(COOKIE))
        if saved:
            country, lang = saved
            session['country'], session['lang'] = country, lang
    if country not in _countries:
        country = None
    allowed = country_languages(country) if country else available_languages()
    if lang not in allowed:
        lang = request.accept_languages.best_match(allowed) or DEFAULT_LANG
    g.country, g.lang = country, lang


@bp.route('/locale', methods=['POST'])
def set_locale():
    country = request.form.get('country') or None
    if country not in _countries:
        country = None
    lang = request.form.get('language') or current_lang()
    if country:
        allowed = country_languages(country)
        if lang not in allowed:
            lang = current_lang() if current_lang() in allowed else allowed[0]
    elif lang not in available_languages():
        lang = current_lang()
    session['country'], session['lang'] = country, lang

    visitor_id = request.cookies.get(COOKIE) or str(uuid.uuid4())
    _save_prefs(visitor_id, country, lang)

    target = request.form.get('next') or '/'
    if not target.startswith('/') or target.startswith('//'):
        target = '/'
    response = redirect(target)
    response.set_cookie(COOKIE, visitor_id, max_age=365 * 24 * 3600, httponly=True, samesite='Lax')
    return response


# ---------------------------------------------------------------- translations page

def language_overview():
    """One row per language file for the translations page."""
    rows = []
    for lang in available_languages():
        info = _info.get(lang, {})
        countries = [country_name(c) for c in _countries
                     if c != NON_EU and lang in _countries[c]['languages']]
        total = info.get('total') or 0
        reviewed = info.get('reviewed') or 0
        rows.append({
            'code': lang,
            'name': _formats.get(lang, {}).get('language_name') or lang,
            'confidence': 'source' if lang == DEFAULT_LANG else (
                'reviewed' if total and reviewed == total else info.get('confidence') or 'low'),
            'translated': info.get('translated') or 0,
            'reviewed': reviewed,
            'total': total,
            'countries': sorted(str(c) for c in countries),
            'file': lang + '.xlsx',
        })
    return rows


@bp.route('/translations')
def translations_page():
    return render_template('translations.html', languages=language_overview())


@bp.route('/translations/<name>.xlsx')
def translation_file(name):
    if name not in _texts and name != 'countries':
        abort(404)
    return send_from_directory(TRANSLATIONS_DIR, name + '.xlsx', as_attachment=True)


# ---------------------------------------------------------------- texts and numbers

_placeholder = re.compile(r'\{(\w+)\}')
_bold = re.compile(r'\*\*(.+?)\*\*')


def t(key, **values):
    """Translated text for key, with {placeholders} filled in and **bold** applied."""
    lang = current_lang()
    text = _texts.get(lang, {}).get(key) or _texts.get(DEFAULT_LANG, {}).get(key) or key
    html = str(escape(text))
    html = _bold.sub(r'<b>\1</b>', html).replace('\n', '<br>')

    def fill(match):
        name = match.group(1)
        return str(escape(values[name])) if name in values else match.group(0)
    return Markup(_placeholder.sub(fill, html))


def _fmt(setting):
    return _formats.get(current_lang(), {}).get(setting, FORMAT_DEFAULTS[setting])


def num(x, decimals=None):
    """A number with the decimal separator of the current language.
    Without decimals it keeps the precision the game calculated (as before)."""
    if x is None:
        return ''
    s = str(x) if decimals is None else f'{x:.{decimals}f}'
    return s.replace('.', _fmt('decimal_separator'))


def pct(x, decimals=None, sign=False):
    value = num(x, decimals)
    if sign and x is not None and x >= 0:
        value = '+' + value
    return _fmt('percent_pattern').replace('{value}', value)


def _group(n):
    return f'{n:,}'.replace(',', _fmt('thousands_separator'))


def money(eur, sign=False):
    """An amount calculated in EUR, shown in the currency of the selected country."""
    if eur is None:
        return ''
    info = country_info()
    amount = int(eur * info['eur_rate'])
    text = _fmt('currency_pattern').replace('{symbol}', info['currency']).replace('{amount}', _group(abs(amount)))
    if amount < 0:
        return '-' + text
    return ('+' + text) if sign else text


def currency_parts():
    """Text before and after an amount, e.g. ('€ ', '') or ('', ' kr'), for input fields."""
    pattern = _fmt('currency_pattern').replace('{symbol}', country_info()['currency'])
    before, _, after = pattern.partition('{amount}')
    return before, after


def init_app(app):
    reload_if_changed(force=True)
    app.register_blueprint(bp)
    app.before_request(_resolve_locale)
    app.jinja_env.globals.update(
        Markup=Markup, t=t, num=num, pct=pct, money=money, currency_parts=currency_parts,
        current_lang=current_lang, current_country=current_country, country_info=country_info,
        country_list=country_list, language_list=language_list,
    )
