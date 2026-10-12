"""Figures for the pqdv README / docs. Run from tools/: python3 figs.py  -> ../docs/fig/*.svg"""
import sys
sys.path.insert(0, '.')
from svgplot import Svg, gantt, SERIES, INK, INK2, MUTED, GRID

CRIT, OFF, EXT, RISK = SERIES[1], SERIES[0], '#b9b8b2', SERIES[7]

# ---------------------------------------------------------------------------------------------------------
# 1. Validator lifecycle: which activities run in which stage, on/off the critical path, and their bottleneck
STAGES = ['Cluster\nformation', 'Key\ngeneration', 'Distribute\npublic table', 'Deposit &\nactivation',
          'Every slot\n(4 s)', 'Every ~3 days\n(2^16 slots)', 'Operator\nchange', 'Key lifetime\nends']
ROWS = [  # label, first stage, last stage, colour, bar text
    ('Agree cluster config, threshold, operators', 0, 0, CRIT, 'minutes (as today)'),
    ('Prototype only: dealer in a TEE', 1, 1, OFF, 'minutes; trust HW'),
    ('MPC key generation (BLAKE2s)', 1, 1, RISK, '12–35 TB/val-yr'),
    ('Store public table (f+1 or remote)', 2, 2, CRIT, '≤74 GB/val-yr'),
    ('Register 52-byte public key', 3, 3, CRIT, 'protocol queue'),
    ('Agree message (QBFT, as today)', 4, 4, CRIT, '≤ ~200 ms'),
    ('Agree encoding randomness (rho)', 4, 4, CRIT, '+1–2 rounds'),
    ('PRF shares → combine → publish', 4, 4, CRIT, '~1.5 KiB / node'),
    ('Never-sign-twice record per slot', 4, 7, OFF, 'like a slashing DB'),
    ('Prefetch next table window', 5, 5, OFF, '~0.6 GB'),
    ('F_hash: new key = new validator', 6, 6, RISK, 'full re-keygen'),
    ('F_lat: reshare, same public key', 6, 6, OFF, 'cheap; research'),
    ('Rotate to pre-built key (12–18 mo)', 7, 7, RISK, 'protocol ask'),
]


def lifecycle(path):
    L, T, colw, rowh = 300, 96, 118, 30
    w = L + colw * len(STAGES) + 20
    h = T + rowh * len(ROWS) + 70
    s = Svg(w, h)
    s.text(16, 26, 'A distributed validator\'s life with threshold leanSig (PRAWNS)', size=15, fill=INK, weight='bold')
    s.text(16, 44, 'Columns are lifecycle stages (not to scale). Orange = on the critical path to signing; '
                   'blue = background; red = the hard / open parts.', size=11, fill=MUTED)
    for i, st in enumerate(STAGES):
        x = L + i * colw
        s.rect(x + 1, T - 40, colw - 2, 34, '#f3f2ef', rx=3)
        for k, line in enumerate(st.split('\n')):
            s.text(x + colw / 2, T - 26 + 13 * k, line, size=10.5, fill=INK, anchor='middle', weight='bold')
        s.line(x, T - 4, x, T + rowh * len(ROWS), stroke=GRID)
    for r, (label, a, b, col, txt) in enumerate(ROWS):
        y = T + r * rowh
        s.text(16, y + rowh * 0.65, label, size=11, fill=INK2)
        x0, x1 = L + a * colw + 3, L + (b + 1) * colw - 3
        s.rect(x0, y + 5, x1 - x0, rowh - 10, col, rx=3, opacity=0.9)
        s.text((x0 + x1) / 2, y + rowh * 0.66, txt, size=9.5, fill='#ffffff', anchor='middle')
    ly = T + rowh * len(ROWS) + 30
    lx = L
    for col, lab in ((CRIT, 'on the critical path'), (OFF, 'background / off the critical path'), (RISK, 'hard, expensive or unsolved')):
        s.rect(lx, ly - 10, 14, 10, col, rx=2)
        s.text(lx + 19, ly - 1, lab, size=10.5, fill=INK2)
        lx += 40 + 6.4 * len(lab)
    s.save(path, 'Sources: PRAWNS (ePrint 2026/2142), leanSpec/leanSig repos, tools/cost_model.py')


# ---------------------------------------------------------------------------------------------------------
# 2. One 4-second lean slot: the signing path, and why signing inside MPC does not fit
def slot(path):
    P = [SERIES[6], SERIES[0], SERIES[2], SERIES[3], SERIES[4]]
    lanes = [
        dict(label='LEAN CONSENSUS SLOT (5 × 800 ms)', header=True),
        dict(label='protocol schedule', bars=[(0, 800, P[0], 'propose'), (800, 1600, P[1], 'attest'),
                                              (1600, 2400, P[2], 'aggregate'), (2400, 3200, P[3], 'confirm'),
                                              (3200, 4000, P[4], 'ingest')]),
        dict(label='DV ATTESTATION WITH PRAWNS', header=True),
        dict(label='agree on the message (QBFT)', bars=[(800, 1000, CRIT, 'QBFT')]),
        dict(label='agree encoding randomness (rho)', bars=[(1000, 1100, CRIT, 'rho')]),
        dict(label='each node: PRF shares (no hashing)', bars=[(1100, 1115, CRIT, '')], marks=[]),
        dict(label='send shares to combiner (1 RTT)', bars=[(1115, 1200, CRIT, '')]),
        dict(label='combine, look up cpk, grind, publish', bars=[(1200, 1300, CRIT, 'sign')]),
        dict(label='background: never-sign-twice record', bars=[(0, 4000, OFF, 'persisted before shares leave the node', 0.35)]),
        dict(label='IF WE HAD TO SIGN INSIDE MPC', header=True),
        dict(label='Poseidon chains in MPC (196–392 rounds)', bars=[(1000, 4000, RISK, '→ 4–39 s: misses the slot', 0.85)]),
        dict(label='BLAKE2s chains in MPC (3.6k–17.6k rounds)', bars=[(1000, 4000, RISK, '→ 73 s – 29 min', 0.85)]),
        dict(label='rho grinding in MPC (BLAKE2s, 2^15 tries)', bars=[(1000, 4000, RISK, '→ ≥10 s and ~150 Mbps per validator', 0.85)]),
    ]
    gantt(path, 'One lean slot: where a threshold signature has to fit',
          'PRAWNS keeps all hashing off the slot\'s critical path; signing inside MPC cannot meet the 1.6 s aggregation point.',
          lanes, xmax=4000, xstep=400, vlines=[(800, 'attest'), (1600, 'aggregators')], lane_h=26, w=1100,
          comment='Durations for the PRAWNS path are illustrative (charon QBFT ~tens-hundreds of ms); MPC rows from tools/cost_model.py',
          legend=[(CRIT, 'critical path'), (OFF, 'background'), (RISK, 'does not fit')], label_w=300)


# ---------------------------------------------------------------------------------------------------------
# 3. R&D journey: what is on the critical path to a dealer-free threshold leanSig
def roadmap(path):
    m = lambda x: x * 1000  # months -> gantt units
    lanes = [
        dict(label='ETHEREUM (external, dates unknown)', header=True),
        dict(label='leanSig params + hash choice settle', bars=[(m(0), m(9), EXT, 'drifting to BLAKE (Flock-proven)')]),
        dict(label='lean consensus specs → PQ fork', bars=[(m(6), m(24), EXT, 'specs 2027 per lean roadmap talks; fork date unknown', 0.6)]),
        dict(label='SPEC ASKS (critical)', header=True),
        dict(label='rotation 12–18 mo, joint rho, records', bars=[(m(0), m(6), CRIT, 'engage EF / leanSig / leanSpec')]),
        dict(label='XMSS-level PRAWNS proof for leanSig', bars=[(m(2), m(10), CRIT, 'authors sketch only today')]),
        dict(label='BUILD', header=True),
        dict(label='dealer-based F_hash prototype in charon', bars=[(m(1), m(7), CRIT, 'lean devnet, real numbers')]),
        dict(label='public-table (cpk) storage + combiner', bars=[(m(4), m(9), OFF, 'storage, prefetch')]),
        dict(label='Boolean MPC keygen: 6-day key < 1 h', bars=[(m(3), m(10), CRIT, 'BLAKE2s, 3–4 party, PRSS/DN07')]),
        dict(label='12-month keys, chunked + resumable', bars=[(m(10), m(17), CRIT, 'TB-scale, background')]),
        dict(label='RESEARCH (parallel)', header=True),
        dict(label='robustness / identifiable abort', bars=[(m(4), m(14), OFF, 'paper: none yet')]),
        dict(label='operator change without re-keying', bars=[(m(6), m(18), OFF, 'F_lat or new idea')]),
        dict(label='SHIP', header=True),
        dict(label='audit + production hardening', bars=[(m(17), m(23), CRIT, 'gated on the above')]),
    ]
    gantt(path, 'The journey to a dealer-free threshold leanSig (illustrative, months from now)',
          'Orange = critical path. Grey = Ethereum timelines we do not control. Durations are rough engineering guesses.',
          lanes, xmax=m(24), xstep=m(3), lane_h=26, w=1100, tickfmt=lambda v: f'{v / 1000:g} mo',
          comment='Illustrative sequencing, not a commitment.',
          legend=[(CRIT, 'critical path'), (OFF, 'off the critical path'), (EXT, 'external dependency')], label_w=300)


if __name__ == '__main__':
    lifecycle('../docs/fig/lifecycle.svg')
    slot('../docs/fig/slot.svg')
    roadmap('../docs/fig/roadmap.svg')
    print('ok')
