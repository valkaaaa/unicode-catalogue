import os
import csv
import bisect
import tkinter as tk
from tkinter import ttk, font as tkfont, filedialog, messagebox
import unicodedata as ud
import html as html_module
from collections import OrderedDict

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
else:
    try:
        from PIL import ImageTk
        HAS_IMAGETK = True
    except ImportError:
        HAS_IMAGETK = False


# ============================================================
#  Поиск шрифтов
# ============================================================
def _find(cands):
    for p in cands:
        if os.path.exists(p):
            return p
    return None

FONT_DEFAULT = _find([
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    'C:/Windows/Fonts/segoeui.ttf',
    'C:/Windows/Fonts/arial.ttf',
    '/System/Library/Fonts/Supplemental/Arial.ttf',
])
FONT_EMOJI = _find([
    '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',
    '/usr/share/fonts/noto/NotoColorEmoji.ttf',
    '/usr/share/fonts/noto-emoji/NotoColorEmoji.ttf',
    'C:/Windows/Fonts/seguiemj.ttf',
    '/System/Library/Fonts/Apple Color Emoji.ttc',
])
FONT_SYMBOLS = _find([
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    'C:/Windows/Fonts/seguisym.ttf',
    '/System/Library/Fonts/Apple Symbols.ttf',
])
FONT_CJK = _find([
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    'C:/Windows/Fonts/msgothic.ttc',
    '/System/Library/Fonts/PingFang.ttc',
])


# ============================================================
#  Pillow: кэш, проверка глифа, рендер эмодзи
# ============================================================
_pil_fonts = {}
_glyph_cache = {}
_emoji_cache = OrderedDict()
EMOJI_CACHE_MAX = 800


def _pil_font(path, size):
    key = (path, size)
    if key not in _pil_fonts:
        try:
            _pil_fonts[key] = ImageFont.truetype(path, size)
        except Exception:
            _pil_fonts[key] = None
    return _pil_fonts[key]


def has_glyph(path, ch):
    if not HAS_PIL or not path:
        return None
    key = (path, ch)
    if key in _glyph_cache:
        return _glyph_cache[key]
    font = _pil_font(path, 32)
    if font is None:
        _glyph_cache[key] = None
        return None
    try:
        if ch == '\uFFFF':
            res = False
        else:
            m1 = font.getmask(ch, mode='L')
            m2 = font.getmask('\uFFFF', mode='L')
            res = (m1.size != m2.size) or (bytes(m1) != bytes(m2))
    except Exception:
        res = None
    _glyph_cache[key] = res
    return res


def render_emoji(cp, size=40):
    if not (HAS_PIL and HAS_IMAGETK and FONT_EMOJI):
        return None
    key = (cp, size)
    if key in _emoji_cache:
        _emoji_cache.move_to_end(key)
        return _emoji_cache[key]

    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.ANTIALIAS

    result = None
    try:
        font_size = size * 2
        try:
            font = ImageFont.truetype(FONT_EMOJI, font_size,
                                      layout_engine=ImageFont.Layout.BASIC)
        except Exception:
            font = ImageFont.truetype(FONT_EMOJI, 109)

        def _draw(text):
            canvas_size = font_size * 2
            img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            try:
                d.text((canvas_size // 2, canvas_size // 2), text,
                       font=font, embedded_color=True, anchor='mm')
            except Exception:
                d.text((canvas_size // 2, canvas_size // 2), text,
                       font=font, anchor='mm')
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
            else:
                img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            return img

        img = _draw(chr(cp))
        notdef = _draw('\uFFFF')
        if img.tobytes() != notdef.tobytes():
            img.thumbnail((size, size), resample)
            final = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            offset = ((size - img.width) // 2, (size - img.height) // 2)
            final.paste(img, offset)
            result = ImageTk.PhotoImage(final)
    except Exception:
        result = None

    _emoji_cache[key] = result
    while len(_emoji_cache) > EMOJI_CACHE_MAX:
        _emoji_cache.popitem(last=False)
    return result


def pick_font_path(cp):
    if 0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF:
        return FONT_EMOJI or FONT_SYMBOLS or FONT_DEFAULT
    if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF
            or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF):
        return FONT_CJK or FONT_DEFAULT
    return FONT_DEFAULT


def is_emoji_cp(cp):
    return (0x1F000 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF)


# ============================================================
#  Категории
# ============================================================
INVISIBLE = {
    'Cc', 'Cf', 'Cs', 'Cn', 'Co',
    'Zl', 'Zp', 'Zs',
    'Mn', 'Mc', 'Me',
}
CAT_COLORS = {
    'Cc': '#c02020', 'Cf': '#c06000', 'Cs': '#900000', 'Cn': '#909090',
    'Co': '#b050b0', 'Zl': '#0060c0', 'Zp': '#0060c0', 'Zs': '#0060c0',
    'Mn': '#6040a0', 'Mc': '#6040a0', 'Me': '#6040a0',
}
CATEGORY_NAMES = {
    'Lu': 'Letter, uppercase', 'Ll': 'Letter, lowercase',
    'Lt': 'Letter, titlecase', 'Lm': 'Letter, modifier', 'Lo': 'Letter, other',
    'Mn': 'Mark, nonspacing', 'Mc': 'Mark, spacing combining',
    'Me': 'Mark, enclosing',
    'Nd': 'Number, decimal digit', 'Nl': 'Number, letter', 'No': 'Number, other',
    'Pc': 'Punctuation, connector', 'Pd': 'Punctuation, dash',
    'Ps': 'Punctuation, open', 'Pe': 'Punctuation, close',
    'Pi': 'Punctuation, initial quote', 'Pf': 'Punctuation, final quote',
    'Po': 'Punctuation, other',
    'Sm': 'Symbol, math', 'Sc': 'Symbol, currency', 'Sk': 'Symbol, modifier',
    'So': 'Symbol, other',
    'Zs': 'Separator, space', 'Zl': 'Separator, line', 'Zp': 'Separator, paragraph',
    'Cc': 'Other, control', 'Cf': 'Other, format', 'Cs': 'Other, surrogate',
    'Co': 'Other, private use', 'Cn': 'Other, not assigned',
}
CATEGORY_GROUPS = {
    'Буквы':        {'Lu', 'Ll', 'Lt', 'Lm', 'Lo'},
    'Цифры':        {'Nd', 'Nl', 'No'},
    'Пунктуация':   {'Pc', 'Pd', 'Ps', 'Pe', 'Pi', 'Pf', 'Po'},
    'Символы':      {'Sm', 'Sc', 'Sk', 'So'},
    'Метки':        {'Mn', 'Mc', 'Me'},
    'Разделители':  {'Zs', 'Zl', 'Zp'},
    'Прочие':       {'Cc', 'Cf', 'Cs', 'Co', 'Cn'},
}


def binary_for(cp):
    bits = 16 if cp <= 0xFFFF else 24
    s = format(cp, f'0{bits}b')
    return '\n'.join(s[i:i+8] for i in range(0, len(s), 8))


def cell_info(cp):
    try:
        ch = chr(cp)
        cat = ud.category(ch)
    except (ValueError, TypeError):
        return {'kind': 'binary', 'color': '#999',
                'text': binary_for(cp), 'cat': '?'}
    if cat in INVISIBLE:
        return {'kind': 'binary', 'color': CAT_COLORS.get(cat, '#909090'),
                'text': binary_for(cp), 'cat': cat}
    return {'kind': 'char', 'char': ch, 'cat': cat}


# ============================================================
#  Блоки Unicode
# ============================================================
BLOCKS = [
    ('Basic Latin', 0x0000, 0x007F),
    ('Latin-1 Supplement', 0x0080, 0x00FF),
    ('Latin Extended-A', 0x0100, 0x017F),
    ('Latin Extended-B', 0x0180, 0x024F),
    ('IPA Extensions', 0x0250, 0x02AF),
    ('Spacing Modifier Letters', 0x02B0, 0x02FF),
    ('Combining Diacritical Marks', 0x0300, 0x036F),
    ('Greek and Coptic', 0x0370, 0x03FF),
    ('Cyrillic', 0x0400, 0x04FF),
    ('Cyrillic Supplement', 0x0500, 0x052F),
    ('Armenian', 0x0530, 0x058F),
    ('Hebrew', 0x0590, 0x05FF),
    ('Arabic', 0x0600, 0x06FF),
    ('Syriac', 0x0700, 0x074F),
    ('Arabic Supplement', 0x0750, 0x077F),
    ('Thaana', 0x0780, 0x07BF),
    ('NKo', 0x07C0, 0x07FF),
    ('Samaritan', 0x0800, 0x083F),
    ('Mandaic', 0x0840, 0x085F),
    ('Devanagari', 0x0900, 0x097F),
    ('Bengali', 0x0980, 0x09FF),
    ('Gurmukhi', 0x0A00, 0x0A7F),
    ('Gujarati', 0x0A80, 0x0AFF),
    ('Oriya', 0x0B00, 0x0B7F),
    ('Tamil', 0x0B80, 0x0BFF),
    ('Telugu', 0x0C00, 0x0C7F),
    ('Kannada', 0x0C80, 0x0CFF),
    ('Malayalam', 0x0D00, 0x0D7F),
    ('Sinhala', 0x0D80, 0x0DFF),
    ('Thai', 0x0E00, 0x0E7F),
    ('Lao', 0x0E80, 0x0EFF),
    ('Tibetan', 0x0F00, 0x0FFF),
    ('Myanmar', 0x1000, 0x109F),
    ('Georgian', 0x10A0, 0x10FF),
    ('Hangul Jamo', 0x1100, 0x11FF),
    ('Ethiopic', 0x1200, 0x137F),
    ('Cherokee', 0x13A0, 0x13FF),
    ('Canadian Aboriginal Syllabics', 0x1400, 0x167F),
    ('Ogham', 0x1680, 0x169F),
    ('Runic', 0x16A0, 0x16FF),
    ('Tagalog', 0x1700, 0x171F),
    ('Khmer', 0x1780, 0x17FF),
    ('Mongolian', 0x1800, 0x18AF),
    ('Latin Extended Additional', 0x1E00, 0x1EFF),
    ('Greek Extended', 0x1F00, 0x1FFF),
    ('General Punctuation', 0x2000, 0x206F),
    ('Superscripts and Subscripts', 0x2070, 0x209F),
    ('Currency Symbols', 0x20A0, 0x20CF),
    ('Letterlike Symbols', 0x2100, 0x214F),
    ('Number Forms', 0x2150, 0x218F),
    ('Arrows', 0x2190, 0x21FF),
    ('Mathematical Operators', 0x2200, 0x22FF),
    ('Miscellaneous Technical', 0x2300, 0x23FF),
    ('Control Pictures', 0x2400, 0x243F),
    ('Enclosed Alphanumerics', 0x2460, 0x24FF),
    ('Box Drawing', 0x2500, 0x257F),
    ('Block Elements', 0x2580, 0x259F),
    ('Geometric Shapes', 0x25A0, 0x25FF),
    ('Miscellaneous Symbols', 0x2600, 0x26FF),
    ('Dingbats', 0x2700, 0x27BF),
    ('Braille Patterns', 0x2800, 0x28FF),
    ('Supplemental Arrows-B', 0x2900, 0x297F),
    ('Miscellaneous Symbols and Arrows', 0x2B00, 0x2BFF),
    ('Glagolitic', 0x2C00, 0x2C5F),
    ('Coptic', 0x2C80, 0x2CFF),
    ('Tifinagh', 0x2D30, 0x2D7F),
    ('Cyrillic Extended-A', 0x2DE0, 0x2DFF),
    ('Supplemental Punctuation', 0x2E00, 0x2E7F),
    ('CJK Radicals Supplement', 0x2E80, 0x2EFF),
    ('Kangxi Radicals', 0x2F00, 0x2FDF),
    ('CJK Symbols and Punctuation', 0x3000, 0x303F),
    ('Hiragana', 0x3040, 0x309F),
    ('Katakana', 0x30A0, 0x30FF),
    ('Bopomofo', 0x3100, 0x312F),
    ('Hangul Compatibility Jamo', 0x3130, 0x318F),
    ('Kanbun', 0x3190, 0x319F),
    ('Enclosed CJK Letters and Months', 0x3200, 0x32FF),
    ('CJK Compatibility', 0x3300, 0x33FF),
    ('CJK Unified Ideographs Extension A', 0x3400, 0x4DBF),
    ('CJK Unified Ideographs', 0x4E00, 0x9FFF),
    ('Yi Syllables', 0xA000, 0xA48F),
    ('Lisu', 0xA4D0, 0xA4FF),
    ('Vai', 0xA500, 0xA63F),
    ('Cyrillic Extended-B', 0xA640, 0xA69F),
    ('Modifier Tone Letters', 0xA700, 0xA71F),
    ('Latin Extended-D', 0xA720, 0xA7FF),
    ('Phags-pa', 0xA840, 0xA87F),
    ('Devanagari Extended', 0xA8E0, 0xA8FF),
    ('Javanese', 0xA980, 0xA9DF),
    ('Myanmar Extended-A', 0xAA60, 0xAA7F),
    ('Tai Viet', 0xAA80, 0xAADF),
    ('Latin Extended-E', 0xAB30, 0xAB6F),
    ('Meetei Mayek', 0xABC0, 0xABFF),
    ('Hangul Syllables', 0xAC00, 0xD7AF),
    ('Hangul Jamo Extended-B', 0xD7B0, 0xD7FF),
    ('High Surrogates', 0xD800, 0xDB7F),
    ('Low Surrogates', 0xDC00, 0xDFFF),
    ('Private Use Area', 0xE000, 0xF8FF),
    ('CJK Compatibility Ideographs', 0xF900, 0xFAFF),
    ('Alphabetic Presentation Forms', 0xFB00, 0xFB4F),
    ('Arabic Presentation Forms-A', 0xFB50, 0xFDFF),
    ('Variation Selectors', 0xFE00, 0xFE0F),
    ('Vertical Forms', 0xFE10, 0xFE1F),
    ('Combining Half Marks', 0xFE20, 0xFE2F),
    ('CJK Compatibility Forms', 0xFE30, 0xFE4F),
    ('Small Form Variants', 0xFE50, 0xFE6F),
    ('Arabic Presentation Forms-B', 0xFE70, 0xFEFF),
    ('Halfwidth and Fullwidth Forms', 0xFF00, 0xFFEF),
    ('Specials', 0xFFF0, 0xFFFF),
    ('Linear B Syllabary', 0x10000, 0x1007F),
    ('Linear B Ideograms', 0x10080, 0x100FF),
    ('Aegean Numbers', 0x10100, 0x1013F),
    ('Ancient Greek Numbers', 0x10140, 0x1018F),
    ('Old Italic', 0x10300, 0x1032F),
    ('Gothic', 0x10330, 0x1034F),
    ('Deseret', 0x10400, 0x1044F),
    ('Shavian', 0x10450, 0x1047F),
    ('Osmanya', 0x10480, 0x104AF),
    ('Cypriot Syllabary', 0x10800, 0x1083F),
    ('Phoenician', 0x10900, 0x1091F),
    ('Lydian', 0x10920, 0x1093F),
    ('Kharoshthi', 0x10A00, 0x10A5F),
    ('Cuneiform', 0x12000, 0x123FF),
    ('Egyptian Hieroglyphs', 0x13000, 0x1342F),
    ('Anatolian Hieroglyphs', 0x14400, 0x1467F),
    ('Bamum Supplement', 0x16800, 0x16A3F),
    ('Miao', 0x16F00, 0x16F9F),
    ('Emoticons', 0x1F600, 0x1F64F),
    ('Ornamental Dingbats', 0x1F650, 0x1F67F),
    ('Transport and Map Symbols', 0x1F680, 0x1F6FF),
    ('Alchemical Symbols', 0x1F700, 0x1F77F),
    ('Geometric Shapes Extended', 0x1F780, 0x1F7FF),
    ('Supplemental Arrows-C', 0x1F800, 0x1F8FF),
    ('Supplemental Symbols and Pictographs', 0x1F900, 0x1F9FF),
    ('Chess Symbols', 0x1FA00, 0x1FA6F),
    ('Symbols and Pictographs Extended-A', 0x1FA70, 0x1FAFF),
    ('CJK Unified Ideographs Extension B', 0x20000, 0x2A6DF),
    ('CJK Unified Ideographs Extension C', 0x2A700, 0x2B73F),
    ('CJK Unified Ideographs Extension D', 0x2B740, 0x2B81F),
    ('CJK Unified Ideographs Extension E', 0x2B820, 0x2CEAF),
    ('CJK Compatibility Ideographs Supplement', 0x2F800, 0x2FA1F),
    ('Tags', 0xE0000, 0xE007F),
    ('Variation Selectors Supplement', 0xE0100, 0xE01EF),
    ('Supplementary Private Use Area-A', 0xF0000, 0xFFFFF),
    ('Supplementary Private Use Area-B', 0x100000, 0x10FFFF),
]


# ============================================================
#  Приложение
# ============================================================
class UnicodeCatalogue:
    CELL = 64
    FS_CHAR = 18
    FS_BIN = 9
    FS_CODE = 7

    def __init__(self, root):
        self.root = root
        root.title('Unicode Catalogue')
        root.geometry('1200x760')

        self.start_cp = 0x20
        self.end_cp = 0x7E
        self.cps = []
        self.selected_cp = None
        self.cols = 1
        self._resize_job = None
        self._rebuild_id = 0
        self._active_photos = []

        self.theme_dark = False
        self.colors = self._light_colors()
        self.theme_var = tk.StringVar(value='light')

        self._export_id = 0
        self._export_state = None

        self._build_ui()
        self._load_range()

    # ---------- цвета ----------
    def _light_colors(self):
        return {
            'canvas_bg':        'white',
            'cell_bg':          'white',
            'cell_bg_sel':      '#e6ecff',
            'cell_bg_bin':      '#fafafa',
            'cell_bg_bin_sel':  '#e6ecff',
            'cell_outline':     '#e8e8e8',
            'cell_outline_sel': '#3070d0',
            'hex_fg':           '#888',
            'char_fg':          'black',
        }

    def _dark_colors(self):
        return {
            'canvas_bg':        '#1e1e1e',
            'cell_bg':          '#1e1e1e',
            'cell_bg_sel':      '#2a3a5e',
            'cell_bg_bin':      '#252525',
            'cell_bg_bin_sel':  '#2a3a5e',
            'cell_outline':     '#3a3a3a',
            'cell_outline_sel': '#5080d0',
            'hex_fg':           '#666',
            'char_fg':          '#e0e0e0',
        }

    # ---------- меню ----------
    def _build_menubar(self):
        menubar = tk.Menu(self.root)

        # Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='Экспорт в TXT…', accelerator='Ctrl+E',
                              command=lambda: self._export('txt'))
        file_menu.add_command(label='Экспорт в CSV…',
                              command=lambda: self._export('csv'))
        file_menu.add_command(label='Экспорт в HTML…',
                              command=lambda: self._export('html'))
        file_menu.add_separator()
        file_menu.add_command(label='Выход', accelerator='Ctrl+Q',
                              command=self.root.destroy)
        menubar.add_cascade(label='Файл', menu=file_menu)

        # Экспорт
        exp_menu = tk.Menu(menubar, tearoff=0)
        exp_menu.add_command(label='TXT (UTF-8)',
                             command=lambda: self._export('txt'))
        exp_menu.add_command(label='CSV (UTF-8)',
                             command=lambda: self._export('csv'))
        exp_menu.add_command(label='HTML (grid)',
                             command=lambda: self._export('html'))
        exp_menu.add_separator()
        exp_menu.add_command(
            label='Экспорт только выделенного (TXT)',
            command=lambda: self._export('txt', only_selected=True))
        menubar.add_cascade(label='Экспорт', menu=exp_menu)

        # Вид
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_radiobutton(
            label='Светлая тема', value='light', variable=self.theme_var,
            command=lambda: self._set_theme('light'))
        view_menu.add_radiobutton(
            label='Тёмная тема', value='dark', variable=self.theme_var,
            command=lambda: self._set_theme('dark'))
        menubar.add_cascade(label='Вид', menu=view_menu)

        # Справка
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label='О программе',
            command=lambda: messagebox.showinfo(
                'Unicode Catalogue',
                f'Версия Unicode: {ud.unidata_version}\n'
                f'Pillow: {"да" if HAS_PIL else "нет"}\n'
                f'Эмодзи-шрифт: {FONT_EMOJI or "не найден"}'))
        menubar.add_cascade(label='Справка', menu=help_menu)

        self.root.config(menu=menubar)

    # ---------- UI ----------
    def _build_ui(self):
        self._build_menubar()

        # строка 1
        r1 = ttk.Frame(self.root, padding=(6, 4, 6, 0))
        r1.pack(fill='x')
        ttk.Label(r1, text='От:').pack(side='left')
        self.start_entry = ttk.Entry(r1, width=10)
        self.start_entry.insert(0, '0x20')
        self.start_entry.pack(side='left', padx=(2, 8))

        ttk.Label(r1, text='До:').pack(side='left')
        self.end_entry = ttk.Entry(r1, width=10)
        self.end_entry.insert(0, '0x7E')
        self.end_entry.pack(side='left', padx=(2, 8))
        ttk.Button(r1, text='Показать',
                   command=self._load_range).pack(side='left')

        ttk.Separator(r1, orient='vertical').pack(side='left', fill='y',
                                                 padx=8, pady=2)

        ttk.Label(r1, text='Блок:').pack(side='left')
        self.block_var = tk.StringVar()
        self.block_combo = ttk.Combobox(r1, textvariable=self.block_var,
                                        width=34, state='readonly')
        self.block_combo['values'] = [b[0] for b in BLOCKS]
        self.block_combo.pack(side='left', padx=(2, 8))
        self.block_combo.bind('<<ComboboxSelected>>', self._on_block)

        ttk.Separator(r1, orient='vertical').pack(side='left', fill='y',
                                                 padx=8, pady=2)

        ttk.Label(r1, text='Перейти:').pack(side='left')
        self.goto_entry = ttk.Entry(r1, width=10)
        self.goto_entry.pack(side='left', padx=(2, 4))
        self.goto_entry.bind('<Return>', lambda e: self._goto())
        ttk.Button(r1, text='→', width=3,
                   command=self._goto).pack(side='left')

        # строка 2
        r2 = ttk.Frame(self.root, padding=(6, 2, 6, 4))
        r2.pack(fill='x')
        ttk.Label(r2, text='Поиск по имени:').pack(side='left')
        self.search_var = tk.StringVar()
        se = ttk.Entry(r2, textvariable=self.search_var, width=22)
        se.pack(side='left', padx=(2, 4))
        se.bind('<Return>', lambda e: self._rebuild(scroll_to_first=True))
        ttk.Button(r2, text='Найти',
                   command=lambda: self._rebuild(
                       scroll_to_first=True)).pack(side='left')

        ttk.Separator(r2, orient='vertical').pack(side='left', fill='y',
                                                 padx=8, pady=2)

        ttk.Label(r2, text='Категории:').pack(side='left')
        self.cat_vars = {}
        for name in CATEGORY_GROUPS:
            v = tk.BooleanVar(value=False)
            self.cat_vars[name] = v
            ttk.Checkbutton(r2, text=name, variable=v,
                            command=self._rebuild).pack(side='left', padx=1)
        ttk.Button(r2, text='Сброс',
                   command=self._reset_filters).pack(side='left', padx=4)

        ttk.Separator(r2, orient='vertical').pack(side='left', fill='y',
                                                 padx=8, pady=2)

        # кнопка Экспорт
        self.export_btn = ttk.Menubutton(r2, text='Экспорт ▾')
        exp_btn_menu = tk.Menu(self.export_btn, tearoff=0)
        exp_btn_menu.add_command(label='TXT (UTF-8)',
                                 command=lambda: self._export('txt'))
        exp_btn_menu.add_command(label='CSV (UTF-8)',
                                 command=lambda: self._export('csv'))
        exp_btn_menu.add_command(label='HTML (grid)',
                                 command=lambda: self._export('html'))
        self.export_btn['menu'] = exp_btn_menu
        self.export_btn.pack(side='left', padx=(0, 4))

        # кнопка Тема
        self.theme_btn = ttk.Menubutton(r2, text='Тема ▾')
        theme_btn_menu = tk.Menu(self.theme_btn, tearoff=0)
        theme_btn_menu.add_radiobutton(
            label='Светлая тема', value='light', variable=self.theme_var,
            command=lambda: self._set_theme('light'))
        theme_btn_menu.add_radiobutton(
            label='Тёмная тема', value='dark', variable=self.theme_var,
            command=lambda: self._set_theme('dark'))
        self.theme_btn['menu'] = theme_btn_menu
        self.theme_btn.pack(side='right', padx=4)

        # середина
        paned = ttk.PanedWindow(self.root, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=4, pady=2)

        left = ttk.Frame(paned)
        self.canvas = tk.Canvas(left, bg=self.colors['canvas_bg'],
                                highlightthickness=0)
        vsb = ttk.Scrollbar(left, orient='vertical',
                            command=self._on_yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.bind('<Configure>', self._on_configure)
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<Double-Button-1>', self._on_double_click)
        self.canvas.bind('<Button-3>', self._show_menu)
        self.canvas.bind('<Button-2>', self._show_menu)
        self.canvas.bind('<MouseWheel>', self._on_wheel)
        self.canvas.bind('<Button-4>', self._on_wheel)
        self.canvas.bind('<Button-5>', self._on_wheel)
        self.canvas.bind('<Control-c>', self._copy_selected)
        self.canvas.bind('<Control-C>', self._copy_selected)
        self.canvas.bind('<Command-c>', self._copy_selected)
        self.canvas.configure(takefocus=True)
        paned.add(left, weight=3)

        right = ttk.Frame(paned)
        ttk.Label(right, text='Детали', padding=(4, 2)).pack(anchor='w')
        self.details = ttk.Treeview(right, columns=('p', 'v'),
                                    show='headings')
        self.details.heading('p', text='Свойство')
        self.details.heading('v', text='Значение')
        self.details.column('p', width=110, stretch=False)
        self.details.column('v', width=220, stretch=True)
        dvsb = ttk.Scrollbar(right, orient='vertical',
                             command=self.details.yview)
        self.details.configure(yscrollcommand=dvsb.set)
        dvsb.pack(side='right', fill='y')
        self.details.pack(side='left', fill='both', expand=True)
        paned.add(right, weight=1)

        # низ
        bottom = ttk.Frame(self.root)
        bottom.pack(fill='x', side='bottom')
        self.progress = ttk.Progressbar(bottom, mode='determinate',
                                        maximum=100)
        self.status = ttk.Label(bottom, anchor='w', padding=(6, 2))
        self.status.pack(side='left', fill='x', expand=True)

        if not HAS_PIL:
            self.status.config(
                text='Pillow не установлен — проверка глифов и эмодзи '
                     'отключены (pip install pillow)')

        # горячие клавиши
        self.root.bind('<Control-e>', lambda e: self._export('txt'))
        self.root.bind('<Control-q>', lambda e: self.root.destroy())

    # ---------- парсинг ----------
    def _parse(self, s):
        s = s.strip()
        if not s:
            raise ValueError('empty')
        if s.startswith(('0x', '0X')):
            return int(s, 16)
        if s.startswith(('U+', 'u+')):
            return int(s[2:], 16)
        if len(s) == 1:
            return ord(s)
        return int(s, 10)

    # ---------- диапазон ----------
    def _load_range(self):
        try:
            s = self._parse(self.start_entry.get())
            e = self._parse(self.end_entry.get())
        except ValueError:
            self.status.config(text='Ошибка: неверный формат кода')
            return
        if s > e:
            s, e = e, s
        s = max(0, s)
        e = min(0x10FFFF, e)
        self.start_cp, self.end_cp = s, e
        self.selected_cp = None
        self._rebuild()

    def _on_block(self, _event=None):
        name = self.block_var.get()
        for n, s, e in BLOCKS:
            if n == name:
                self.start_entry.delete(0, 'end')
                self.start_entry.insert(0, f'0x{s:04X}')
                self.end_entry.delete(0, 'end')
                self.end_entry.insert(0, f'0x{e:04X}')
                self._load_range()
                return

    def _reset_filters(self):
        self.search_var.set('')
        for v in self.cat_vars.values():
            v.set(False)
        self._rebuild()

    # ---------- отфильтрованный список ----------
    def _allowed_categories(self):
        any_checked = False
        sel = set()
        for name, var in self.cat_vars.items():
            if var.get():
                any_checked = True
                sel |= CATEGORY_GROUPS[name]
        return sel if any_checked else None

    def _rebuild(self, scroll_to_first=False):
        self._rebuild_id += 1
        my_id = self._rebuild_id

        self.cps = []
        allowed = self._allowed_categories()
        search = self.search_var.get().strip().upper()
        total = self.end_cp - self.start_cp + 1
        start = self.start_cp

        self.progress['value'] = 0
        if not self.progress.winfo_ismapped():
            self.progress.pack(fill='x', padx=4, pady=(2, 0),
                               before=self.status)
        self.status.config(text=f'Строим список: {total} кодов…')

        def step(idx):
            if my_id != self._rebuild_id:
                return
            end = min(idx + 3000, self.end_cp + 1)
            for cp in range(idx, end):
                try:
                    ch = chr(cp)
                    cat = ud.category(ch)
                except (ValueError, TypeError):
                    continue
                if allowed is not None and cat not in allowed:
                    continue
                if search and search not in ud.name(ch, ''):
                    continue
                self.cps.append(cp)
            done = end - start
            self.progress['value'] = done / max(1, total) * 100
            if end <= self.end_cp:
                self.root.after(1, step, end)
            else:
                self._on_build_done(scroll_to_first)

        step(start)

    def _on_build_done(self, scroll_to_first=False):
        if self.progress.winfo_ismapped():
            self.progress.pack_forget()
        n = len(self.cps)
        total = self.end_cp - self.start_cp + 1
        self.status.config(
            text=f'U+{self.start_cp:04X}..U+{self.end_cp:04X}: '
                 f'{n} из {total} символов'
                 + (' [фильтр]' if n != total else ''))
        self.canvas.yview_moveto(0)
        if scroll_to_first and n:
            self.selected_cp = self.cps[0]
            self._update_details(self.cps[0])
            self._scroll_to_cp(self.cps[0])
        self._redraw()

    # ---------- скролл ----------
    def _on_yview(self, *args):
        self.canvas.yview(*args)
        self._redraw()

    def _on_wheel(self, event):
        down = event.num == 5 or getattr(event, 'delta', 0) < 0
        self.canvas.yview_scroll(3 if down else -3, 'units')
        self._redraw()
        return 'break'

    def _on_configure(self, _event):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(60, self._redraw)

    def _scroll_to_cp(self, cp):
        idx = bisect.bisect_left(self.cps, cp)
        if idx >= len(self.cps) or self.cps[idx] != cp:
            return False
        row = idx // self.cols
        h = self.canvas.winfo_height() or 1
        total_h = ((len(self.cps) + self.cols - 1) // self.cols) * self.CELL
        target = max(0, row * self.CELL - h // 2)
        self.canvas.yview_moveto(target / max(1, total_h))
        return True

    def _goto(self):
        try:
            cp = self._parse(self.goto_entry.get())
        except ValueError:
            self.status.config(text='Ошибка: некорректный код')
            return
        cp = max(0, min(0x10FFFF, cp))
        if cp < self.start_cp or cp > self.end_cp:
            self.start_entry.delete(0, 'end')
            self.start_entry.insert(0, f'0x{cp:04X}')
            self.end_entry.delete(0, 'end')
            self.end_entry.insert(0, f'0x{cp:04X}')
            self.selected_cp = cp
            self._load_range()
            return
        self.selected_cp = cp
        self._update_details(cp)
        if not self._scroll_to_cp(cp):
            self.status.config(
                text=f'U+{cp:04X} скрыт фильтром — снимите фильтры')
        else:
            self.status.config(text=f'Перешли к U+{cp:04X}')
        self._redraw()

    # ---------- отрисовка ----------
    def _mono(self):
        fams = set(tkfont.families())
        for f in ('Consolas', 'DejaVu Sans Mono', 'Courier New', 'Monaco'):
            if f in fams:
                return (f,)
        return ('TkFixedFont',)

    def _char_font_for(self, cp):
        fams = set(tkfont.families())
        if is_emoji_cp(cp):
            for f in ('Segoe UI Emoji', 'Apple Color Emoji',
                      'Noto Color Emoji', 'Segoe UI Symbol'):
                if f in fams:
                    return (f, self.FS_CHAR)
        if (0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF
                or 0xAC00 <= cp <= 0xD7AF):
            for f in ('MS Gothic', 'Noto Sans CJK JP', 'PingFang SC',
                      'Hiragino Sans', 'Yu Gothic', 'DejaVu Sans'):
                if f in fams:
                    return (f, self.FS_CHAR)
        for f in ('DejaVu Sans', 'Segoe UI', 'Arial', 'Noto Sans'):
            if f in fams:
                return (f, self.FS_CHAR)
        return ('TkDefaultFont', self.FS_CHAR)

    def _redraw(self):
        c = self.canvas
        c.delete('all')
        self._active_photos = []
        if not self.cps:
            c.configure(scrollregion=(0, 0, 1, 1))
            return
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            return

        self.cols = max(1, w // self.CELL)
        rows = (len(self.cps) + self.cols - 1) // self.cols
        c.configure(scrollregion=(0, 0, self.cols * self.CELL,
                                  rows * self.CELL))

        y0 = max(0, c.canvasy(0))
        y1 = y0 + h
        r0 = max(0, int(y0 // self.CELL))
        r1 = min(rows, int(y1 // self.CELL) + 2)
        mono = self._mono()
        col = self.colors

        for r in range(r0, r1):
            for cc in range(self.cols):
                idx = r * self.cols + cc
                if idx >= len(self.cps):
                    break
                cp = self.cps[idx]
                x, y = cc * self.CELL, r * self.CELL
                cx = x + self.CELL / 2
                cy = y + self.CELL / 2
                sel = (cp == self.selected_cp)

                info = cell_info(cp)
                if info['kind'] == 'binary':
                    bg = (col['cell_bg_bin_sel'] if sel
                          else col['cell_bg_bin'])
                else:
                    bg = col['cell_bg_sel'] if sel else col['cell_bg']
                c.create_rectangle(
                    x, y, x + self.CELL, y + self.CELL,
                    outline=(col['cell_outline_sel'] if sel
                             else col['cell_outline']),
                    width=2 if sel else 1, fill=bg)

                if info['kind'] == 'binary':
                    c.create_text(cx, cy - 6, text=info['text'],
                                  font=mono + (self.FS_BIN,),
                                  fill=info['color'], justify='center')
                elif is_emoji_cp(cp) and HAS_IMAGETK:
                    photo = render_emoji(cp, self.CELL - 24)
                    if photo is not None:
                        self._active_photos.append(photo)
                        c.create_image(cx, cy - 8, image=photo)
                    else:
                        c.create_text(cx, cy - 6, text=info['char'],
                                      font=self._char_font_for(cp),
                                      fill=col['char_fg'])
                else:
                    c.create_text(cx, cy - 6, text=info['char'],
                                  font=self._char_font_for(cp),
                                  fill=col['char_fg'])

                c.create_text(cx, y + self.CELL - 8, text=f'{cp:04X}',
                              font=mono + (self.FS_CODE,),
                              fill=col['hex_fg'])

    # ---------- клики ----------
    def _cell_at(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        cc = int(x // self.CELL)
        r = int(y // self.CELL)
        idx = r * self.cols + cc
        if 0 <= idx < len(self.cps):
            return self.cps[idx]
        return None

    def _on_click(self, event):
        self.canvas.focus_set()
        cp = self._cell_at(event)
        if cp is None:
            return
        self.selected_cp = cp
        self._update_details(cp)
        self._redraw()

    def _on_double_click(self, event):
        cp = self._cell_at(event)
        if cp is not None:
            self.selected_cp = cp
            self._update_details(cp)
            self._copy_to_clipboard(chr(cp))
            self._redraw()

    def _show_menu(self, event):
        cp = self._cell_at(event)
        if cp is None:
            return
        self.canvas.focus_set()
        self.selected_cp = cp
        self._update_details(cp)
        self._redraw()

        ch = chr(cp)
        name = ud.name(ch, '—')
        py_escape = f'\\u{cp:04x}' if cp <= 0xFFFF else f'\\U{cp:08x}'
        utf8 = ' '.join(f'{b:02X}' for b in ch.encode('utf-8', 'replace'))
        html = f'&#x{cp:X};'

        m = tk.Menu(self.root, tearoff=0)
        label = ('Копировать символ' if not ch.isprintable()
                 else f'Копировать  «{ch}»')
        m.add_command(label=label,
                      command=lambda: self._copy_to_clipboard(ch))
        m.add_command(label=f'Копировать код  U+{cp:04X}',
                      command=lambda: self._copy_to_clipboard(
                          f'U+{cp:04X}'))
        m.add_command(label=f'Копировать Python  {py_escape}',
                      command=lambda: self._copy_to_clipboard(py_escape))
        m.add_command(label=f'Копировать HTML  {html}',
                      command=lambda: self._copy_to_clipboard(html))
        m.add_command(label='Копировать имя',
                      command=lambda: self._copy_to_clipboard(name))
        m.add_command(label=f'Копировать UTF-8  {utf8}',
                      command=lambda: self._copy_to_clipboard(utf8))
        m.add_separator()
        m.add_command(label=name, state='disabled')
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ---------- буфер ----------
    def _copy_to_clipboard(self, text):
        if not text:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            preview = (text if text.isprintable() and len(text) <= 20
                       else repr(text))
            self.status.config(text=f'Скопировано: {preview}')
        except tk.TclError as e:
            self.status.config(text=f'Не удалось скопировать: {e}')

    def _copy_selected(self, _event=None):
        if self.selected_cp is not None:
            self._copy_to_clipboard(chr(self.selected_cp))
        return 'break'

    # ---------- детали ----------
    def _block_of(self, cp):
        for n, s, e in BLOCKS:
            if s <= cp <= e:
                return n
        return '—'

    def _update_details(self, cp):
        for item in self.details.get_children():
            self.details.delete(item)
        ch = chr(cp)
        cat = ud.category(ch)
        name = ud.name(ch, None) or '—'
        try:
            utf8 = ' '.join(
                f'{b:02X}' for b in ch.encode('utf-8', 'replace'))
        except Exception:
            utf8 = '—'
        try:
            b16 = ch.encode('utf-16-be', 'surrogatepass')
            utf16 = ' '.join(
                f'{int.from_bytes(b16[i:i+2], "big"):04X}'
                for i in range(0, len(b16), 2))
        except Exception:
            utf16 = '—'

        fp = pick_font_path(cp)
        glyph = has_glyph(fp, ch)
        if glyph is True:
            gtxt = f'есть ({os.path.basename(fp)})'
        elif glyph is False:
            gtxt = f'НЕТ — тофу ({os.path.basename(fp)})'
        else:
            gtxt = '?'

        rows = [
            ('Код', f'U+{cp:04X}'),
            ('Десятичное', str(cp)),
            ('Имя', name),
            ('Категория', f'{cat} ({CATEGORY_NAMES.get(cat, cat)})'),
            ('Блок', self._block_of(cp)),
            ('Bidi', ud.bidirectional(ch) or '—'),
            ('Combining', str(ud.combining(ch))),
            ('East Asian', ud.east_asian_width(ch)),
            ('UTF-8', utf8),
            ('UTF-16', utf16),
            ('Python', f'\\u{cp:04x}' if cp <= 0xFFFF
                       else f'\\U{cp:08x}'),
            ('HTML', f'&#x{cp:X};'),
            ('Глиф', gtxt),
        ]
        for k, v in rows:
            self.details.insert('', 'end', values=(k, v))

    # ---------- тема ----------
    def _set_theme(self, mode):
        self.theme_dark = (mode == 'dark')
        self.theme_var.set(mode)
        self.colors = (self._dark_colors() if self.theme_dark
                       else self._light_colors())
        self._apply_ttk_theme()
        self.canvas.config(bg=self.colors['canvas_bg'])
        self._redraw()

    def _apply_ttk_theme(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        if self.theme_dark:
            bg, fg, entry_bg = '#2b2b2b', '#e0e0e0', '#3a3a3a'
            sel_bg = '#2a3a5e'
            self.root.configure(bg=bg)
            style.configure('.', background=bg, foreground=fg)
            style.configure('TFrame', background=bg)
            style.configure('TLabel', background=bg, foreground=fg)
            style.configure('TButton', background='#3a3a3a',
                            foreground=fg)
            style.map('TButton', background=[('active', '#4a4a4a')])
            style.configure('TMenubutton', background='#3a3a3a',
                            foreground=fg)
            style.map('TMenubutton', background=[('active', '#4a4a4a')])
            style.configure('TEntry', fieldbackground=entry_bg,
                            foreground=fg, insertcolor=fg)
            style.configure('TCombobox', fieldbackground=entry_bg,
                            foreground=fg, background='#3a3a3a',
                            arrowcolor=fg)
            style.map('TCombobox',
                      fieldbackground=[('readonly', entry_bg)],
                      foreground=[('readonly', fg)])
            style.configure('TCheckbutton', background=bg, foreground=fg)
            style.map('TCheckbutton', background=[('active', bg)])
            style.configure('Treeview', background='#252525',
                            fieldbackground='#252525', foreground=fg)
            style.configure('Treeview.Heading',
                            background='#3a3a3a', foreground=fg)
            style.map('Treeview',
                      background=[('selected', sel_bg)],
                      foreground=[('selected', '#ffffff')])
            style.configure('TProgressbar', background='#5080d0')
        else:
            self.root.configure(bg='#f0f0f0')
            for name in ('TFrame', 'TLabel', 'TButton', 'TMenubutton',
                         'TEntry', 'TCombobox', 'TCheckbutton',
                         'Treeview', 'Treeview.Heading', 'TProgressbar'):
                try:
                    style.configure(name)
                except tk.TclError:
                    pass

    # ---------- экспорт ----------
    def _export(self, fmt, only_selected=False):
        if only_selected:
            if self.selected_cp is None:
                messagebox.showinfo('Экспорт',
                                    'Сначала выделите символ.')
                return
            cps = [self.selected_cp]
        else:
            cps = self.cps
            if not cps:
                messagebox.showinfo(
                    'Экспорт',
                    'Нечего экспортировать — диапазон пуст.')
                return

        ext = {'txt': '.txt', 'csv': '.csv', 'html': '.html'}[fmt]
        ftypes = {'txt': [('Text', '*.txt')],
                  'csv': [('CSV', '*.csv')],
                  'html': [('HTML', '*.html')]}[fmt] + [
                      ('Все файлы', '*.*')]
        path = filedialog.asksaveasfilename(
            title='Экспорт символов',
            defaultextension=ext,
            filetypes=ftypes,
            initialfile=f'unicode_{self.start_cp:04X}-{self.end_cp:04X}{ext}')
        if not path:
            return

        self._export_id += 1
        my_id = self._export_id

        try:
            if fmt == 'txt':
                f = open(path, 'w', encoding='utf-8')
                self._export_state = {
                    'f': f, 'fmt': fmt, 'id': my_id, 'path': path,
                    'idx': 0, 'cps': cps}
                self._export_write_txt()
            elif fmt == 'csv':
                f = open(path, 'w', encoding='utf-8', newline='')
                w = csv.writer(f)
                w.writerow(['hex', 'dec', 'char', 'name',
                            'category', 'utf8'])
                self._export_state = {
                    'f': f, 'w': w, 'fmt': fmt, 'id': my_id, 'path': path,
                    'idx': 0, 'cps': cps}
                self._export_write_csv()
            elif fmt == 'html':
                f = open(path, 'w', encoding='utf-8')
                f.write(self._html_header())
                self._export_state = {
                    'f': f, 'fmt': fmt, 'id': my_id, 'path': path,
                    'idx': 0, 'cps': cps}
                self._export_write_html()
        except OSError as e:
            self.status.config(text=f'Ошибка записи: {e}')
            return

        self.progress['value'] = 0
        if not self.progress.winfo_ismapped():
            self.progress.pack(fill='x', padx=4, pady=(2, 0),
                               before=self.status)
        self.status.config(text=f'Экспорт → {path}')

    def _export_chunk(self):
        st = self._export_state
        start = st['idx']
        end = min(start + 5000, len(st['cps']))
        st['idx'] = end
        return start, end

    def _export_finish(self):
        st = self._export_state
        try:
            if st['fmt'] == 'html':
                st['f'].write(self._html_footer())
        finally:
            st['f'].close()
        if self.progress.winfo_ismapped():
            self.progress.pack_forget()
        self.status.config(
            text=f'Готово: {st["path"]} ({len(st["cps"])} символов)')
        self._export_state = None

    def _export_write_txt(self):
        st = self._export_state
        if st['id'] != self._export_id:
            st['f'].close()
            return
        start, end = self._export_chunk()
        for cp in st['cps'][start:end]:
            ch = chr(cp)
            name = ud.name(ch, '')
            st['f'].write(f'U+{cp:04X}\t{ch}\t{name}\n')
        self.progress['value'] = st['idx'] / len(st['cps']) * 100
        if st['idx'] < len(st['cps']):
            self.root.after(1, self._export_write_txt)
        else:
            self._export_finish()

    def _export_write_csv(self):
        st = self._export_state
        if st['id'] != self._export_id:
            st['f'].close()
            return
        start, end = self._export_chunk()
        for cp in st['cps'][start:end]:
            ch = chr(cp)
            try:
                name = ud.name(ch)
            except ValueError:
                name = ''
            cat = ud.category(ch)
            try:
                utf8 = ch.encode('utf-8').hex(' ')
            except Exception:
                utf8 = ''
            st['w'].writerow([f'U+{cp:04X}', cp, ch, name, cat, utf8])
        self.progress['value'] = st['idx'] / len(st['cps']) * 100
        if st['idx'] < len(st['cps']):
            self.root.after(1, self._export_write_csv)
        else:
            self._export_finish()

    def _export_write_html(self):
        st = self._export_state
        if st['id'] != self._export_id:
            st['f'].close()
            return
        start, end = self._export_chunk()
        for cp in st['cps'][start:end]:
            ch = chr(cp)
            cat = ud.category(ch)
            try:
                name = ud.name(ch)
            except ValueError:
                name = '—'
            if cat in INVISIBLE:
                display = (f'<span class="bin">'
                           f'{binary_for(cp).replace(chr(10), "<br>")}'
                           f'</span>')
                cell_cls = 'cell bin-cell'
            else:
                display = (f'<span class="glyph">'
                           f'{html_module.escape(ch)}</span>')
                cell_cls = 'cell'
            st['f'].write(
                f'<div class="{cell_cls}" '
                f'title="{html_module.escape(name)}">'
                f'{display}'
                f'<span class="code">{cp:04X}</span>'
                f'<span class="name">{html_module.escape(name)}</span>'
                f'</div>\n')
        self.progress['value'] = st['idx'] / len(st['cps']) * 100
        if st['idx'] < len(st['cps']):
            self.root.after(1, self._export_write_html)
        else:
            self._export_finish()

    def _html_header(self):
        return f'''<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<title>Unicode Catalogue — U+{self.start_cp:04X}..U+{self.end_cp:04X}</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; background: #fafafa;
         color: #222; margin: 16px; }}
  h1 {{ font-size: 18px; }}
  .grid {{ display: grid;
           grid-template-columns: repeat(auto-fill, minmax(84px, 1fr));
           gap: 4px; }}
  .cell {{ background: white; border: 1px solid #e8e8e8;
           border-radius: 4px; padding: 4px; text-align: center;
           overflow: hidden; }}
  .bin-cell {{ background: #fafafa; }}
  .glyph {{ font-size: 32px; display: block; line-height: 1.2; }}
  .bin {{ font-family: Consolas, monospace; font-size: 8px;
          color: #c06000; display: block; white-space: pre; }}
  .code {{ font-family: Consolas, monospace; font-size: 10px;
           color: #888; display: block; }}
  .name {{ font-size: 8px; color: #aaa; display: block;
           overflow: hidden; text-overflow: ellipsis;
           white-space: nowrap; }}
</style></head><body>
<h1>Unicode Catalogue — U+{self.start_cp:04X}..U+{self.end_cp:04X}
 ({len(self.cps)} символов)</h1>
<div class="grid">
'''

    def _html_footer(self):
        return '</div></body></html>\n'


# ============================================================
if __name__ == '__main__':
    root = tk.Tk()
    try:
        ttk.Style().theme_use('clam')
    except tk.TclError:
        pass
    if not HAS_PIL:
        print('Pillow не установлен — проверка глифов и эмодзи отключены.')
        print('Установите: pip install pillow')
    app = UnicodeCatalogue(root)
    root.mainloop()