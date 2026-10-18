# ==============================================================================
# RIPE 93 poster (A1 portrait, 594 x 841 mm) - one layout, two outputs:
#   results/poster/ripe93_poster.pptx       editable in PowerPoint (export to PDF to print)
#   results/poster/ripe93_poster_preview.png preview drawn with matplotlib (to check the layout
#                                            on the server; PowerPoint wraps text slightly differently)
#
# Numbers and "features that fired" are read from the E3 results, never typed by hand.
# Texts in [square brackets] are placeholders to fill in (authors, logos, contact, reference).
#
# Run from the repository root (after scripts/poster/figures.py):
#   python scripts/poster/build_poster.py
# ==============================================================================

import argparse
import os
import sys
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Mm, Pt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'e3'))
import threshold_rule as T

# ---------------- editable header ----------------
TITLE = 'Worms, leaks and blackouts: would your route collector have raised the alarm?'
SUBTITLE = ('Label-free BGP alarms from one-second matrix profiles, tested on 6 incidents (2001-2017) '
            'at RIPE RIS RRC04  ·  work in progress')
AUTHORS = 'Shadi Motaali, Óscar Cuevas Martínez, [co-authors]'
AFFILIATION = 'Universidad Autónoma de Madrid (UAM), Spain   [check]'
CONTACT = None            # e.g. 'mailto:name@example.org' or a URL; None = placeholder box instead of a QR code
REFERENCE = ('The one-second, multi-scale Pan Matrix Profile representation behind this poster, validated on the same '
             'six incidents, will be presented at CNSM 2026, the 22nd International Conference on Network and Service '
             'Management, Alcalá de Henares (Madrid), Spain, 26-30 October 2026.  Data: RIPE RIS RRC04.')

PAGE_W, PAGE_H = 594, 841          # mm, A1 portrait
NAVY, BLUE, LIGHT, WHITE, DARK, ORANGE = '0B3C5D', '1D6FA3', 'EAF2F8', 'FFFFFF', '222222', 'E07B00'
FONT = 'Arial'
STATIC, DYNAMIC = ('smooth10', 3), ('dynamic4', 2)
EVENT_ROWS = [  # event key, label, type
    ('slammer', 'Slammer 2003', 'worm'),
    ('codered', 'Code Red I 2001', 'worm'),
    ('moscow_blackout', 'Moscow 2005', 'power outage'),
    ('telekom_malaysia', 'Telekom MY 2015', 'route leak'),
    ('nimda', 'Nimda 2001', 'worm'),
    ('wannacrypt', 'WannaCrypt 2017', 'ransomware'),
]


def p(text, size, bold=False, color=DARK, bullet=False, space=0.35):
    """One paragraph: text, size in pt, bold, colour, bullet, space after (in lines)."""
    return {'text': text, 'size': size, 'bold': bold, 'color': color, 'bullet': bullet, 'space': space}


PLAIN = {  # feature -> what an operator would call it
    'rare_ases_avg': 'rare ASes in paths', 'number_rare_ases': 'rare ASes in paths',
    'withdrawals': 'withdrawals', 'imp_wd': 'implicit withdrawals', 'imp_wd_spath': 'implicit withdrawals',
    'imp_wd_dpath': 'implicit withdrawals', 'announcements': 'announcements', 'nlri_ann': 'announcements',
    'origin_0': 'announcements', 'origin_2': 'announcements', 'origin_changes': 'origin changes',
    'as_path_max': 'long AS paths', 'unique_as_path_max': 'long AS paths', 'flaps': 'route flaps',
    'dups': 'duplicate updates', 'nadas': 'path changes',
}


def plain(feature):
    return 'AS-path changes' if feature.startswith('edit_distance') else PLAIN.get(feature, feature)


def clock(start_hhmm, delay):
    """Clock time of the first alarm, e.g. ('05:31', 7) -> '05:38 (+7 min)'."""
    if pd.isna(delay):
        return 'no alarm'
    t = T.minute_index(start_hhmm) + int(delay)
    return f'{t // 60:02d}:{t % 60:02d} (+{int(delay)} min)'


def numbers(e3):
    """Delays, signatures and false-alarm rates from the E3 results."""
    s = pd.read_csv(os.path.join(e3, 'summary.csv'))
    avg = pd.read_csv(os.path.join(e3, 'summary_average.csv'))
    tops = pd.read_csv(os.path.join(e3, 'top_features.csv'))
    out = {}
    for ev, _, _ in EVENT_ROWS:
        row = {}
        start = T.EVENTS[ev][2]
        row['start'] = start
        for name, (rule, k) in (('static', STATIC), ('dynamic', DYNAMIC)):
            r = s[(s.rule == rule) & (s.k == k) & (s.event == ev)].iloc[0]
            row[name] = clock(start, r.delay_min)
        t = tops[(tops.rule == STATIC[0]) & (tops.event == ev)]
        strong = t[(t.firing_in_window >= 0.1) & (t.firing_in_window >= 2 * t.firing_outside)]
        names = [plain(f) for f in (strong if len(strong) else t.head(1)).feature.head(3)]
        row['fired'] = ', '.join(dict.fromkeys(names))          # plain words, no repeats
        out[ev] = row
    fa = {name: avg[(avg.rule == rule) & (avg.k == k)].iloc[0] for name, (rule, k) in
          (('static', STATIC), ('dynamic', DYNAMIC))}
    dyn = s[(s.rule == DYNAMIC[0]) & (s.k == DYNAMIC[1])]
    out['_n_fast'] = int((dyn.delay_min <= 30).sum())
    out['_fa'] = fa
    return out


def layout(figs, e3):
    """List of elements; coordinates in mm from the top-left corner."""
    n = numbers(e3)
    fa_s, fa_d = n['_fa']['static'], n['_fa']['dynamic']
    els = []
    add = els.append

    # ---------- header ----------
    add({'kind': 'rect', 'x': 0, 'y': 0, 'w': PAGE_W, 'h': 118, 'fill': NAVY})
    add({'kind': 'text', 'x': 18, 'y': 10, 'w': 430, 'h': 56, 'paras': [p(TITLE, 54, True, WHITE, space=0)]})
    add({'kind': 'text', 'x': 18, 'y': 60, 'w': 430, 'h': 22, 'paras': [p(SUBTITLE, 24, False, 'CFE3F2', space=0)]})
    add({'kind': 'text', 'x': 18, 'y': 86, 'w': 430, 'h': 12, 'paras': [p(AUTHORS, 27, True, WHITE, space=0)]})
    add({'kind': 'text', 'x': 18, 'y': 100, 'w': 430, 'h': 11, 'paras': [p(AFFILIATION, 22, False, 'CFE3F2', space=0)]})
    add({'kind': 'rect', 'x': 458, 'y': 14, 'w': 118, 'h': 90, 'fill': WHITE})
    add({'kind': 'text', 'x': 462, 'y': 50, 'w': 110, 'h': 20,
         'paras': [p('[UAM logo]   [RIPE NCC / RACI logo]', 20, False, '888888', space=0)]})

    def box(x, y, w, h, title):
        add({'kind': 'rect', 'x': x, 'y': y, 'w': w, 'h': h, 'fill': LIGHT})
        add({'kind': 'rect', 'x': x, 'y': y, 'w': w, 'h': 13, 'fill': BLUE})
        add({'kind': 'text', 'x': x + 6, 'y': y + 1.5, 'w': w - 12, 'h': 12, 'paras': [p(title, 27, True, WHITE, space=0)]})

    L, R, COLW = 18, 303, 273

    # ---------- row 1: question + method ----------
    y = 128
    box(L, y, COLW, 116, 'The question')
    add({'kind': 'text', 'x': L + 7, 'y': y + 18, 'w': COLW - 14, 'h': 96, 'paras': [
        p('Worms, route leaks and outages change BGP within seconds, but most monitoring looks at '
          'counters per minute or per hour.', 22),
        p('Can one public collector feed raise an alarm automatically, without training labels, '
          'minutes after an incident starts?', 22, True, NAVY),
        p('Data: RIPE RIS RRC04 update dumps for 6 historical incidents, each with a normal day '
          'one week earlier. Incident times from published reports.', 22),
    ]})
    box(R, y, COLW, 116, 'How it works')
    # four steps as a flow: box -> arrow -> box ...
    steps = [('Listen', 'every BGP update RRC04 hears, second by second'),
             ('Measure', '27 vital signs per second: churn, paths, rare ASes'),
             ('Compare', 'has today seen this traffic before? No twin = unusual'),
             ('Alert', 'several vital signs out of range for 2 minutes')]
    bw, gap, bx, by, bh = 55, 11, R + 6, y + 19, 70
    for i, (head, detail) in enumerate(steps):
        x = bx + i * (bw + gap)
        add({'kind': 'rect', 'x': x, 'y': by, 'w': bw, 'h': bh, 'fill': WHITE})
        add({'kind': 'rect', 'x': x, 'y': by, 'w': bw, 'h': 2.5, 'fill': ORANGE if i == 3 else BLUE})
        add({'kind': 'text', 'x': x + 3, 'y': by + 5, 'w': bw - 6, 'h': bh - 8, 'paras': [
            p(f'{i + 1}  {head}', 22, True, NAVY, space=0.3),
            p(detail, 17, space=0)]})
        if i < len(steps) - 1:
            add({'kind': 'arrow', 'x': x + bw + 1.5, 'y': by + bh / 2 - 4, 'w': gap - 3, 'h': 8, 'fill': BLUE})
    add({'kind': 'text', 'x': R + 7, 'y': by + bh + 4, 'w': COLW - 14, 'h': 20, 'paras': [
        p('Shape only, scaled by √m; each value is stamped at the end of its window, so an alarm only uses '
          'data that already exists.', 15, False, '444444', space=0)]})

    # ---------- row 2: what the method sees ----------
    y = 252
    box(L, y, PAGE_W - 2 * L, 222, 'What the Slammer worm did to the RRC04 feed (25 Jan 2003)')
    add({'kind': 'image', 'x': L + 5, 'y': y + 17, 'w': 330, 'path': os.path.join(figs, 'fig_slammer_pmp.png')})
    add({'kind': 'image', 'x': 374, 'y': y + 16, 'w': 190, 'path': os.path.join(figs, 'fig_slammer_3d.png')})
    add({'kind': 'text', 'x': L + 7, 'y': y + 204, 'w': 330, 'h': 17, 'paras': [
        p('Each column is one moment of the day.  Bright: this traffic looks like nothing else today.  '
          'Dark: we have seen it many times.', 16, False, DARK, space=0)]})
    add({'kind': 'text', 'x': 370, 'y': y + 179, 'w': 201, 'h': 42, 'paras': [
        p('How to read the 3D', 17, True, NAVY, space=0.15),
        p('Height = how different this moment is from the rest of the day', 15, bullet=True, space=0.05),
        p('Normal, varied traffic → high, rough surface', 15, bullet=True, space=0.05),
        p('05:31 worm: the same pattern repeats → deep trench for hours', 15, bullet=True, space=0.05),
        p('Alarm = the surface leaves its usual height', 15, True, ORANGE, bullet=True, space=0)]})

    # ---------- row 3: first automated alarms ----------
    y = 482
    box(L, y, PAGE_W - 2 * L, 220, 'First automated alarms on 6 real incidents')
    add({'kind': 'image', 'x': L + 5, 'y': y + 17, 'w': 322, 'path': os.path.join(figs, 'fig_alarms.png')})
    add({'kind': 'text', 'x': L + 6, 'y': y + 177, 'w': 326, 'h': 42, 'paras': [
        p('How the alarm decides (no labels, traffic only)', 16, True, NAVY, space=0.15),
        p('Static (red): normal range = 1st-99th percentile of each feature on the normal day; '
          'alarm if ≥ 3 features are outside for 2 min', 15, bullet=True, space=0.1),
        p('Dynamic (purple): normal range = median ± 4 robust σ of the same day\'s last 2 hours; '
          'alarm if ≥ 2 features are outside for 2 min', 15, bullet=True, space=0.1),
        p('Preliminary: one normal day per incident; settings chosen on these 6 incidents', 15, False, ORANGE,
          bullet=True, space=0),
    ]})
    rows = [['What happened', 'Began\n(UTC)', 'First alarm (UTC)\ndynamic / static', 'What the alarm\npointed at']]
    for ev, label, kind in EVENT_ROWS:
        r = n[ev]
        star = '*' if ev == 'moscow_blackout' else ''
        rows.append([f'{label}\n{kind}', r['start'], f'{r["dynamic"]}{star}\n{r["static"]}{star}', r['fired']])
    add({'kind': 'table', 'x': 356, 'y': y + 18, 'w': 216, 'col_w': [50, 20, 57, 89], 'row_h': 17.5,
         'rows': rows, 'size': 15})
    # Moscow: the published window starts at 03:00, but the update storm reached RRC04 only at 04:30
    # (announcements per 10 min: ~2,000 until 04:20, then 117,939 in 04:30-04:40; checked on 2026-10-18)
    add({'kind': 'text', 'x': 357, 'y': y + 141.5, 'w': 214, 'h': 6, 'paras': [
        p('* Moscow: the update storm reached RRC04 at 04:30, the alarm came 16 min later',
          13, False, '555555', space=0)]})
    add({'kind': 'text', 'x': 356, 'y': y + 150, 'w': 216, 'h': 68, 'paras': [
        p(f'All 6 incidents raise an alarm; with the dynamic rule {n["_n_fast"]} of 6 within 30 minutes.',
          17, True, NAVY, bullet=True, space=0.3),
        p('The features that fire hint at what happened: Slammer and the Moscow outage moved rare ASes and '
          'withdrawals; the Telekom leak moved rare ASes and origins.', 17, bullet=True, space=0.3),
        p(f'But {fa_s.mean_false_alarm_pct_before:.0f}-{fa_d.mean_false_alarm_pct_before:.0f} % of normal minutes '
          'also alarm: limits from one normal day do not carry over to the next day.', 17, True, ORANGE,
          bullet=True, space=0),
    ]})

    # ---------- row 4: lessons, next steps, asks ----------
    y = 708
    w3 = (PAGE_W - 2 * L - 2 * 9) / 3
    xs = [L, L + w3 + 9, L + 2 * (w3 + 9)]
    wide = 2 * w3 + 9                                   # one block over the first two columns
    box(xs[0], y, wide, 115, 'Today on RIS data, tomorrow in your NOC')
    half = (wide - 16) / 2
    add({'kind': 'text', 'x': xs[0] + 5, 'y': y + 16, 'w': half, 'h': 97, 'paras': [
        p('Today', 22, True, ORANGE, space=0.2),
        p('Public RIPE RIS data only: nothing from your routers', 19, bullet=True, space=0.25),
        p('No labelled incidents or training needed', 19, bullet=True, space=0.25),
        p('Each alarm says what moved: rare ASes, withdrawals, announcements', 19, bullet=True, space=0.25),
        p('Worms, a route leak and a blackout all raised alarms', 19, True, NAVY, bullet=True, space=0),
    ]})
    add({'kind': 'rect', 'x': xs[0] + 8 + half, 'y': y + 18, 'w': 0.6, 'h': 90, 'fill': 'B8CCDB'})
    add({'kind': 'text', 'x': xs[0] + 11 + half, 'y': y + 16, 'w': half - 2, 'h': 97, 'paras': [
        p('Next', 22, True, ORANGE, space=0.2),
        p('Fewer false alarms: learn "normal" from many days, per time of day', 19, True, NAVY, bullet=True,
          space=0.25),
        p('More collectors and recent incidents', 19, bullet=True, space=0.25),
        p('Per-peer view: which neighbour is shouting?', 19, bullet=True, space=0.25),
        p('Live feeds: RIS Live or your own BMP', 19, bullet=True, space=0),
    ]})
    box(xs[2], y, w3, 115, 'We need you')
    add({'kind': 'text', 'x': xs[2] + 5, 'y': y + 16, 'w': w3 - 52, 'h': 97, 'paras': [
        p('Seen a BGP incident? Tell us when and which prefixes / ASes: it becomes test data',
          19, bullet=True, space=0.25),
        p('What false-alarm rate could your NOC live with?', 19, bullet=True, space=0.25),
        p('Would you try it on your own BMP feed?', 19, bullet=True, space=0.25),
        p('Talk to me here, or scan the code', 20, True, NAVY, space=0),
    ]})
    if CONTACT:
        add({'kind': 'qr', 'x': xs[2] + w3 - 45, 'y': y + 60, 'w': 40, 'data': CONTACT})
    else:
        add({'kind': 'rect', 'x': xs[2] + w3 - 45, 'y': y + 60, 'w': 40, 'h': 40, 'fill': WHITE})
        add({'kind': 'text', 'x': xs[2] + w3 - 43, 'y': y + 76, 'w': 36, 'h': 8,
             'paras': [p('[QR code]', 14, False, '888888', space=0)]})

    # ---------- footer ----------
    add({'kind': 'text', 'x': L, 'y': 826, 'w': PAGE_W - 2 * L, 'h': 13,
         'paras': [p(REFERENCE, 13, False, '555555', space=0)]})
    return els


# ====================== PowerPoint ======================
def rgb(h):
    return RGBColor.from_string(h)


def to_pptx(els, path, tmp_dir):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Mm(PAGE_W), Mm(PAGE_H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for e in els:
        if e['kind'] == 'rect':
            s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Mm(e['x']), Mm(e['y']), Mm(e['w']), Mm(e['h']))
            s.fill.solid()
            s.fill.fore_color.rgb = rgb(e['fill'])
            s.line.fill.background()
            s.shadow.inherit = False
        elif e['kind'] == 'arrow':
            s = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Mm(e['x']), Mm(e['y']), Mm(e['w']), Mm(e['h']))
            s.fill.solid()
            s.fill.fore_color.rgb = rgb(e['fill'])
            s.line.fill.background()
            s.shadow.inherit = False
        elif e['kind'] == 'text':
            tb = slide.shapes.add_textbox(Mm(e['x']), Mm(e['y']), Mm(e['w']), Mm(e['h']))
            tf = tb.text_frame
            tf.word_wrap = True
            tf.auto_size = MSO_AUTO_SIZE.NONE
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            for i, para in enumerate(e['paras']):
                pa = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                run = pa.add_run()
                run.text = ('•  ' if para['bullet'] else '') + para['text']
                run.font.size = Pt(para['size'])
                run.font.bold = para['bold']
                run.font.name = FONT
                run.font.color.rgb = rgb(para['color'])
                pa.space_after = Pt(para['size'] * para['space'] * 1.2)
        elif e['kind'] in ('image', 'qr'):
            img_path = e['path'] if e['kind'] == 'image' else qr_png(e['data'], tmp_dir)
            iw, ih = Image.open(img_path).size
            h = e['w'] * ih / iw
            slide.shapes.add_picture(img_path, Mm(e['x']), Mm(e['y']), Mm(e['w']), Mm(h))
        elif e['kind'] == 'table':
            rows, cols = len(e['rows']), len(e['col_w'])
            shape = slide.shapes.add_table(rows, cols, Mm(e['x']), Mm(e['y']), Mm(e['w']), Mm(e['row_h'] * rows))
            table = shape.table
            for c, cw in enumerate(e['col_w']):
                table.columns[c].width = Mm(cw)
            for r in range(rows):
                table.rows[r].height = Mm(e['row_h'])
                for c in range(cols):
                    cell = table.cell(r, c)
                    cell.margin_left = cell.margin_right = Mm(1.5)
                    cell.margin_top = cell.margin_bottom = Mm(0.8)
                    cell.text = e['rows'][r][c].replace('​', '')
                    for pa in cell.text_frame.paragraphs:
                        for run in pa.runs:
                            run.font.size = Pt(e['size'])
                            run.font.name = FONT
                            run.font.bold = (r == 0)
                            run.font.color.rgb = rgb(WHITE if r == 0 else DARK)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = rgb(BLUE if r == 0 else (WHITE if r % 2 else 'F4F8FB'))
    prs.save(path)


def qr_png(data, tmp_dir):
    import qrcode
    path = os.path.join(tmp_dir, 'qr.png')
    qrcode.make(data).save(path)
    return path


# ====================== preview (matplotlib) ======================
PT = 0.3528          # mm per point
CHAR = 0.55          # average character width in em (DejaVu Sans; Arial is a little narrower)


def wrap(text, size, width_mm):
    chars = max(5, int(width_mm / (size * PT * CHAR)))
    lines = []
    for part in text.split('\n'):
        lines += textwrap.wrap(part, chars) or ['']
    return lines


def to_preview(els, path, tmp_dir):
    fig = plt.figure(figsize=(PAGE_W / 25.4, PAGE_H / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PAGE_W)
    ax.set_ylim(PAGE_H, 0)
    ax.axis('off')
    warnings = []
    for e in els:
        if e['kind'] == 'rect':
            ax.add_patch(plt.Rectangle((e['x'], e['y']), e['w'], e['h'], color='#' + e['fill'], linewidth=0, zorder=1))
        elif e['kind'] == 'arrow':
            x0, y0, w, h = e['x'], e['y'], e['w'], e['h']
            head = w * 0.45
            pts = [(x0, y0 + h * 0.3), (x0 + w - head, y0 + h * 0.3), (x0 + w - head, y0), (x0 + w, y0 + h / 2),
                   (x0 + w - head, y0 + h), (x0 + w - head, y0 + h * 0.7), (x0, y0 + h * 0.7)]
            ax.add_patch(plt.Polygon(pts, closed=True, color='#' + e['fill'], linewidth=0, zorder=2))
        elif e['kind'] == 'text':
            y = e['y']
            for para in e['paras']:
                lines = wrap(('•  ' if para['bullet'] else '') + para['text'], para['size'], e['w'])
                for line in lines:
                    ax.text(e['x'], y, line, fontsize=para['size'], fontweight='bold' if para['bold'] else 'normal',
                            color='#' + para['color'], va='top', ha='left', zorder=3)
                    y += para['size'] * PT * 1.2
                y += para['size'] * PT * 1.2 * para['space']
            if y > e['y'] + e['h'] + 1:
                warnings.append(f'text box at ({e["x"]:.0f}, {e["y"]:.0f}) overflows by {y - e["y"] - e["h"]:.0f} mm: '
                                f'"{e["paras"][0]["text"][:40]}..."')
        elif e['kind'] in ('image', 'qr'):
            img_path = e['path'] if e['kind'] == 'image' else qr_png(e['data'], tmp_dir)
            img = Image.open(img_path)
            h = e['w'] * img.size[1] / img.size[0]
            print(f'image {os.path.basename(img_path)}: {e["x"]:.0f},{e["y"]:.0f} -> bottom at {e["y"] + h:.0f} mm')
            ax.imshow(np.asarray(img), extent=[e['x'], e['x'] + e['w'], e['y'] + h, e['y']], zorder=2, aspect='auto')
        elif e['kind'] == 'table':
            yy = e['y']
            for r, row in enumerate(e['rows']):
                xx = e['x']
                fill = '#' + (BLUE if r == 0 else (WHITE if r % 2 else 'F4F8FB'))
                for c, cw in enumerate(e['col_w']):
                    ax.add_patch(plt.Rectangle((xx, yy), cw, e['row_h'], facecolor=fill, edgecolor='#BBBBBB', linewidth=0.5, zorder=2))
                    lines = []
                    for part in row[c].split('\n'):
                        lines += wrap(part.replace('​', ''), e['size'], cw - 3)
                    if len(lines) * e['size'] * PT * 1.2 > e['row_h'] - 1:
                        warnings.append(f'table cell ({r},{c}) "{row[c][:25]}" needs {len(lines)} lines')
                    ax.text(xx + 1.5, yy + 0.8, '\n'.join(lines), fontsize=e['size'], va='top', ha='left',
                            fontweight='bold' if r == 0 else 'normal', color='#' + (WHITE if r == 0 else DARK),
                            linespacing=1.15, zorder=3)
                    xx += cw
                yy += e['row_h']
    ax.set_xlim(0, PAGE_W)
    ax.set_ylim(PAGE_H, 0)
    fig.savefig(path, dpi=60)
    plt.close(fig)
    return warnings


def main():
    parser = argparse.ArgumentParser(description="Build the RIPE 93 poster (pptx + preview)")
    parser.add_argument('--e3', default=os.path.join('results', 'e3'), help='E3 results folder')
    parser.add_argument('--figs', default=os.path.join('results', 'poster'), help='folder with fig_*.png')
    parser.add_argument('--out', default=os.path.join('results', 'poster'), help='output folder')
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    els = layout(args.figs, args.e3)
    to_pptx(els, os.path.join(args.out, 'ripe93_poster.pptx'), args.out)
    warnings = to_preview(els, os.path.join(args.out, 'ripe93_poster_preview.png'), args.out)
    for w in warnings:
        print('LAYOUT WARNING:', w)
    print(f'written: {args.out}/ripe93_poster.pptx and ripe93_poster_preview.png')


if __name__ == '__main__':
    main()
