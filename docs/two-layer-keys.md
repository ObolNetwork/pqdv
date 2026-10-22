# Two-layer validator keys

Ethereum's post-quantum validator key is now a two-layer tree: [EIP-8450](eip-8450.md) registers a leanXMSS key whose
top tree of 2¹⁶ one-time keys certifies 2¹⁶ bottom trees. We had argued for this structure because it makes threshold
(distributed) validators practical. This page explains it, how a DV runs it, and what it costs. Numbers are for
EIP-8450's parameters (Keccak-256, 58 chains of 3 steps, 16-byte values) and come from
`tools/cost_model.py --primary`.

## 1. The idea

| | single tree | two layers (EIP-8450) |
|---|---|---|
| public key commits to | every one-time key in the key's range | the top tree only |
| top layer | — | 2¹⁶ one-time keys; top key *b* signs the root of bottom tree *b*, and nothing else |
| bottom layer | — | 2¹⁶ trees of 2¹⁶ one-time keys, each built before its first use |
| lifetime | 2³² leaves, but key generation covers only a chosen range | 2³² leaves, nothing chosen up front |
| key generation (single signer) | 2³² one-time keys, about 9 × 10¹¹ Keccak-f | 2¹⁶ one-time keys, seconds |

This is classic multi-tree XMSS (XMSS^MT) with two layers. One key signs every duty; the signer chooses which leaf
index each message uses, and the signature carries it.

## 2. Two ways to verify

| | per-slot signature | verification (Keccak-f) | protocol cost |
|---|---|---|---|
| Flat tree of height 32 | 1,460 B | 109 | none, but key generation is infeasible |
| **A. Stateless (EIP-8450):** every signature carries the bottom signature and the top certification | **2,404 B** | **186** | none beyond the signature |
| B. Certified windows: each bottom root is registered once; signatures carry one layer | ~1,204 B | ~93 | about sixteen certifications per block at a million validators |

- **EIP-8450 chose A.** It avoids per-block certifications at the cost of a 944 B larger signature and about 1.7× the
  permutations to prove.
- **We had proposed B.** For DVs the two are equivalent: the MPC, the storage and the safety rules are identical. Only
  the signature size differs.
- **B as a later version.** It remains a possible later key version (the registry has a version byte), for example
  with certificates checked inside periodic validator proofs (*The Extremely Lean Chain*). It is no longer an ask.

## 3. Why it's better for Ethereum, not just for DVs

- **Key generation in seconds for everyone.** A key needs only the top tree, about 1.4 × 10⁷ Keccak-f, instead of every
  leaf in an activation range.
- **No lifetime decision, small secret state.** No activation interval. A signer holds at most the top tree and one
  bottom tree.
- **A cold root.** The long-lived top key signs once per bottom tree. Its certification can be computed and stored when
  the tree is built, so the top secrets can stay offline. A compromised hot machine exposes the bottom trees it holds,
  not the validator's whole life.
- **No forced single point of failure.** Without this structure, a post-quantum validator key must live whole on one
  machine. Two layers let a cluster generate and use keys that no machine ever holds.

## 4. Safety rules

1. **Each top key certifies exactly one bottom root.** Certifying two different roots under one top key is a leaf
   reuse and lets an attacker certify a bottom tree of their own: a full key compromise. EIP-8450 enforces it by
   deterministic derivation from a seed. A DV enforces the same outcome by agreeing the root by consensus and keeping
   a durable "tree *b* certified" record before releasing any signature in it.
2. **Each leaf index signs at most one message.** The proof of possession owns leaf 0.
3. **Domain separation.** Every hash call carries the key's public parameter and a 16-byte address that names the
   layer, key, chain and step.
4. **Timeliness.** A bottom tree must exist before its first leaf is needed. A late tree costs that tree's duties
   (liveness), never safety.

## 5. The DV design

**Top layer: secret shares.**
- One MPC at key generation computes the top layer's one-time keys. Nodes keep **Shamir shares** of each chain's
  positions 0–2, about 2.8 KB per top key.
- **The top-range trick.** Only top keys that will certify a tree need to be real; the rest can be random filler,
  since a filler leaf has no preimage and can't be signed. With a 2¹² range from today's slot (≥ 34 years at 4 s slots
  with one leaf per slot), registration costs 1/16 of the full top tree, and shares take 11 MB per validator.
- **Certifying tree *b*:** the cluster agrees the root (QBFT), then each node opens its shares of the 58 chain values
  the root's codeword selects. That's one round, off the critical path.
- **Operator changes:** a standard Shamir reshare of the stored shares. Same registered key, same validator, no exit.
  This is why the top layer uses shares rather than the hash-based PRAWNS PRF, which can't be reshared without changing
  its outputs.

**Bottom layer: PRAWNS, one tree ahead.**
- Before a tree is needed, the current operators run an MPC that builds it:
  - fresh hash-based PRAWNS PRF keys (kilobytes);
  - the public table of two masked middle values and the end per chain (182 MB per tree).
- **Per-message signing** is non-interactive PRAWNS (see [`prawns.md`](prawns.md)), with randomness
  ρ = threshold-PRF(key, message) + i. The leanXMSS threshold sketch uses the same construction.
- **Operator changes** take effect at the next tree with no extra work.

**Leaf allocation: dense.**
- **Attestations:** synchronized by attestation period.
- **Every other duty:** counter ranges, one per duty type, with the index decided by consensus.
- **Why it matters:** this keeps one leaf per signature. Fixed per-slot schedules multiply DV key generation by up to
  128× ([EIP-8450 notes](eip-8450.md#issue-1-leaf-allocation-sets-the-dvs-key-generation-cost)).

**Why key generation must be MPC, on both layers.** Hashing secret chain values in the clear leaks enough for a
minority to forge (Kondi–Kumar; our numbers in [`prawns.md`](prawns.md) §5.1).

## 6. Costs (per validator, per node)

3–4-party replicated Boolean MPC at 1–3 bits per AND gate; 174 Keccak-f per one-time key at 38,400 ANDs each:

| step | MPC traffic | at 200 Mbps | at 1 Gbps |
|---|---|---|---|
| **Registration:** 2¹² top range + proof of possession | 3.4–10 GB | **2–7 min** | 27–82 s |
| Registration: full 2¹⁶ top tree + proof of possession | 55–164 GB | 36–109 min | 7–22 min |
| **Each bottom tree**, built one ahead | 55–164 GB | **36–109 min** | 7–22 min |

How often a bottom tree is needed with dense allocation:

| duty cadence | one tree lasts | average load | validators per node on half of 200 Mbps |
|---|---|---|---|
| attest once per epoch, 12 s (today) | ~146 days | 0.04–0.1 Mbps | ~1,000–2,900 |
| attest every slot, 12 s | 9.1 days | 0.6–1.7 Mbps | 60–180 |
| attest every slot, 4 s (lean) | 3.0 days | 1.7–5 Mbps | 20–60 |

- **Storage:**
  - top-layer shares: 11 MB with the range, 182 MB for the full tree;
  - bottom-layer tables: 182 MB per tree, two held.

  **About 0.4–0.55 GB per validator per node.**
- **Rounds:** AND-depth 24 per Keccak-f, so a whole tree is about 72 rounds deep when run in parallel. Latency doesn't
  matter.
- **Assumptions and the BLAKE2s comparison:** [`dkg-and-mpc-costs.md`](dkg-and-mpc-costs.md).

## 7. Prior art

- **leanXMSS** (leanVM `doc/lean_xmss`): the scheme EIP-8450 registers, with a Lean 4 proof of 127-bit classical
  security and a threshold-signing sketch after PRAWNS.
- **leanSig split its tree only to save memory:** "we first generate all bottom trees and store their roots, then we
  generate the top tree just from their roots" (`leanSig/src/signature/generalized_xmss.rs`). In leanXMSS, the top
  tree's leaves are one-time keys that *sign* bottom roots.
- **leanSPHINCS** (leanVM) is a 3-layer hypertree with aggregation-guest verification and Lean proofs.

## 8. Open questions

- **The switch fork's duty cadence:** whether attestations stay once per epoch or move to every slot. It sets the DV's
  MPC rate by about 16×.
- **The security proof:** the composition of two-layer leanXMSS with the PRAWNS threshold layer and threshold-derived
  randomness. Lean proofs could extend the existing leanXMSS ones.
- **Key-authorized replacement:** a registered key signing its successor (see [EIP-8450 notes](eip-8450.md), issue 4).
