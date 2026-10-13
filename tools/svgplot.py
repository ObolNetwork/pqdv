"""Tiny SVG chart helpers: white card, recessive grid, 2px lines, direct labels + legend.

Palette: validated categorical slots (light mode) from the dataviz reference palette.
"""
from xml.sax.saxutils import escape

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#ecebe8", "#ffffff"
FONT = "Helvetica, Arial, sans-serif"


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []
        self.add(f'<rect x="0" y="0" width="{w}" height="{h}" fill="{SURF}"/>')

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=11, fill=INK2, anchor="start", weight="normal"):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
                 f'font-weight="{weight}">{escape(s)}</text>')

    def line(self, x1, y1, x2, y2, stroke=GRID, width=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width}"{d}/>')

    def rect(self, x, y, w, h, fill, rx=0, opacity=1.0):
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" fill-opacity="{opacity}"/>')

    def path(self, pts, stroke, width=2, dash=None):
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"{da}/>')

    def dot(self, x, y, fill, r=4):
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{SURF}" stroke-width="2"/>')

    def save(self, path, comment=""):
        c = f"<!-- {escape(comment).replace('--', '- -')} -->\n" if comment else ""
        open(path, "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
            f'font-family="{FONT}">\n{c}' + "\n".join(self.parts) + "\n</svg>\n")


def cdf_chart(path, title, subtitle, series, xmax, xstep, vlines=(), w=960, h=440, comment="",
              xlabel="seconds from slot start", label_q=0.9, ymin=0.0, yticks=(0, 0.25, 0.5, 0.75, 0.9, 1.0),
              ylabel=None, xmin=0, markers=False, xfmt=None):
    """series: list of dict(label, pts=[(x_ms, cumfrac)], color, dash?). Draws CDFs (y = fraction <= x)."""
    L, R, T, B = 70, 210, 84, 52
    pw, ph = w - L - R, h - T - B
    X = lambda v: L + pw * (min(max(v, xmin), xmax) - xmin) / (xmax - xmin)
    Y = lambda f: T + ph * (1 - (max(f, ymin) - ymin) / (1 - ymin))
    s = Svg(w, h)
    s.text(L, 26, title, size=15, fill=INK, weight="bold")
    s.text(L, 44, subtitle, size=11, fill=MUTED)
    for f in yticks:
        s.line(L, Y(f), L + pw, Y(f), stroke=GRID)
        s.text(L - 8, Y(f) + 4, f"{f*100:g}%", size=10, fill=MUTED, anchor="end")
    if ylabel:
        s.add(f'<text x="16" y="{T + ph / 2:.1f}" font-size="11" fill="{INK2}" text-anchor="middle" transform="rotate(-90 16 {T + ph / 2:.1f})">{escape(ylabel)}</text>')
    v = xmin
    while v <= xmax + 1e-9:
        s.line(X(v), T, X(v), T + ph, stroke=GRID)
        s.text(X(v), T + ph + 16, xfmt(v) if xfmt else f"{v/1000:g}s", size=10, fill=MUTED, anchor="middle")
        v += xstep
    s.text(L + pw / 2, h - 12, xlabel, size=11, fill=INK2, anchor="middle")
    for k, (vx, vlabel) in enumerate(vlines):
        s.line(X(vx), T - 4 - 12 * (k % 2), X(vx), T + ph, stroke=INK2, width=1.5, dash="5,4")
        s.text(X(vx) + 4, T - 6 - 12 * (k % 2), vlabel, size=10, fill=INK2)
    ends = []
    for i, se in enumerate(series):
        col = se.get("color", SERIES[i % len(SERIES)])
        pts = [(X(x), Y(f)) for x, f in se["pts"] if x <= xmax * 1.02]
        if not pts:
            continue
        s.path(pts, col, dash=se.get("dash"))
        if markers:
            for x, y in pts:
                s.dot(x, y, col, r=3)
        elif label_q is not None:
            qx = next((x for x, f in se["pts"] if f >= label_q), None)
            if qx is not None and qx <= xmax:
                s.dot(X(qx), Y(label_q), col)
        for (px, py, ptxt) in se.get("annot", []):
            s.dot(X(px), Y(py), col, r=5)
            s.text(X(px) + 8, Y(py) - 8, ptxt, size=10, fill=INK)
        ends.append((pts[-1][1], se["label"], col, se.get("dash")))
    # legend on the right (identity channel), ordered as series
    ly = T + 4
    for i, se in enumerate(series):
        col = se.get("color", SERIES[i % len(SERIES)])
        s.path([(L + pw + 18, ly), (L + pw + 40, ly)], col, dash=se.get("dash"))
        for j, chunk in enumerate(_wrap(se["label"], 22)):
            s.text(L + pw + 46, ly + 4 + 13 * j, chunk, size=10.5, fill=INK2)
        ly += 13 * len(_wrap(se["label"], 22)) + 10
    s.save(path, comment)


def _wrap(t, n):
    words, out, cur = t.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > n and cur:
            out.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    out.append(cur)
    return out


def gantt(path, title, subtitle, lanes, xmax, xstep, vlines=(), w=960, lane_h=26, comment="", legend=(), tickfmt=None, label_w=280):
    """lanes: list of dict(label, bars=[(start_ms, end_ms, color, text?, opacity?)], marks=[(x, text)])."""
    L, R, T = label_w, 30, 64
    pw = w - L - R
    h = T + lane_h * len(lanes) + 70 + (18 if legend else 0)
    X = lambda v: L + pw * min(max(v, 0), xmax) / xmax
    s = Svg(w, h)
    s.text(16, 26, title, size=15, fill=INK, weight="bold")
    s.text(16, 44, subtitle, size=11, fill=MUTED)
    bottom = T + lane_h * len(lanes)
    v = 0
    while v <= xmax + 1e-9:
        s.line(X(v), T - 6, X(v), bottom, stroke=GRID)
        s.text(X(v), bottom + 16, tickfmt(v) if tickfmt else f"{v/1000:g}s", size=10, fill=MUTED, anchor="middle")
        v += xstep
    for vx, vl in vlines:
        s.line(X(vx), T - 10, X(vx), bottom + 4, stroke=INK2, width=1.5, dash="5,4")
        s.text(X(vx) + 4, T - 12, vl, size=10, fill=INK2)
    for i, ln in enumerate(lanes):
        y = T + i * lane_h
        if ln.get("header"):
            s.text(16, y + lane_h * 0.68, ln["label"], size=11.5, fill=INK, weight="bold")
            continue
        s.text(16, y + lane_h * 0.66, ln["label"], size=11, fill=INK2)
        for b in ln.get("bars", []):
            x0, x1, col = b[0], b[1], b[2]
            txt = b[3] if len(b) > 3 else None
            op = b[4] if len(b) > 4 else 1.0
            s.rect(X(x0) + 1, y + 4, X(x1) - X(x0) - 2, lane_h - 8, col, rx=3, opacity=op)
            if txt:
                width_px = X(x1) - X(x0)
                if width_px > 7 * len(txt):
                    s.text((X(x0) + X(x1)) / 2, y + lane_h * 0.66, txt, size=10, fill="#ffffff" if op > 0.6 else INK, anchor="middle")
                elif b is ln["bars"][-1]:
                    s.text(X(x1) + 4, y + lane_h * 0.66, txt, size=10, fill=INK2)
        for mx, mt in ln.get("marks", []):
            s.add(f'<path d="M{X(mx)-5:.1f},{y+4} L{X(mx)+5:.1f},{y+lane_h-4} M{X(mx)+5:.1f},{y+4} L{X(mx)-5:.1f},{y+lane_h-4}" stroke="{INK}" stroke-width="2"/>')
            if mt:
                s.text(X(mx) + 8, y + lane_h * 0.66, mt, size=10, fill=INK)
    lx = L
    for col, lab in legend:
        s.rect(lx, bottom + 30, 14, 10, col, rx=2)
        s.text(lx + 19, bottom + 39, lab, size=10.5, fill=INK2)
        lx += 26 + 6.2 * len(lab)
    s.save(path, comment)
