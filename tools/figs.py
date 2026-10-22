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
    s.text(16, 26, 'A two-layer validator key (EIP-8450 leanXMSS)', size=15, fill=INK, weight='bold')
    s.text(16, 44, 'The registered public key commits only to the top layer. Each bottom tree is built when needed and '
                   'certified once by one top-layer one-time key.', size=11, fill=MUTED)
    s.rect(455, 62, 190, 30, INK, rx=4)
    s.text(550, 82, 'registered public key (32 B)', size=11, fill='#ffffff', anchor='middle', weight='bold')
    s.add(f'<path d="M550,98 L300,210 L800,210 Z" fill="{TOP}" fill-opacity="0.15" stroke="{TOP}" stroke-width="2"/>')
    s.text(550, 160, 'top layer: 65,536 one-time keys', size=11.5, fill=INK, anchor='middle', weight='bold')
    s.text(550, 177, 'built once, jointly (MPC); top key b certifies bottom tree b', size=10.5, fill=INK2, anchor='middle')
    leaves = [(360, 'bottom tree 1', ACTIVE, 'signing now'), (550, 'bottom tree 2', NEXT, 'ready'),
              (740, 'bottom tree 3', BUILD, 'being built')]
    for x, name, col, state in leaves:
        s.dot(x, 210, col, r=7)
        s.line(x, 217, x, 300, stroke=col, width=2, dash=None if col != BUILD else '5,4')
        s.text(x + 8, 262, 'certification', size=9.5, fill=INK2)
        s.text(x + 8, 274, '(computed once)', size=9.5, fill=MUTED)
        dash = ' stroke-dasharray="6,4"' if col == BUILD else ''
        s.add(f'<path d="M{x},300 L{x - 85},400 L{x + 85},400 Z" fill="{col}" fill-opacity="0.18" stroke="{col}" '
              f'stroke-width="2"{dash}/>')
        s.text(x, 372, name, size=11, fill=INK, anchor='middle', weight='bold')
        s.text(x, 388, state, size=10, fill=INK2, anchor='middle')
        s.text(x, 418, '65,536 one-time keys', size=10, fill=INK2, anchor='middle')
        s.text(x, 432, '(one per signature)', size=10, fill=MUTED, anchor='middle')
    s.text(840, 352, '… 65,536 bottom trees', size=11, fill=MUTED)
    s.text(840, 368, '= 2³² leaf indices', size=11, fill=MUTED)
    s.text(16, 470, 'Signature (2,404 B): the bottom one-time signature + its 16-level path, then the top certification '
                    '+ its 16-level path.', size=11, fill=INK2)
    s.text(16, 488, 'The certification is computed once per bottom tree and reused in every signature from it, so the '
                    'top secrets can stay cold.', size=11, fill=INK2)
    s.text(16, 506, 'A single tree of height 32 would sign in 1,460 B, but its key generation covers all 2³² one-time '
                    'keys up front.', size=11, fill=MUTED)
    s.save(path, 'Illustrative structure; EIP-8450 parameters (Keccak-256, 58 chains, 16-byte values).')


# ---------------------------------------------------------------------------------------------------------
# 2. Key generation pipeline: a steady background job
def pipeline(path):
    d = lambda x: (x + 1) * 1000  # days after the switch -> gantt units (one day of lead-in)
    W = 3.03
    lanes = [dict(label='SIGNING (PRAWNS, every 4 s slot)', header=True)]
    for k in range(4):
        lanes.append(dict(label=f'bottom tree {k + 1} in use', bars=[(d(k * W), d((k + 1) * W), NEXT, f'tree {k + 1}')]))
    lanes.append(dict(label='KEY GENERATION (background MPC)', header=True))
    lanes.append(dict(label='registration: top layer + proof of possession', bars=[(d(-0.6), d(-0.55), CRIT, '2–7 min, any time before')]))
    lanes.append(dict(label='at the switch: bottom tree 1', bars=[(d(-0.3), d(-0.224), CRIT, '36–109 min')]))
    for k in range(1, 4):
        start = (k - 1) * W + 0.3
        lanes.append(dict(label=f'build + certify bottom tree {k + 1}', bars=[(d(start), d(start + 0.076), OFF, '36–109 min')]))
    gantt(path, 'Key generation runs in the background, one bottom tree ahead',
          'Worst case shown: attesting every 4 s slot, one leaf per signature, so a tree lasts ~3 days. At today\'s '
          'once-per-epoch cadence a tree lasts ~5 months. Bars to scale at 200 Mbps, per validator.',
          lanes, xmax=d(12.2), xstep=1000, lane_h=26, w=1100,
          tickfmt=lambda v: 'switch' if round(v) == 1000 else ('' if v < 1000 else f'day {v / 1000 - 1:g}'),
          comment='tools/cost_model.py --primary',
          legend=[(CRIT, 'one-off'), (OFF, 'background MPC job'), (NEXT, 'signing with a bottom tree')],
          label_w=300)


# ---------------------------------------------------------------------------------------------------------
# 3. Validator lifecycle (two-layer keys)
STAGES = ['Cluster\nformation', 'Register\n(EIP-8450)', 'Dormant\n(BLS signs)', 'Switch\nfork',
          'Every\nsignature', 'New bottom\ntree', 'Operator\nchange']
ROWS = [  # label, first stage, last stage, colour, bar text
    ('Agree cluster config, threshold, operators', 0, 0, CRIT, 'minutes (as today)'),
    ('MPC: top layer + proof of possession', 1, 1, CRIT, '2–7 min @200M'),
    ('BLS-sign the registration, once', 1, 1, CRIT, 'one-shot'),
    ('Reshare top-layer shares', 2, 2, OFF, 'keys stay registered'),
    ('MPC: first bottom tree; top key certifies it', 3, 3, CRIT, '36–109 min @200M'),
    ('Agree message (QBFT, as today)', 4, 4, CRIT, '≤ ~200 ms'),
    ('Randomness: threshold PRF on QBFT commits', 4, 4, CRIT, 'no extra round'),
    ('Grind the randomizer (~2^20 Keccak)', 4, 4, CRIT, '~0.1 s CPU'),
    ('PRF shares → combine → publish', 4, 4, CRIT, '~1–2 KiB / node'),
    ('MPC: build next bottom tree (background)', 5, 5, OFF, '36–109 min @200M'),
    ('Reshare top layer; new set builds next tree', 6, 6, OFF, 'same key'),
    ('Never-sign-twice (leaves, certifications)', 1, 6, OFF, 'like a slashing DB'),
    ('Key material held per node', 1, 6, OFF, '≤ 0.55 GB per validator'),
]


def lifecycle(path):
    L, T, colw, rowh = 320, 96, 124, 30
    w = L + colw * len(STAGES) + 20
    h = T + rowh * len(ROWS) + 70
    s = Svg(w, h)
    s.text(16, 26, "A distributed validator's life with EIP-8450 keys", size=15, fill=INK, weight='bold')
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
    s.save(path, 'Sources: EIP-8450, PRAWNS (ePrint 2026/2142), tools/cost_model.py --primary')


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
        dict(label='rho = tPRF(msg) + i (shares on commits)', bars=[(1000, 1120, CRIT, 'grind 2^20, ~0.1 s')]),
        dict(label='each node: PRF shares (no hashing)', bars=[(1120, 1135, CRIT, '')]),
        dict(label='send shares to combiner (1 RTT)', bars=[(1135, 1220, CRIT, '')]),
        dict(label='combine, look up table, publish', bars=[(1220, 1320, CRIT, 'sign')]),
        dict(label='background: never-sign-twice record', bars=[(0, 4000, OFF, 'persisted before shares leave the node', 0.35)]),
        dict(label='IF WE HAD TO SIGN INSIDE MPC', header=True),
        dict(label='Keccak chains in MPC (72 rounds)', bars=[(1000, 4000, RISK, '→ 1.4–7 s at 20–100 ms RTT: misses the slot', 0.85)]),
        dict(label='rho grinding in MPC (2^20 Keccak)', bars=[(1000, 4000, RISK, '→ 5–15 GB of MPC traffic per signature', 0.85)]),
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
        dict(label='EIP-8450 registry fork (after Heze)', bars=[(m(0), m(24), EXT, 'Draft → devnets → mainnet; dormant keys', 0.6)]),
        dict(label='switch fork: duties move to PQ keys', bars=[(m(12), m(24), EXT, 'duty set, cadence, aggregation', 0.6)]),
        dict(label='SPEC INPUT', header=True),
        dict(label='asks: dense allocation, outcome rule, replacement', bars=[(m(0), m(6), CRIT, 'EIP-8450 thread')]),
        dict(label='threshold profile for EIP-8310 keystores', bars=[(m(1), m(6), OFF, 'with client teams')]),
        dict(label='BUILD: REGISTRATION', header=True),
        dict(label='charon: BLS-authorized registration', bars=[(m(0), m(3), CRIT, 'one-shot; dealer keys on devnets')]),
        dict(label='top-layer Keccak MPC + proof of possession', bars=[(m(1), m(8), CRIT, '2^12 range; PRSS/DN07')]),
        dict(label='owner path in withdrawal contracts', bars=[(m(3), m(8), OFF, 'PQ key authorization')]),
        dict(label='top-layer resharing', bars=[(m(6), m(12), OFF, 'operator changes while dormant')]),
        dict(label='BUILD: SIGNING', header=True),
        dict(label='bottom-tree MPC + PRAWNS signing + leaf allocator', bars=[(m(9), m(20), CRIT, 'as the switch fork takes shape')]),
        dict(label='threshold two-layer proof; Lean proofs', bars=[(m(4), m(16), OFF, 'PRAWNS + leanXMSS')]),
        dict(label='robustness / identifiable abort', bars=[(m(8), m(16), OFF, 'evict a faulty node')]),
        dict(label='SHIP', header=True),
        dict(label='audit; register on devnets, then mainnet', bars=[(m(8), m(14), CRIT, 'ready for the registry fork')]),
    ]
    gantt(path, 'The road to post-quantum distributed validators (illustrative, months from now)',
          'Orange = critical path. Grey = Ethereum timelines we do not control. Durations are engineering estimates.',
          lanes, xmax=m(24), xstep=m(3), lane_h=26, w=1100, tickfmt=lambda v: f'{v / 1000:g} mo',
          comment='Illustrative sequencing, not a commitment.',
          legend=[(CRIT, 'critical path'), (OFF, 'off the critical path'), (EXT, 'external dependency')], label_w=330)


if __name__ == '__main__':
    keys('../docs/fig/keys.svg')
    pipeline('../docs/fig/pipeline.svg')
    lifecycle('../docs/fig/lifecycle.svg')
    slot('../docs/fig/slot.svg')
    roadmap('../docs/fig/roadmap.svg')
    print('ok')
