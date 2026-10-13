# pqdv: post-quantum distributed validators

**Distributed validators carry over to post-quantum Ethereum.** This repo shows how: how a cluster signs, how it
makes keys without anyone ever holding them, what it costs, and the few protocol choices that make it smooth.

## TL;DR

- **Threshold signing is solved.** With PRAWNS[^prawns], each node contributes its share alone, with no multi-party
  computation (MPC) and no hashing of secrets at signing time. The combined output is a **standard signature**, so
  aggregation and verification are unchanged. It takes milliseconds of a 4-second slot.
- **Keys are made jointly, in the background.** With **two-layer validator keys**, a long-lived top key certifies a
  fresh signing key every ~3 days. The cluster generates keys by MPC, so no machine ever holds a full key:
  - **up front:** 1.6–4.9 hours per validator at 200 Mbps;
  - **then:** a 1–3-hour background job every ~3 days, about 3–9 Mbps on average;
  - **stored:** about 1.5 GB per validator.

  No key lifetime to pick, and operator changes keep the same validator.
- **Two-layer keys are good for all of Ethereum.** Signatures get 21% smaller and cheaper to aggregate, key
  generation drops to minutes for every validator, and the long-lived key can stay cold.
- **What we ask of lean Ethereum:**
  1. two-layer keys, with each window's key certified once (§7);
  2. bless threshold-derived signing randomness, which works today as an invisible deviation;
  3. keep staking in groups a design goal.
- **Status:** the cryptography exists, the costs are known, and the remaining work is engineering, proofs and spec
  alignment. The [roadmap](#8-roadmap) runs ahead of the post-quantum chain.

---

## 1. Why BLS made distributed validators easy

A BLS key is a number, and everything about it is **linear**. Shamir-split the key and any `t` partial signatures
combine into the signature the public key expects. A distributed key generation (DKG) takes seconds, and thousands of
signatures add up into one. The protocol never needs to know a validator is distributed.

## 2. What changes after the post-quantum switch

Lean Ethereum replaces BLS with **leanSig**, a hash-based signature (generalized XMSS). Proofs replace
pairing-based aggregation.

| | BLS (today) | leanSig (post-quantum) |
|---|---|---|
| Secret | one number | a seed expanding into millions of hash chains |
| Signature | algebraic | reveals points on hash chains, plus a Merkle path |
| State | slashing protection | each slot's one-time key signs once, ever |
| Aggregation | add signatures | a zk proof that many standard signatures verify |
| Threshold signing | algebra | needs a new idea: **PRAWNS** |
| Distributed key generation | seconds | hashing secrets inside MPC: needs a key structure that allows background generation |

Slots are 4 seconds: attest at 0.8 s, aggregators collect at 1.6 s. Every validator attests every slot.

## 3. How a DV signs

![One lean slot](docs/fig/slot.svg)

**PRAWNS** precomputes every hash-chain value at key generation and publishes each one *masked* by a threshold
pseudorandom function (PRF). To sign, nodes send PRF shares for the positions the message selects; a combiner unmasks
those positions and outputs an ordinary leanSig signature. No secret is hashed at signing time, so signing fits the
slot with room to spare.

- **Randomness.** leanSig signatures include a randomizer ρ, normally derived from the full secret key. A DV uses
  ρ = threshold-PRF(key, message) + i, where i is the first value that makes the encoding valid. Nodes attach their PRF
  shares to the QBFT commit messages they already send, so this costs no extra round. It is unbiasable and
  deterministic, and verifiers can't tell it apart.
- **Threshold.** PRAWNS needs `t > (n + f)/2`, which charon's `ceil(2n/3)` already meets.
- **State.** Each node keeps a never-sign-twice record, like today's slashing protection.

Details: [`docs/prawns.md`](docs/prawns.md).

## 4. Two-layer keys, in plain terms

![Two-layer key](docs/fig/keys.svg)

**Today's single-tree key** is a book of 4 billion single-use tickets, one per slot. The public key fingerprints the
whole book, so every ticket must be printed before the key can be published.

**A two-layer key** works like a certificate chain:
- **Top layer:** a small master book of 65,536 single-use stamps. The public key fingerprints only this book.
- **Bottom layer:** every ~3 days, a fresh book of 65,536 tickets, certified once by one master stamp.
- **Validity:** a ticket counts if its book is certified.

Same 2³² slots (~544 years), but only the master book plus the current ticket book ever need to exist.

With the certificate registered once per window ("option B"):

| | today (one tree) | two-layer, certified windows |
|---|---|---|
| Signature per slot | 1,208 B | **952 B (−21%)** |
| Verification per signature (hash compressions) | ~144 | **~128 (−11%)** |
| Extra on-chain data | — | one ~950 B certificate per validator per ~3 days |
| Key generation, any validator | every slot in the activation range (hours to days for long ranges) | top layer + one window (minutes) |
| Key lifetime chosen up front | yes | no |
| Long-lived key | used for every signature | used once per ~3 days, so it can stay **cold** |

Full analysis: [`docs/two-layer-keys.md`](docs/two-layer-keys.md).

## 5. How a DV makes keys

Without a trusted dealer, the hash chains behind each key have to be computed on secret data **inside MPC**. There is
no shortcut: hashing in the clear provably leaks enough for a minority to forge[^kk]. Two-layer keys make that MPC
small and steady:

![Key generation pipeline](docs/fig/pipeline.svg)

Per validator, per node, BLAKE2s, 3–4-party Boolean MPC:

| step | MPC traffic | at 200 Mbps | at 1 Gbps |
|---|---|---|---|
| **Up front:** top layer + first window | 146–437 GB | **1.6–4.9 h** | 19–58 min |
| **Every ~3 days:** next window | 97–291 GB | **1–3 h** | 13–39 min |
| …with proposal keys indexed by duty | 49–146 GB | 32–97 min | 6–19 min |

- **Average load:** 3–9 Mbps per validator per node (1.5–4.4 with duty-indexed proposal keys).
- **Capacity:** using half of a 200 Mbps link, a node supports **11–34 validators** (22–67 with duty-indexed proposal
  keys). At 2048 ETH each, that's roughly 22k–137k ETH per cluster. Five times more on 1 Gbps.
- **Latency doesn't matter.** Every chain is independent, so the whole computation is only a few thousand rounds deep.
  Each window is built one ahead, so a failed job simply retries within the 3 days.
- **Storage:** about 1.5 GB per validator per node:
  - top-layer secret shares, kept for life (~0.3 GB);
  - two windows of signing tables (~1.2 GB).
- **Operator changes:** reshare the top-layer shares (a standard Shamir reshare), and the new operator set builds the
  next window. Same validator, same public key.

Model and assumptions: [`docs/dkg-and-mpc-costs.md`](docs/dkg-and-mpc-costs.md).

## 6. A validator's life

![Lifecycle](docs/fig/lifecycle.svg)

| stage | what happens | resources (per validator, per node) |
|---|---|---|
| Cluster formation | agree config, threshold, operators | as today |
| Key generation | MPC builds the top layer and the first window | 1.6–4.9 h at 200 Mbps |
| Every slot | QBFT → threshold randomness on commits → PRF shares → combine → publish | ~1.5 KiB, milliseconds |
| Every ~3 days | MPC builds the next window; the top key certifies it | 1–3 h at 200 Mbps; ~950 B on-chain |
| Operator change | reshare the top layer; the new set builds the next window | minutes; same validator |
| Always | never-sign-twice records for slots and windows; ~1.5 GB key material | |

## 7. What we ask of lean Ethereum

| | ask | why it matters |
|---|---|---|
| 1 | **Two-layer validator keys, certifying each window once** | smaller signatures and cheaper aggregation; key generation in minutes for every validator; a cold long-lived key; and the background key generation DVs need |
| 2 | **Bless threshold-derived signing randomness** (ρ = threshold-PRF(key, message) + i) | a one-line spec note; verifiers can't see the difference, but the spec and proofs should cover it |
| 3 | **Keep staking in groups a design goal** | every other choice stays compatible by default |
| 4 | index proposal keys by proposal duty, not slot | about halves DV key generation |
| 5 | higher maximum balance (2¹⁷–2²⁰ ETH) | fewer keys per ETH, so less key generation per ETH |

Why two-layer keys make staking more secure:
- **No forced single point of failure.** Without a threshold-friendly key structure, every post-quantum validator key
  would have to live whole on one machine. One compromise could make it slashable, and one outage takes it offline.
  Two-layer keys let a cluster generate and use keys that no single machine ever holds.
- **A cold root for everyone.** Even a solo validator signs with the long-lived top key only once per ~3 days. It can
  stay offline, and a hot-machine compromise exposes only the windows that machine holds (about 6 days), not the
  validator's whole life.
- **One new rule to enforce.** Each top-layer key certifies exactly one window. That's one more record in slashing
  protection.

Ranked detail, alternatives and history: [`docs/ethereum-design-decisions.md`](docs/ethereum-design-decisions.md).

## 8. Roadmap

![Roadmap](docs/fig/roadmap.svg)

The critical path:
1. **Agree on two-layer keys** and threshold randomness with the leanSig / leanSpec teams.
2. **Prove it:** a threshold two-layer XMSS security proof (PRAWNS covers the one-time layer).
3. **Prototype:** a dealer-based prototype in charon on a lean devnet.
4. **Build:** a per-window Boolean MPC key generation for BLAKE2s, chunked and resumable.
5. **Ship:** audit and hardening, ahead of the post-quantum chain.

Running alongside: top-layer resharing for operator changes, robustness (identify and evict a faulty node), and
formal proofs in Lean extending the existing XMSS proofs.

## 9. Open questions

- **Final leanSig parameters:** the hash and the chain counts. Cost scales with chain steps per slot, and with
  BLAKE-family hashes in Boolean MPC.
- **The certificate's home:** on-chain per window, or inside a periodic proof such as daily balance or key-registration
  proofs[^elc], which would also keep windows unlinkable.
- **Real-network MPC throughput:** bytes per AND gate for a production 3–4-party protocol. Our range assumes 1–3 bits.
- **Ceremony UX:** progress, checkpointing and failure handling for the first, hours-long key generation.

## 10. Verdict

- **Signing: ready.** Non-interactive, cheap, standard output.
- **Keys: viable and simple** with two-layer keys: a one-off MPC of a few hours, then a light background job per
  window. No single machine ever holds a key, and operator changes keep the validator.
- **Distributed validators in post-quantum Ethereum are a *when*, not an *if*.** The remaining steps are known
  engineering, a proof, and a spec change that benefits every staker.

## Further reading

| | |
|---|---|
| [`docs/two-layer-keys.md`](docs/two-layer-keys.md) | the two-layer design: options, sizes, security rules, prior art |
| [`docs/prawns.md`](docs/prawns.md) | PRAWNS construction, threshold condition, randomness, why key generation needs MPC |
| [`docs/dkg-and-mpc-costs.md`](docs/dkg-and-mpc-costs.md) | cost model: per-hash MPC costs, key generation, storage, single-layer fallback |
| [`docs/ethereum-design-decisions.md`](docs/ethereum-design-decisions.md) | ranked asks, maximum balance, equivocation rules, The Extremely Lean Chain |
| [`docs/alternatives.md`](docs/alternatives.md) | helpers that may only cost liveness, TEE, FHE, Stoffel MPC, Flock |
| [`docs/leansig.md`](docs/leansig.md) | leanSig parameter sets, key generation structure, slot usage |
| [`tools/`](tools/) | `cost_model.py --primary` (this page's numbers), `--blake`, `kk_leak.py`, `kk_multitarget.py`, `figs.py` |
| [`doc/`](doc/), [`mpspdz/`](mpspdz/) | prior work (2025): *Towards Threshold Hash-Based Signatures for Post-Quantum Distributed Validators*, with MP-SPDZ benchmarks that calibrate our MPC costs |

## References

[^prawns]: Boneh, Bünz, Justin D., Litchev, Nazirkhanova. *PRAWNS: Threshold Hash-Based Signatures from Threshold PRFs*. IACR ePrint 2026/2142. <https://eprint.iacr.org/2026/2142>
[^kk]: Kondi, Kumar. *A Black-Box Impossibility Result for Threshold Signing Standard Hash-Based Signatures*. IACR ePrint 2026/2194. <https://eprint.iacr.org/2026/2194>
[^elc]: *The Extremely Lean Chain*. ethresear.ch, July 2026. <https://ethresear.ch/t/the-extremely-lean-chain/25369>

Also: *Flock: Fast Proving for Batch Boolean Computations*, ePrint 2026/1329 <https://eprint.iacr.org/2026/1329> ·
leanSig <https://github.com/leanEthereum/leanSig> · leanSpec <https://github.com/leanEthereum/leanSpec> · leanVM
<https://github.com/leanEthereum/leanVM> · HoneyBadgerMPC, ePrint 2019/883 <https://eprint.iacr.org/2019/883>
