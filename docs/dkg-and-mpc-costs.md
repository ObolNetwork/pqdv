# DKG and MPC cost model for threshold leanSig

Everything here is reproducible with `python3 tools/cost_model.py`. Every input is either sourced (leanSig/leanSpec
code, this repo's 2025 benchmarks) or a labelled assumption. Treat the outputs as **order-of-magnitude** estimates:
there's no implementation of the DKG described here yet.

## 1. What has to happen inside MPC, and what doesn't

| Work | Secret? | Where it runs |
|---|---|---|
| chain starts (PRF outputs) | yes | **locally**, with `F_hash`: each node computes its own PRF terms, giving additive shares for free |
| 7 chain steps on each of 46 chains, per slot per key | yes (every intermediate value is a future signature value) | **MPC**: the dominant cost |
| masks for the public table (`cpk`) | yes | locally (same as chain starts), then *open* masked values |
| chain tops, one-time public key (leaf) hash, Merkle tree | no (public by design) | **in the clear**, after opening the tops |
| per-slot signing (PRAWNS) | PRF shares | locally: no hashing of secrets at all |

So the DKG is 46 × 7 = **322 hash calls on secret data per slot per key** (leanSig devnet parameters), × 2 keys per
validator, × the number of slots the key covers. Kondi–Kumar show this can't be avoided by hashing in the clear
(see [`prawns.md`](prawns.md) §5).

**Latency vs bandwidth.** Chains for different slots and different chains are independent, so a well-built DKG runs
them all in parallel. It needs only 7 × (depth of one hash) rounds: **196–392 rounds for Poseidon**, seconds of
latency. The 2025 benchmarks in [`../doc/`](../doc/) ran keys sequentially and were latency-bound (4–12 days
extrapolated); that's an implementation artifact, not the floor. The real floor is **bandwidth**: total
multiplications × bytes per multiplication per node.

## 2. Inputs

- **Poseidon1, width 16, over KoalaBear** (leanSig devnets): 8 full + 20 partial rounds, S-box x³. That is
  148 S-boxes = 296 multiplications per call, depth 28 (one-round cube with cube triples) to 56 (plain Beaver).
  Poseidon2 at width 16 has the same S-box count, so this repo's 2025 Poseidon2 numbers (296 triples, depth 28) carry
  over.
- **BLAKE2s compression** (leanSig draft spec, "placeholder"): 10 rounds × 8 G functions. Each G is two 3-operand and
  two 2-operand 32-bit additions; XORs and rotations are free in Boolean MPC. Two adder designs:
  - ripple-carry (31 ANDs, depth 31) with a carry-save layer: **20,160 ANDs, depth 2,520**;
  - parallel-prefix: **~87k ANDs, depth ~520**.
- **Keccak-f[1600]** (SHAKE128, leanSig devnets' PRF for chain starts and ρ): 1,600 ANDs per round × 24 rounds,
  depth 24.
- **Bytes per multiplication per node, including preprocessing** (assumptions):
  - ~4 B: best 3–4-party protocols (replicated sharing, "Fantastic Four"-style, about one field element per mult);
  - 13 B: semi-honest Shamir, measured (ATLAS in this repo's 2025 MP-SPDZ benchmarks, 5 parties);
  - 31 B: malicious Shamir, measured (same benchmarks).
- **Bits per AND per node:** 1–3 for 3–4-party replicated Boolean MPC (semi-honest to malicious); 8–24 when Shamir
  over GF(2⁸) is needed (larger committees).
- **Slots:** 4 s; 7,889,400 per year; 2 keys per validator.

## 3. Results: two-layer keys (the primary scenario)

With [two-layer keys](two-layer-keys.md) and window certificates, a DV runs one MPC at setup (top layer + first
window) and then one per ~3-day window, each built a window ahead. Per validator, per node, BLAKE2s, 3–4-party
Boolean MPC at 1–3 bits per AND gate:


| step | MPC traffic | at 200 Mbps | at 1 Gbps |
|---|---|---|---|
| Up front: top tree + first bottom trees (attestation + proposal) | 146 GB–437 GB | 97 min–4.9 h | 19 min–58 min |
| Every ~3 days: next bottom trees (attestation + proposal) | 97 GB–291 GB | 65 min–3.2 h | 13 min–39 min |
| Every ~3 days, proposal key indexed by duty (≈ one bottom tree) | 49 GB–146 GB | 32 min–97 min | 6 min–19 min |

Average, spread across the window: 3.0–8.9 Mbps per validator per node (1.5–4.4 with duty-indexed proposal keys).
Validators per node using half of a 200 Mbps link: 11–34 (22–67 with duty-indexed proposal keys).
Validators per node using half of a 1 Gbps link: 56–169 (112–337 with duty-indexed proposal keys).

Storage per validator per node: top-layer secret shares 0.31 GB (for life) + bottom-layer public tables for two windows, two keys 1.23 GB ≈ 1.5 GB.
Per-slot signature 952 B (~128 compressions); once-per-window certificate ~950 B. Today: 1,208 B (~144).

**Planning figure: 200 Mbps per node.** A commodity link handles the one-off in an afternoon and the per-window job
in 1–3 hours. 1 Gbps makes both trivial.

## 4. Results: single-layer keys (fallback), BLAKE2s

Ethereum's direction is a classic hash proven with fast batch provers (e.g. Flock), so key generation becomes a
**Boolean** MPC over BLAKE2s (draft leanSig set B: 42 chains × 7 steps, 128-bit values).
- **Inputs:** 20,160 ANDs per compression (ripple-carry adders; parallel-prefix adders cut depth at about 4× the
  ANDs), and 1–3 bits per AND per node for 3–4-party replicated sharing (semi-honest to malicious).
- **The black-box column** is plaintext hashing at about 5 M BLAKE2s compressions per second per core. That's what an
  *insecure* DKG would cost (see [`prawns.md`](prawns.md) §5.1).

### BLAKE2s key generation (draft set B): dealer-free MPC DKG vs a black-box (insecure) DKG

| key covers | ANDs / validator | MPC traffic per node | MPC time @1 Gbps | @10 Gbps | black-box (insecure) compute on one 16-core box |
|---|---|---|---|---|---|
| 1 day (daily keys, Extremely Lean Chain; smaller tree) | 2.6e+11 | 32 GB–96 GB | 4 min–13 min | 26 s–77 s | 0 s |
| ≈ 6 days (minimum key) | 1.6e+12 | 194 GB–583 GB | 26 min–78 min | 3 min–8 min | 1 s |
| 12 months | 9.4e+13 | 11.7 TB–35.1 TB | 26.0 h–3.2 d | 2.6 h–7.8 h | 58 s |
| 18 months | 1.4e+14 | 17.5 TB–52.6 TB | 39.0 h–4.9 d | 3.9 h–11.7 h | 87 s |
| 5 years | 4.7e+14 | 58.5 TB–175.4 TB | 5.4 d–16.2 d | 13.0 h–39.0 h | 5 min |

Amortised (background, continuous): 3.0–8.9 Mbps per node per validator. Rounds: 3,640–17,640 in total (≈ 3–15 min at 50 ms) — latency is irrelevant, bandwidth is the cost.

### Persistent storage per validator (public combiner table; secret key shares are kilobytes)

| strategy | BLAKE2s (set B) | Poseidon (set A) | validators per 2 TB node (set B, 12-month keys) |
|---|---|---|---|
| every node stores the whole year | 74 GB | 163 GB | 27 |
| only f+1 combiner replicas (n=4,f=1 → ½ of nodes) | 37 GB | 81 GB | 54 |
| only f+1 replicas (n=7,f=2 → 3/7 of nodes) | 32 GB | 70 GB | 63 |
| Reed–Solomon across the cluster (n=4, f=1: any 3 shards rebuild; Merkle-committed shards) | 25 GB | 54 GB | 81 |
| Reed–Solomon across the cluster (n=7, f=2: any 5 shards rebuild; Merkle-committed shards) | 15 GB | 33 GB | 135 |
| Reed–Solomon across the cluster (n=10, f=3: any 7 shards rebuild; Merkle-committed shards) | 11 GB | 23 GB | 189 |
| untrusted object store + local prefetch of 2 × 2^16-slot windows (≈6 days) | 1.2 GB local (+74 GB remote, ≈$1.7/month at S3 list price) | 2.7 GB local | 1,622 |
| regenerate each window by MPC instead of storing | ≈ 0 | ≈ 0 | doubles the MPC traffic |

Daily keys: public table per validator per day ≈ 203 MB (BLAKE2s set B).

Re-deriving a lost 2^16-slot window (~3 days) of the public table by MPC: 97 GB–291 GB per node, 13 min–39 min at 1 Gbps (needs t nodes' PRF key shares).

**Storage notes.**
- **Reed–Solomon:** shards are Merkle-committed (AVID-style) so a Byzantine node can't serve garbage undetected; the
  combiner rebuilds each window ahead of time, keeping decoding off the slot's critical path.
- **Ethereum blobs don't fit:** they are pruned after about 18 days and priced per byte (about 580k blobs per
  validator-year).
- **Losing the table costs liveness only.** It can be rebuilt by rerunning the MPC from any t nodes' PRF key
  shares, and the result is checked against the commitment from key generation.

## 5. Results: Poseidon (if Ethereum kept a zk-friendly hash)

### Per hash call inside MPC (one chain step)

| hash | non-linear ops | MPC rounds (depth) | wire per party |
|---|---|---|---|
| Poseidon1-16 (KoalaBear, x^3) | 296 field mults | 28–56 | 1.2–9.0 KiB |
| BLAKE2s, ripple adders | 20,160 ANDs | 2,520 | 2.5–7.4 KiB (3–4 party); 20–59 KiB (Shamir/GF(2^8)) |
| BLAKE2s, prefix adders | 87,040 ANDs | 520 | 10.6–31.9 KiB (3–4 party); 85–255 KiB (Shamir/GF(2^8)) |
| Keccak-f[1600] (SHAKE128) | 38,400 ANDs | 24 | 4.7–14.1 KiB (3–4 party); 38–112 KiB (Shamir/GF(2^8)) |

### Dealer-free DKG, set A (Poseidon): 322 chain steps/slot/key = 95,312 mults

| key covers | mults/validator | best 3-4 party (replicated / Fantastic-Four-like) | semi-honest Shamir, measured (ATLAS in pqdv) | malicious Shamir, measured (pqdv) |
|---|---|---|---|---|
| minimum key (2^17 slots ≈ 6 days) | 2.5e+10 | 0.1 TB · 13 min @1G · 80 s @10G | 0.3 TB · 42 min @1G · 4 min @10G | 0.8 TB · 105 min @1G · 10 min @10G |
| 1 year | 1.5e+12 | 6.0 TB · 13.4 h @1G · 80 min @10G | 19.0 TB · 42.2 h @1G · 4.2 h @10G | 47.4 TB · 4.4 d @1G · 10.5 h @10G |
| 5 years | 7.5e+12 | 30.1 TB · 66.8 h @1G · 6.7 h @10G | 94.8 TB · 8.8 d @1G · 21.1 h @10G | 236.9 TB · 21.9 d @1G · 52.6 h @10G |
| full lifetime 2^32 (≈544 y) | 8.2e+14 | 3,274.9 TB · 303.2 d @1G · 30.3 d @10G | 10,326.8 TB · 956.2 d @1G · 95.6 d @10G | 25,789.3 TB · 2387.9 d @1G · 238.8 d @10G |

Amortised per validator, per node: 1.5 Mbps (best 3-4 party), 4.8 Mbps (semi-honest Shamir, measured), 12.0 Mbps (malicious Shamir, measured)
Rounds for the whole DKG if fully parallel: 196–392 (7 chain steps x per-hash depth), i.e. seconds of latency, not days

### Dealer-free DKG, set B chain count (if it stayed Poseidon): 294 chain steps/slot/key = 87,024 mults

| key covers | mults/validator | best 3-4 party (replicated / Fantastic-Four-like) | semi-honest Shamir, measured (ATLAS in pqdv) | malicious Shamir, measured (pqdv) |
|---|---|---|---|---|
| minimum key (2^17 slots ≈ 6 days) | 2.3e+10 | 0.1 TB · 12 min @1G · 73 s @10G | 0.3 TB · 38 min @1G · 4 min @10G | 0.7 TB · 96 min @1G · 10 min @10G |
| 1 year | 1.4e+12 | 5.5 TB · 12.2 h @1G · 73 min @10G | 17.3 TB · 38.5 h @1G · 3.8 h @10G | 43.3 TB · 4.0 d @1G · 9.6 h @10G |
| 5 years | 6.9e+12 | 27.5 TB · 61.0 h @1G · 6.1 h @10G | 86.6 TB · 8.0 d @1G · 19.2 h @10G | 216.3 TB · 20.0 d @1G · 48.1 h @10G |
| full lifetime 2^32 (≈544 y) | 7.5e+14 | 2,990.1 TB · 276.9 d @1G · 27.7 d @10G | 9,428.9 TB · 873.0 d @1G · 87.3 d @10G | 23,546.7 TB · 2180.3 d @1G · 218.0 d @10G |

Amortised per validator, per node: 1.4 Mbps (best 3-4 party), 4.4 Mbps (semi-honest Shamir, measured), 11.0 Mbps (malicious Shamir, measured)
Rounds for the whole DKG if fully parallel: 196–392 (7 chain steps x per-hash depth), i.e. seconds of latency, not days

BLAKE2s vs Poseidon, DKG bandwidth (same security setting): ×2.2–×9.5 with 3–4 party replicated Boolean MPC; ×18–×76 if ANDs need Shamir over GF(2^8) (larger n)
BLAKE2s DKG rounds: 3,640–17,640 (≈ 3–15 min at 50 ms RTT)

### Moving per-slot work into MPC (both hashes) (latency budget ≈ 0.8 s: attest at 0.8 s, aggregators at 1.6 s)

| candidate | rounds | wall-clock at 20–100 ms RTT | per-party wire per signature | verdict |
|---|---|---|---|---|
| sign in MPC, Poseidon chains (no PRAWNS) | 196–392 | 4–39 s | 231–1792 KiB | ✗ misses the slot |
| sign in MPC, BLAKE2s chains (no PRAWNS) | 3,640–17,640 | 73–1,764 s | 480+ KiB | ✗✗ |
| sign with precomputed secret-shared chain values | 1 | 20–100 ms | ~1.5 KiB | ✓ online, but ~10 KiB *secret* storage per slot per key per node (≈163 GB/validator-year) and the same DKG cost — PRAWNS is the PRF-compressed version of this |
| grind rho in MPC, set A (SHAKE128 PRF, ~900 trials, parallel) | 24 | 0.5–2.4 s | 4.3–13 MB | ⚠ borderline |
| grind rho in MPC, set B (BLAKE2s, ~2^14.85 trials) | 520+ | ≥10 s | 74+ MB (≈149 Mbps per validator) | ✗ |
| PRAWNS signing (PRF shares, no hashing on secrets) | 1 (+1–2 to agree rho) | 20–300 ms | ~1.5 KiB | ✓ |

### Combiner public table (cpk): 10.1 KiB per slot per key, 163 GB per validator-year (public, incompressible)

## 6. Reading the numbers

- **Two-layer keys (expected route).** One-off 1.6–4.9 h at 200 Mbps, then 1.1–3.2 h per ~3-day window, ~1.5 GB of
  storage (§3). Everything below applies only if keys stay single-layer.
- **Single-layer BLAKE2s.** Per validator and node, a 12-month key is 12–35 TB, 26 h – 3.2 days at 1 Gbps, about 3–9 Mbps amortised (§3). The Poseidon bullets below are for comparison.
- **"Minutes, hours or untenable?"** It depends on the key range:
  - **the minimum key (2¹⁷ slots, about 6 days):** minutes;
  - **1-year key:** hours with a good protocol on fast links, days off the shelf;
  - **full 2³² lifetime:** untenable.

  lean consensus has no key rotation today, so the range chosen at DKG is the validator's life.
- **Fleet scale is the real constraint.** About 1.5–12 Mbps per node per validator, continuously amortised. A cluster
  with 50 validators needs 75–600 Mbps of sustained MPC traffic per node just for key material.
- **BLAKE2s vs Poseidon.**
  - **Signing inside MPC:** 10–90× more depth is fatal, but PRAWNS doesn't sign inside MPC.
  - **DKG:** depth adds minutes of latency in total; the real cost is **2–10× more bandwidth** with 3–4 parties, and
    18–76× if the committee forces Shamir over GF(2⁸).
- **Encoding randomness (ρ) must not need MPC.** With BLAKE2s grinding (~2¹⁵ tries) it would cost ~150 Mbps per
  validator, so ρ should be agreed jointly, not derived from the secret seed.
- **Storage.** The public `cpk` table is 10 KiB per slot per key, about 163 GB per validator-year, pseudorandom and so
  incompressible. Alternatives:
  - regenerate it per 2¹⁶-slot window by MPC, which doubles the MPC work but bounds storage;
  - or let each node keep only the windows it might combine.

## 7. What can be precomputed

| Piece | Depends on the key? | When it can run |
|---|---|---|
| MPC correlated randomness (triples, or PRSS + DN07 double sharings) | no | any time, continuously, low priority. With pseudorandom secret sharing (one PRF key per subset of nodes, C(n,t) keys) double sharings cost no traffic, and DN07 degree reduction costs about 2.7–2.9 field elements per node per multiplication (Stoffel's measured formulas; see [`alternatives.md`](alternatives.md)) |
| key generation proper | yes | two-layer: the next window during the current one (1–3 h at 200 Mbps); single-layer: in independent chunks, next year's key during the last month or two |
| the public table | yes (output of key generation) | written once; fetch per window or keep f+1 replicas |
| encoding randomness ρ | per message | commit early, reveal on QBFT messages after the message is agreed |
| signing | per slot | nothing heavy to precompute |

Single-layer only: throttling arithmetic for a 12-month BLAKE2s key built over the final 30 days of the previous key: 12–35 TB per node
→ **36–108 Mbps per validator** (half that over 60 days). Operators with many validators either have the bandwidth,
consolidate, or stagger rotations across the year.

## 8. Levers, biggest first

1. **Protocol: two-layer keys** ([two-layer-keys.md](two-layer-keys.md)), or failing that key rotation or extension. It doesn't reduce total work, but it spreads the DKG into rolling
   per-window runs (about 6.2 × 10⁹ multiplications per key per ~3 days). That bounds lock-in, allows operator changes
   at window boundaries, and removes the "pay for 5 years up front" problem.
2. **Protocol: chain steps per slot.** Cost is linear in v·(2^w − 1), which is 322 for the devnet set and 294 for the
   draft set. Larger w shortens signatures but raises it exponentially.
3. **Protocol: the chain hash.** Poseidon-class is 2–10× cheaper in MPC than BLAKE2s at 3–4 parties. Ethereum is leaning towards BLAKE, so plan for BLAKE: keep the MPC committee at 3–4 nodes (replicated Boolean sharing), and avoid GF(2⁸) Shamir, which costs 8× more.
4. **Protocol choice:**
   - **3–4-party replicated sharing:** about 4 B per mult, versus 31 B for off-the-shelf malicious Shamir;
   - **pseudorandom correlation generators:** could make preprocessing nearly free.
   - Committees larger than 4 need care: the MPC committee must have an honest majority under the cluster's fault
     assumption. A `2f+1` subset works.
5. **Trust: a dealer in a TEE.** Turns the DKG into CPU-hours on one machine (about 5.5 × 10⁹ Poseidon calls per
   validator-year, the same as single-signer key generation) plus share and table distribution. The cost is trust in
   the enclave and in erasure.

## 9. Caveats

- **Bytes per mult.** These come from MP-SPDZ (2025) and literature-level estimates for 3–4-party protocols. A custom
  implementation needs to measure its own.
- **BLAKE2s AND counts** are our own circuit estimates (ripple vs prefix adders). Published circuits may differ by a
  small factor.
- **`F_lat` DKG.** Rounding inside MPC is extra and not modelled.
- **Parameters will move.** leanSig is still in flux: the hash, v and w (see [`leansig.md`](leansig.md)).
