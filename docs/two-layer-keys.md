# Two-layer validator keys

Our proposed key structure for lean Ethereum, developed in discussion with EF researchers. It makes threshold
(distributed) validators practical, and it improves signature size, key generation and key security for every
validator. Numbers are for the draft leanSig parameters (BLAKE2s, 42 chains of 7 steps, 128-bit values) and come from
`tools/cost_model.py --primary`.

## 1. The idea

| | single tree (today) | two layers |
|---|---|---|
| public key commits to | every slot's one-time key | the top layer only |
| top layer | — | 2¹⁶ one-time keys; key *w* certifies window *w* |
| bottom layer | — | one tree of 2¹⁶ one-time keys per window (~3 days), built when needed |
| lifetime | 2³² slots, but key generation covers only a chosen activation range | 2¹⁶ windows × 2¹⁶ slots = 2³² slots, nothing chosen up front |

This is the classic multi-tree XMSS (XMSS^MT) construction with two layers. One certificate per window can cover
both of a validator's bottom trees, attestation and proposal, by signing a hash of both roots.

## 2. Two ways to verify

| | per-slot signature | verification (compressions) | protocol change |
|---|---|---|---|
| Today | 1,208 B (one-time signature + 32-level path) | ~144 | — |
| **A. Stateless:** each signature carries the bottom signature and the window's certificate | ~1,904 B (+58%) | ~256 (~1.8×) | signature scheme only |
| **B. Certified windows (proposed):** the certificate is registered once per window; signatures reference the window root | **~952 B (−21%)** | **~128 (−11%)** | one certificate per validator per window, plus a current-root record |

**Option B is our ask.**
- **Cost per certificate:** about 950 B, verified once. That's 1/65,536 of the per-slot cost when amortised.
- **Chain-wide:** at 1M validators, ~0.95 GB of certificates every ~3 days (≈ 3.6 KB/s), aggregated by proofs like any
  other signature.
- **Where it can live:**
  - in an on-chain registry of each validator's current window root (16 bytes of state); or
  - inside periodic validator proofs such as daily balance and key-registration proofs (*The Extremely Lean Chain*),
    where it also keeps windows unlinkable.

Option A is a fallback if consensus changes are off the table. It is a pure signature-scheme change, but it works
against the goal of minimising verification hashing for aggregation.

## 3. Why it's better for Ethereum, not just for DVs

- **Smaller, cheaper signatures.** Every per-slot signature drops a 16-level path: 21% smaller and 11% cheaper to
  verify inside aggregation proofs.
- **Key generation in minutes for everyone.** A key needs the top layer plus one window, about 4 × 10⁷ hashes,
  instead of every slot in an activation range (today: "1–2 hours" for 2¹⁸ slots, "~days" for a full tree).
- **No lifetime decision, small secret state.** No activation interval, and no multi-gigabyte secret key.
- **A cold root.** The long-lived top key signs once per ~3 days and can stay offline. A compromised hot machine
  exposes only the windows it holds (about 6 days), not the validator's whole life. The attacker can't certify new
  windows.
- **No forced single point of failure.** Without a structure like this, a post-quantum validator key must live
  whole on one machine. Two layers let a cluster generate and use keys that no machine ever holds.

## 4. Safety rules

1. **Each top-layer key certifies exactly one window.** Its index is the window number. Certifying two different
   roots for one window would let an attacker certify a bottom tree of their own: a full key compromise, worse than a
   double vote. This needs slashing-style protection (a durable "window certified" record), and ideally a slashing
   condition for two certificates with the same index.
2. **Each bottom-layer key signs once per slot**, as today.
3. **Domain separation.** A certificate binds (validator, window index, root), so it can't be replayed for another
   window or validator.
4. **Timeliness.** The certificate must be registered before its window starts, with a grace period. A late window
   costs that window's duties (liveness), never safety.

## 5. The DV design on two-layer keys

**Top layer: kept as secret shares.**
- One MPC at setup computes all 2¹⁶ top-layer one-time keys. Nodes keep **Shamir shares** of every chain value, about
  0.31 GB per validator per node, for life.
- Certifying window *w*: the cluster agrees the window root (QBFT), then each node opens its shares of the 42 chain
  values that root's encoding selects. That's one round, entirely off the slot's critical path.
- **Operator changes:** a standard Shamir reshare of the stored shares to the new operator set. Same public key, same
  validator, no exit.
- Why shares rather than PRAWNS here: latency doesn't matter for a once-per-window signature, and shares are trivially
  reshareable. The hash-based PRAWNS PRF can't be reshared without changing its outputs.

**Bottom layer: PRAWNS, rebuilt every window.**
- One window ahead, the current operators run an MPC that builds the next bottom trees: fresh hash-based PRAWNS PRF
  keys (kilobytes) and the masked public table (~0.31 GB per tree).
- Per-slot signing is non-interactive PRAWNS (see [`prawns.md`](prawns.md)), with randomness
  ρ = threshold-PRF(key, message) + i.
- Because the bottom layer is rebuilt every window, an operator change takes effect at the next window boundary with
  no extra work.

**Why the key generation must be MPC, on both layers.** Hashing secret chain values in the clear leaks enough for a
minority to forge (Kondi–Kumar; our numbers in [`prawns.md`](prawns.md) §5.1). The top layer is no exception.

## 6. Costs (per validator, per node)

| step | MPC traffic | at 200 Mbps | at 1 Gbps |
|---|---|---|---|
| Up front: top layer + first windows (attestation + proposal) | 146–437 GB | 1.6–4.9 h | 19–58 min |
| Every ~3 days: next windows (attestation + proposal) | 97–291 GB | 1.1–3.2 h | 13–39 min |
| Every ~3 days, proposal key indexed by duty | 49–146 GB | 32–97 min | 6–19 min |

- **Average:** 3–9 Mbps per validator (1.5–4.4 with duty-indexed proposal keys).
- **Capacity with half a 200 Mbps link:** 11–34 validators per node (22–67 with duty-indexed proposal keys).
- **Storage:** ~1.5 GB per validator per node.
- **Assumptions:** 3–4-party replicated Boolean MPC at 1–3 bits per AND gate, and 20,160 ANDs per BLAKE2s
  compression. See [`dkg-and-mpc-costs.md`](dkg-and-mpc-costs.md).

## 7. Tuning the split

| top / bottom | window | up front at 200 Mbps | per window at 200 Mbps |
|---|---|---|---|
| **2¹⁶ / 2¹⁶ (proposed)** | ~3 days | 1.6–4.9 h | 1.1–3.2 h |
| 2²⁰ / 2¹² | ~4.6 h | 8.7–26 h | 4–12 min |
| 2¹² / 2²⁰ | ~48 days | 17–52 h | 17–52 h |

The balanced split keeps both the one-off and the recurring job to a few hours. Smaller windows mean smaller jobs but
a much bigger one-off top layer.

## 8. Prior art in the lean repos

- **leanSig already splits its tree**, but only to save memory: "During key generation, we first generate all bottom
  trees and store their roots, then we generate the top tree just from their roots"
  (`leanSig/src/signature/generalized_xmss.rs`). Two-layer keys make the top tree's leaves one-time keys that *sign*
  bottom roots later.
- **leanVM already implements a hypertree.** leanSPHINCS, the account signature, is a 3-layer hypertree with a Rust
  implementation, aggregation-guest verification and Lean proofs (`leanVM/crates/sphincs`, `leanVM/formal/sphincs`).
- **Key generation time is a known pain point:** "KeyGen ~days for full tree (~64 GiB sk)" (lean week, KeyGen & API
  talk), which is why activation intervals exist.
- **The design goal to respect:** minimise verification hashing for aggregation (pq-interop meeting 01). Option B
  improves it; option A works against it.

## 9. Open questions

- Certificate placement (registry vs periodic proofs) and its interaction with validator privacy.
- A slashing condition for double certificates.
- The security proof: two-layer XMSS composition is standard, but it needs combining with the PRAWNS threshold layer
  and threshold-derived randomness. Formal proofs in Lean could extend the existing XMSS and hypertree work.
