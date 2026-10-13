"""Figures for the pqdv README / docs. Run from tools/: python3 figs.py  -> ../docs/fig/*.svg"""
import sys
sys.path.insert(0, '.')
from svgplot import Svg, gantt, SERIES, INK, INK2, MUTED, GRID

CRIT, OFF, EXT, RISK = SERIES[1], SERIES[0], '#b9b8b2', SERIES[7]
TOP, ACTIVE, NEXT, BUILD = SERIES[6], SERIES[0], SERIES[2], SERIES[3]


# ---------------------------------------------------------------------------------------------------------
# 1. The two-layer key
def keys(path):
    w, h = 1100, 520
    s = Svg(w, h)
    s.text(16, 26, 'A two-layer validator key', size=15, fill=INK, weight='bold')
    s.text(16, 44, 'The public key commits only to the top layer. Each ~3-day window gets a fresh bottom tree, '
                   'certified once by one top-layer one-time key.', size=11, fill=MUTED)
    s.rect(470, 62, 160, 30, INK, rx=4)
    s.text(550, 82, 'validator public key', size=11, fill='#ffffff', anchor='middle', weight='bold')
    s.add(f'<path d="M550,98 L300,210 L800,210 Z" fill="{TOP}" fill-opacity="0.15" stroke="{TOP}" stroke-width="2"/>')
    s.text(550, 160, 'top layer: 65,536 one-time keys', size=11.5, fill=INK, anchor='middle', weight='bold')
    s.text(550, 177, 'built once, jointly (MPC); one key per window', size=10.5, fill=INK2, anchor='middle')
    leaves = [(360, 'window 1', ACTIVE, 'signing now'), (550, 'window 2', NEXT, 'ready'), (740, 'window 3', BUILD, 'being built')]
    for x, name, col, state in leaves:
        s.dot(x, 210, col, r=7)
        s.line(x, 217, x, 300, stroke=col, width=2, dash=None if col != BUILD else '5,4')
        s.text(x + 8, 262, 'certificate', size=9.5, fill=INK2)
        s.text(x + 8, 274, '(posted once)', size=9.5, fill=MUTED)
        dash = ' stroke-dasharray="6,4"' if col == BUILD else ''
        s.add(f'<path d="M{x},300 L{x - 85},400 L{x + 85},400 Z" fill="{col}" fill-opacity="0.18" stroke="{col}" '
              f'stroke-width="2"{dash}/>')
        s.text(x, 372, name, size=11, fill=INK, anchor='middle', weight='bold')
        s.text(x, 388, state, size=10, fill=INK2, anchor='middle')
        s.text(x, 418, '65,536 one-time keys', size=10, fill=INK2, anchor='middle')
        s.text(x, 432, '(one per slot, ~3 days)', size=10, fill=MUTED, anchor='middle')
    s.text(840, 352, '… 65,536 windows', size=11, fill=MUTED)
    s.text(840, 368, '= 2³² slots ≈ 544 years', size=11, fill=MUTED)
    s.text(16, 470, 'Per-slot signature (~952 B): one one-time signature + a 16-level path to the current window\'s '
                    'certified root.', size=11, fill=INK2)
    s.text(16, 488, 'Once per window (~950 B): a top-layer one-time signature over the new window\'s root, registered '
                    'on-chain or inside a periodic proof.', size=11, fill=INK2)
    s.text(16, 506, 'Today\'s single tree instead fixes every slot\'s key up front: 1,208 B signatures and key '
                    'generation for the whole activation range.', size=11, fill=MUTED)
    s.save(path, 'Illustrative structure; sizes for draft leanSig parameters (BLAKE2s, 42 chains, 128-bit values).')


# ---------------------------------------------------------------------------------------------------------
# 2. Key generation pipeline: a steady background job
def pipeline(path):
    d = lambda x: x * 1000  # days -> gantt units
    W = 3.03
    lanes = [dict(label='SIGNING (per slot, PRAWNS)', header=True)]
    for k in range(4):
        lanes.append(dict(label=f'window {k + 1} active', bars=[(d(k * W), d((k + 1) * W), NEXT, f'window {k + 1}')]))
    lanes.append(dict(label='KEY GENERATION (background MPC)', header=True))
    lanes.append(dict(label='up front: top layer + window 1', bars=[(d(0), d(0.2), CRIT, '1.6–4.9 h')]))
    for k in range(1, 4):
        start = (k - 1) * W + 0.3
        lanes.append(dict(label=f'build + certify window {k + 1}', bars=[(d(start), d(start + 0.13), OFF, '1–3 h')]))
    gantt(path, 'Key generation runs in the background, one window ahead',
          'Each ~3-day window\'s keys are built and certified while the previous window signs. '
          'Bars to scale at 200 Mbps, per validator.',
          lanes, xmax=d(12.2), xstep=d(1), lane_h=26, w=1100, tickfmt=lambda v: f'day {v / 1000:g}',
          comment='tools/cost_model.py --primary',
          legend=[(CRIT, 'one-off, before activation'), (OFF, 'background MPC job'), (NEXT, 'signing window')],
          label_w=280)


# ---------------------------------------------------------------------------------------------------------
# 3. Validator lifecycle (two-layer keys)
STAGES = ['Cluster\nformation', 'Key\ngeneration', 'Deposit &\nactivation', 'Every slot\n(4 s)',
          'Every ~3 days\n(new window)', 'Operator\nchange', 'Exit']
ROWS = [  # label, first stage, last stage, colour, bar text
    ('Agree cluster config, threshold, operators', 0, 0, CRIT, 'minutes (as today)'),
    ('MPC: top layer + first window', 1, 1, CRIT, '1.6–4.9 h @200M'),
    ('Register the public key', 2, 2, CRIT, 'protocol queue'),
    ('Agree message (QBFT, as today)', 3, 3, CRIT, '≤ ~200 ms'),
    ('Randomness: threshold PRF on QBFT commits', 3, 3, CRIT, 'no extra round'),
    ('PRF shares → combine → publish', 3, 3, CRIT, '~1.5 KiB / node'),
    ('Never-sign-twice records (slots + windows)', 3, 6, OFF, 'like a slashing DB'),
    ('MPC: build next window (background)', 4, 4, OFF, '1–3 h @200M'),
    ('Certify next window (top-layer signature)', 4, 4, OFF, '~950 B, once'),
    ('Reshare top layer; new set builds next window', 5, 5, OFF, 'same validator'),
    ('Key material held per node', 1, 6, OFF, '≈ 1.5 GB per validator'),
]


def lifecycle(path):
    L, T, colw, rowh = 320, 96, 124, 30
    w = L + colw * len(STAGES) + 20
    h = T + rowh * len(ROWS) + 70
    s = Svg(w, h)
    s.text(16, 26, "A distributed validator's life with two-layer keys", size=15, fill=INK, weight='bold')
    s.text(16, 44, 'Columns are lifecycle stages (not to scale). Orange = on the critical path to signing; '
                   'blue = background work.', size=11, fill=MUTED)
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
    ly, lx = T + rowh * len(ROWS) + 30, L
    for col, lab in ((CRIT, 'on the critical path'), (OFF, 'background / off the critical path')):
        s.rect(lx, ly - 10, 14, 10, col, rx=2)
        s.text(lx + 19, ly - 1, lab, size=10.5, fill=INK2)
        lx += 40 + 6.4 * len(lab)
    s.save(path, 'Sources: PRAWNS (ePrint 2026/2142), leanSpec/leanSig repos, tools/cost_model.py --primary')


# ---------------------------------------------------------------------------------------------------------
# 4. One 4-second lean slot
def slot(path):
    P = [SERIES[6], SERIES[0], SERIES[2], SERIES[3], SERIES[4]]
    lanes = [
        dict(label='LEAN CONSENSUS SLOT (5 × 800 ms)', header=True),
        dict(label='protocol schedule', bars=[(0, 800, P[0], 'propose'), (800, 1600, P[1], 'attest'),
                                              (1600, 2400, P[2], 'aggregate'), (2400, 3200, P[3], 'confirm'),
                                              (3200, 4000, P[4], 'ingest')]),
        dict(label='DV ATTESTATION WITH PRAWNS', header=True),
        dict(label='agree on the message (QBFT)', bars=[(800, 1000, CRIT, 'QBFT')]),
        dict(label='rho = tPRF(msg) + i (shares on commits)', bars=[(1000, 1020, CRIT, 'grind')]),
        dict(label='each node: PRF shares (no hashing)', bars=[(1100, 1115, CRIT, '')]),
        dict(label='send shares to combiner (1 RTT)', bars=[(1115, 1200, CRIT, '')]),
        dict(label='combine, look up table, publish', bars=[(1200, 1300, CRIT, 'sign')]),
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
# 5. Roadmap
def roadmap(path):
    m = lambda x: x * 1000
    lanes = [
        dict(label='ETHEREUM (external, dates unknown)', header=True),
        dict(label='leanSig parameters + hash settle', bars=[(m(0), m(9), EXT, 'classic hash (BLAKE family)')]),
        dict(label='lean consensus specs → PQ chain', bars=[(m(6), m(24), EXT, 'specs 2027 per lean roadmap talks; launch date unknown', 0.6)]),
        dict(label='SPEC ASKS (critical)', header=True),
        dict(label='two-layer keys, certified roots', bars=[(m(0), m(8), CRIT, 'design with leanSig / leanSpec')]),
        dict(label='bless threshold-derived randomness', bars=[(m(0), m(4), CRIT, 'tPRF(msg) + i')]),
        dict(label='PROOFS', header=True),
        dict(label='threshold two-layer XMSS proof', bars=[(m(2), m(10), CRIT, 'PRAWNS + certified roots')]),
        dict(label='formal proofs in Lean', bars=[(m(4), m(16), OFF, 'extend existing XMSS proofs')]),
        dict(label='BUILD', header=True),
        dict(label='dealer-based prototype in charon', bars=[(m(1), m(6), CRIT, 'lean devnet, real numbers')]),
        dict(label='per-window Boolean MPC key generation', bars=[(m(3), m(12), CRIT, 'BLAKE2s, PRSS/DN07, resumable')]),
        dict(label='top-layer shares + resharing', bars=[(m(6), m(13), OFF, 'operator changes')]),
        dict(label='robustness / identifiable abort', bars=[(m(4), m(14), OFF, 'evict a faulty node')]),
        dict(label='SHIP', header=True),
        dict(label='audit + production hardening', bars=[(m(13), m(20), CRIT, 'ready ahead of the PQ chain')]),
    ]
    gantt(path, 'The road to post-quantum distributed validators (illustrative, months from now)',
          'Orange = critical path. Grey = Ethereum timelines we do not control. Durations are engineering estimates.',
          lanes, xmax=m(24), xstep=m(3), lane_h=26, w=1100, tickfmt=lambda v: f'{v / 1000:g} mo',
          comment='Illustrative sequencing, not a commitment.',
          legend=[(CRIT, 'critical path'), (OFF, 'off the critical path'), (EXT, 'external dependency')], label_w=300)


if __name__ == '__main__':
    keys('../docs/fig/keys.svg')
    pipeline('../docs/fig/pipeline.svg')
    lifecycle('../docs/fig/lifecycle.svg')
    slot('../docs/fig/slot.svg')
    roadmap('../docs/fig/roadmap.svg')
    print('ok')
