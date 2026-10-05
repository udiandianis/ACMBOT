import unicodedata
from functools import lru_cache
from PIL import ImageFont
from fontTools.ttLib import TTFont
from .paths import RESOURCE_DIRECTORY

FONT_DIRECTORY = RESOURCE_DIRECTORY / 'fonts'


@lru_cache(maxsize=1)
def font_catalog():
    """读取项目字体及字形覆盖，优先使用黑体，并缓存结果。"""
    paths = sorted(FONT_DIRECTORY.glob('*.ttf'), key=lambda path: (path.name != 'SimHei.ttf', path.name))
    if not paths:
        raise FileNotFoundError('fonts 文件夹中没有可用字体')
    catalog = []
    for path in paths:
        with TTFont(path) as font:
            catalog.append((path, frozenset(font.getBestCmap())))
    return tuple(catalog)


@lru_cache(maxsize=32)
def load_font(path, size):
    """按路径和字号加载字体，复用已加载的字体对象。"""
    return ImageFont.truetype(str(path), size)


def font_for_text(text, size):
    """选择能完整显示文本的字体；没有单一字体覆盖时返回 None。"""
    characters = {ord(character) for character in text}
    for path, coverage in font_catalog():
        if characters <= coverage:
            return load_font(path, size)
    return None


def draw_text(drawing, position, text, size, fill='black'):
    """完整文本优先使用同一字体，否则按字符簇回退并对齐基线。"""
    font = font_for_text(text, size)
    if font is not None:
        drawing.text(position, text, font=font, fill=fill)
        return
    clusters = []
    for character in text:
        if clusters and (unicodedata.category(character).startswith('M') or character == '\u200d' or clusters[-1].endswith('\u200d')):
            clusters[-1] += character
        else:
            clusters.append(character)
    runs = []
    for cluster in clusters:
        font = font_for_text(cluster, size) or load_font(font_catalog()[0][0], size)
        if runs and runs[-1][0] is font:
            runs[-1] = (font, runs[-1][1] + cluster)
        else:
            runs.append((font, cluster))
    baseline = position[1] + max((font.getmetrics()[0] for font, _ in runs), default=0)
    left = position[0]
    for font, run in runs:
        drawing.text((left, baseline), run, font=font, fill=fill, anchor='ls')
        left += drawing.textlength(run, font=font)


@lru_cache(maxsize=1)
def configure_matplotlib():
    """注册项目字体，启用表格文字的多字体回退。"""
    from matplotlib import font_manager, rcParams
    families = []
    for path, _ in font_catalog():
        font_manager.fontManager.addfont(str(path))
        family = font_manager.FontProperties(fname=str(path)).get_name()
        if family not in families:
            families.append(family)
    rcParams['font.family'] = families
    rcParams['axes.unicode_minus'] = False
