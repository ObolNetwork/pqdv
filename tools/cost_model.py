#!/usr/bin/env python3
"""Back-of-envelope cost model for threshold leanSig (PRAWNS) and for moving pieces into MPC.

Every constant is either sourced (see SOURCES) or an explicit assumption (ASSUME_*).
Run: python3 tools/cost_model.py
"""

SOURCES = {
    "leanSig set A (devnets)": "leanSpec xmss/constants.py PROD_CONFIG; leanSig instantiations_aborting.rs: "
                               "46 chains, base 8 (7 steps), Poseidon1 width-16 chain step, 8 full + 20 partial rounds, x^3",
    "leanSig set B (draft spec)": "leanVM doc/xmss + crates/xmss: 42 chains, chain length 8 (7 steps), BLAKE2s, ~2^14.85 grinding",
    "lean slots": "leanSpec forks/lstar/config.py: 4 s slots, 5 intervals of 800 ms; attest at interval 1, aggregate at interval 2",
    "keys per validator": "leanSpec containers/validator.py: attestation key + proposal key",
    "pqdv calibration": "pqdv doc/5_benchmarks.tex (MP-SPDZ, 5 parties): malicious Shamir 118.28 GB / 7.51e8 triples, "
                        "ATLAS 23.65 GB / 3.75e8 triples",
}

SLOT_S = 4
SLOTS_PER_YEAR = int(365.25 * 86400 / SLOT_S)
KEYS_PER_VALIDATOR = 2

# ---- per-hash MPC cost ----------------------------------------------------------------------------------
# Poseidon1, width 16, x^3: S-boxes = 8 full rounds * 16 + 20 partial rounds * 1 = 148; x^3 = 2 multiplications.
POSEIDON = dict(name="Poseidon1-16 (KoalaBear, x^3)", ops=148 * 2, bits_per_op=31,
                depth_lo=28, depth_hi=56)  # 28 rounds with one-round cube (cube triples), 56 with plain Beaver
# BLAKE2s compression: 10 rounds x 8 G; G = 2 three-operand adds + 2 two-operand adds on 32-bit words.
# ripple-carry adders (31 ANDs, depth ~31) with a carry-save layer for 3-operand adds (64 ANDs, depth 1):
BLAKE_RIPPLE_AND = 80 * (2 * (64 + 31) + 2 * 31)          # 20,160 ANDs
BLAKE_RIPPLE_DEPTH = 10 * 2 * ((1 + 31) + 31 + (1 + 31) + 31)  # 2,520 AND-depth
# parallel-prefix adders (~240 ANDs, depth ~6) trade ANDs for depth:
BLAKE_PREFIX_AND = 80 * (2 * (64 + 240) + 2 * 240)        # ~87k ANDs
BLAKE_PREFIX_DEPTH = 10 * 2 * ((1 + 6) + 6 + (1 + 6) + 6)  # ~520 AND-depth
# Keccak-f[1600] (SHAKE128, leanSig set A's PRF for chain starts / rho): chi = 1600 ANDs per round, 24 rounds
KECCAK_AND, KECCAK_DEPTH = 1600 * 24, 24

# ---- MPC protocol cost per multiplication / AND, per party (bytes or bits on the wire, incl. preprocessing) -
ASSUME_BYTES_PER_MULT = {"best 3-4 party (replicated / Fantastic-Four-like)": 4,
                         "semi-honest Shamir, measured (ATLAS in pqdv)": 23.65e9 / 3.75e8 / 5,
                         "malicious Shamir, measured (pqdv)": 118.28e9 / 7.51e8 / 5}
ASSUME_BITS_PER_AND = {"3-4 party replicated Boolean": (1, 3),  # semi-honest .. malicious
                       "n>4 Shamir over GF(2^8)": (8, 24)}


def fmt_b(b):
    return f"{b / 1e9:.0f} GB" if b < 1e12 else f"{b / 1e12:.1f} TB"


def fmt_t(s):
    if s < 120:
        return f"{s:.0f} s"
    if s < 7200:
        return f"{s / 60:.0f} min"
    if s < 3 * 86400:
        return f"{s / 3600:.1f} h"
    return f"{s / 86400:.1f} d"


def hash_table():
    print("## Per hash call inside MPC (one chain step)\n")
    print("| hash | non-linear ops | MPC rounds (depth) | wire per party |")
    print("|---|---|---|---|")
    p = POSEIDON
    print(f"| {p['name']} | {p['ops']} field mults | {p['depth_lo']}–{p['depth_hi']} | "
          f"{p['ops'] * 4 / 1024:.1f}–{p['ops'] * 31 / 1024:.1f} KiB |")
    for label, ands, depth in (("BLAKE2s, ripple adders", BLAKE_RIPPLE_AND, BLAKE_RIPPLE_DEPTH),
                               ("BLAKE2s, prefix adders", BLAKE_PREFIX_AND, BLAKE_PREFIX_DEPTH),
                               ("Keccak-f[1600] (SHAKE128)", KECCAK_AND, KECCAK_DEPTH)):
        lo = ands * 1 / 8 / 1024
        hi = ands * 3 / 8 / 1024
        print(f"| {label} | {ands:,} ANDs | {depth:,} | {lo:.1f}–{hi:.1f} KiB (3–4 party); "
              f"{ands * 8 / 8 / 1024:.0f}–{ands * 24 / 8 / 1024:.0f} KiB (Shamir/GF(2^8)) |")
    print()


def dkg_table(steps_per_slot=46 * 7, label="set A (Poseidon)"):
    mults_slot = steps_per_slot * POSEIDON["ops"]
    print(f"## Dealer-free DKG, {label}: {steps_per_slot} chain steps/slot/key = {mults_slot:,} mults\n")
    spans = {"minimum key (2^17 slots ≈ 6 days)": 2 ** 17, "1 year": SLOTS_PER_YEAR,
             "5 years": 5 * SLOTS_PER_YEAR, "full lifetime 2^32 (≈544 y)": 2 ** 32}
    print("| key covers | mults/validator | " + " | ".join(ASSUME_BYTES_PER_MULT) + " |")
    print("|---|---|" + "---|" * len(ASSUME_BYTES_PER_MULT))
    for name, slots in spans.items():
        m = KEYS_PER_VALIDATOR * slots * mults_slot
        cells = []
        for bpm in ASSUME_BYTES_PER_MULT.values():
            b = m * bpm
            cells.append(f"{b / 1e12:,.1f} TB · {fmt_t(b / 125e6)} @1G · {fmt_t(b / 1.25e9)} @10G")
        print(f"| {name} | {m:.1e} | " + " | ".join(cells) + " |")
    per_year = KEYS_PER_VALIDATOR * SLOTS_PER_YEAR * mults_slot
    print("\nAmortised per validator, per node: " + ", ".join(
        f"{per_year * bpm * 8 / (365.25 * 86400) / 1e6:.1f} Mbps ({k.split(' (')[0]})" for k, bpm in ASSUME_BYTES_PER_MULT.items()))
    print(f"Rounds for the whole DKG if fully parallel: {7 * POSEIDON['depth_lo']}–{7 * POSEIDON['depth_hi']} "
          f"(7 chain steps x per-hash depth), i.e. seconds of latency, not days\n")


def blake_dkg_factor():
    """Like-for-like (same security setting) bandwidth ratio of BLAKE2s to Poseidon per chain step."""
    p_bits = POSEIDON["ops"] * 31  # one 31-bit element per mult per party, scaled identically to AND bits below
    lo, hi = BLAKE_RIPPLE_AND / p_bits, BLAKE_PREFIX_AND / p_bits
    print(f"BLAKE2s vs Poseidon, DKG bandwidth (same security setting): ×{lo:.1f}–×{hi:.1f} with 3–4 party "
          f"replicated Boolean MPC; ×{lo * 8:.0f}–×{hi * 8:.0f} if ANDs need Shamir over GF(2^8) (larger n)")
    print(f"BLAKE2s DKG rounds: {7 * BLAKE_PREFIX_DEPTH:,}–{7 * BLAKE_RIPPLE_DEPTH:,} "
          f"(≈ {7 * BLAKE_PREFIX_DEPTH * 0.05 / 60:.0f}–{7 * BLAKE_RIPPLE_DEPTH * 0.05 / 60:.0f} min at 50 ms RTT)\n")


def online_table():
    print("## Moving per-slot work into MPC (latency budget ≈ 0.8 s: attest at 0.8 s, aggregators at 1.6 s)\n")
    print("| candidate | rounds | wall-clock at 20–100 ms RTT | per-party wire per signature | verdict |")
    print("|---|---|---|---|---|")
    pd = (7 * POSEIDON["depth_lo"], 7 * POSEIDON["depth_hi"])
    print(f"| sign in MPC, Poseidon chains (no PRAWNS) | {pd[0]}–{pd[1]} | "
          f"{pd[0] * 0.02:.0f}–{pd[1] * 0.1:.0f} s | {200 * POSEIDON['ops'] * 4 / 1024:.0f}–{200 * POSEIDON['ops'] * 31 / 1024:.0f} KiB | ✗ misses the slot |")
    bd = (7 * BLAKE_PREFIX_DEPTH, 7 * BLAKE_RIPPLE_DEPTH)
    print(f"| sign in MPC, BLAKE2s chains (no PRAWNS) | {bd[0]:,}–{bd[1]:,} | "
          f"{bd[0] * 0.02:.0f}–{bd[1] * 0.1:,.0f} s | {195 * BLAKE_RIPPLE_AND / 8 / 1024:,.0f}+ KiB | ✗✗ |")
    print("| sign with precomputed secret-shared chain values | 1 | 20–100 ms | ~1.5 KiB | ✓ online, but ~10 KiB *secret* "
          "storage per slot per key per node (≈163 GB/validator-year) and the same DKG cost — PRAWNS is the PRF-compressed version of this |")
    a_trials, b_trials = 900, 2 ** 14.85
    print(f"| grind rho in MPC, set A (SHAKE128 PRF, ~{a_trials} trials, parallel) | {KECCAK_DEPTH} | "
          f"{KECCAK_DEPTH * 0.02:.1f}–{KECCAK_DEPTH * 0.1:.1f} s | "
          f"{a_trials * KECCAK_AND / 8 / 1e6:.1f}–{a_trials * KECCAK_AND * 3 / 8 / 1e6:.0f} MB | ⚠ borderline |")
    print(f"| grind rho in MPC, set B (BLAKE2s, ~2^14.85 trials) | {BLAKE_PREFIX_DEPTH}+ | ≥{BLAKE_PREFIX_DEPTH * 0.02:.0f} s | "
          f"{b_trials * BLAKE_RIPPLE_AND / 8 / 1e6:,.0f}+ MB (≈{b_trials * BLAKE_RIPPLE_AND / 4 / 1e6:,.0f} Mbps per validator) | ✗ |")
    print("| PRAWNS signing (PRF shares, no hashing on secrets) | 1 (+1–2 to agree rho) | 20–300 ms | ~1.5 KiB | ✓ |\n")


def storage():
    cell = 46 * 7 * 8 * 4
    print(f"## Combiner public table (cpk): {cell / 1024:.1f} KiB per slot per key, "
          f"{KEYS_PER_VALIDATOR * cell * SLOTS_PER_YEAR / 1e9:.0f} GB per validator-year (public, incompressible)\n")



# ---- BLAKE2s world (draft leanSig set B: 42 chains x 7 steps, 128-bit digests) -------------------------------
SET_B_STEPS = 42 * 7
ASSUME_BLAKE2S_PER_CORE = 5e6        # plaintext BLAKE2s compressions per second per core (~200 ns), assumption
ASSUME_BITS_PER_AND_3PC = (1, 3)     # 3-4 party replicated Boolean MPC, semi-honest .. malicious


def blake_world():
    print("## BLAKE2s world (draft set B): dealer-free MPC DKG vs a black-box (insecure) DKG\n")
    print("| key covers | ANDs / validator | MPC traffic per node | MPC time @1 Gbps | @10 Gbps | "
          "black-box (insecure) compute on one 16-core box |")
    print("|---|---|---|---|---|---|")
    for name, slots in (("1 day (daily keys, Extremely Lean Chain; smaller tree)", 21600), ("≈ 6 days (minimum key)", 2 ** 17), ("12 months", SLOTS_PER_YEAR),
                        ("18 months", int(1.5 * SLOTS_PER_YEAR)), ("5 years", 5 * SLOTS_PER_YEAR)):
        comps = KEYS_PER_VALIDATOR * slots * SET_B_STEPS
        ands = comps * BLAKE_RIPPLE_AND
        lo, hi = (ands * b / 8 for b in ASSUME_BITS_PER_AND_3PC)
        bb = comps / (ASSUME_BLAKE2S_PER_CORE * 16)
        print(f"| {name} | {ands:.1e} | {fmt_b(lo)}–{fmt_b(hi)} | {fmt_t(lo / 125e6)}–{fmt_t(hi / 125e6)} | "
              f"{fmt_t(lo / 1.25e9)}–{fmt_t(hi / 1.25e9)} | {fmt_t(bb)} |")
    per_year = KEYS_PER_VALIDATOR * SLOTS_PER_YEAR * SET_B_STEPS * BLAKE_RIPPLE_AND
    lo, hi = (per_year * b / (365.25 * 86400) / 1e6 for b in ASSUME_BITS_PER_AND_3PC)
    print(f"\nAmortised (background, continuous): {lo:.1f}–{hi:.1f} Mbps per node per validator. "
          f"Rounds: {7 * BLAKE_PREFIX_DEPTH:,}–{7 * BLAKE_RIPPLE_DEPTH:,} in total (≈ {7 * BLAKE_PREFIX_DEPTH * .05 / 60:.0f}–"
          f"{7 * BLAKE_RIPPLE_DEPTH * .05 / 60:.0f} min at 50 ms) — latency is irrelevant, bandwidth is the cost.\n")


def storage_options():
    cell_a = 46 * 7 * 8 * 4          # Poseidon set A: 8 x 31-bit elements per value
    cell_b = 42 * 7 * 16             # BLAKE2s set B: 128-bit values
    print("## Persistent storage per validator (public combiner table; secret key shares are kilobytes)\n")
    print("| strategy | BLAKE2s (set B) | Poseidon (set A) | validators per 2 TB node (set B, 12-month keys) |")
    print("|---|---|---|---|")
    yr = KEYS_PER_VALIDATOR * SLOTS_PER_YEAR
    full_b, full_a = yr * cell_b, yr * cell_a
    rows = [("every node stores the whole year", full_b, full_a, 1.0),
            ("only f+1 combiner replicas (n=4,f=1 → ½ of nodes)", full_b / 2, full_a / 2, 0.5),
            ("only f+1 replicas (n=7,f=2 → 3/7 of nodes)", full_b * 3 / 7, full_a * 3 / 7, 3 / 7)]
    for label, b, a, _ in rows:
        print(f"| {label} | {b / 1e9:.0f} GB | {a / 1e9:.0f} GB | {2e12 / b:.0f} |")
    for n, f in ((4, 1), (7, 2), (10, 3)):
        k = n - f
        print(f"| Reed–Solomon across the cluster (n={n}, f={f}: any {k} shards rebuild; Merkle-committed shards) | "
              f"{full_b / k / 1e9:.0f} GB | {full_a / k / 1e9:.0f} GB | {2e12 / (full_b / k):.0f} |")
    win = 2 * 2 ** 16 * KEYS_PER_VALIDATOR
    print(f"| untrusted object store + local prefetch of 2 × 2^16-slot windows (≈6 days) | {win * cell_b / 1e9:.1f} GB local "
          f"(+{full_b / 1e9:.0f} GB remote, ≈${full_b / 1e9 * 0.023:.1f}/month at S3 list price) | {win * cell_a / 1e9:.1f} GB local | "
          f"{2e12 / (win * cell_b):,.0f} |")
    print("| regenerate each window by MPC instead of storing | ≈ 0 | ≈ 0 | doubles the MPC traffic |\n")


def daily_storage():
    cell_b = 42 * 7 * 16
    day = KEYS_PER_VALIDATOR * 21600 * cell_b
    print(f"Daily keys: public table per validator per day ≈ {day / 1e6:.0f} MB (BLAKE2s set B).\n")


def table_recovery():
    win_slots = 2 ** 16
    ands = KEYS_PER_VALIDATOR * win_slots * SET_B_STEPS * BLAKE_RIPPLE_AND
    lo, hi = (ands * b / 8 for b in ASSUME_BITS_PER_AND_3PC)
    print(f"Re-deriving a lost 2^16-slot window (~3 days) of the public table by MPC: {fmt_b(lo)}–{fmt_b(hi)} per node, "
          f"{fmt_t(lo / 125e6)}–{fmt_t(hi / 125e6)} at 1 Gbps (needs t nodes' PRF key shares).\n")


if __name__ == "__main__" and "--blake" in __import__("sys").argv:
    blake_world()
    storage_options()
    daily_storage()
    table_recovery()


if __name__ == "__main__" and "--blake" not in __import__("sys").argv:
    hash_table()
    dkg_table()
    dkg_table(42 * 7, "set B chain count (if it stayed Poseidon)")
    blake_dkg_factor()
    online_table()
    storage()
