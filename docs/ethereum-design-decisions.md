# Lean Ethereum design decisions that make or break distributed validators

Ranked by impact on whether threshold leanSig (PRAWNS signing plus MPC key generation) is viable. "Must" means
DVs don't work without it. Numbers come from [`dkg-and-mpc-costs.md`](dkg-and-mpc-costs.md) (`tools/cost_model.py`).

## Ranked list

| # | Priority | Decision | Why it matters for DVs | Current state (Oct 2026) |
|---|---|---|---|---|
| 1 | **Must** | **Keep "stake in groups / MPC-friendly" as an explicit design goal** | Without it every choice below drifts against DVs by default. Vitalik on ethresear.ch (2026-07): "I'm personally strongly in favor of this continuing to be a goal." | stated support, no spec commitment |
| 2 | **Should (top ask)** | **Two-layer validator keys** (a long-lived top key certifies a fresh ~3-day bottom tree; ideally the certificate is registered once per window, "option B" below) | Key generation becomes a small upfront step (top tree + first bottom tree, the cost of today's minimum key) plus a steady background job per bottom tree. No lifetime to choose up front, no rotation needed, about 1.2 GB of public table per validator instead of 74 GB/year. Also shortens key generation for *every* validator, not just DVs | leanSig is one tree (its top/bottom split is a memory optimisation); leanSPHINCS (accounts) already uses a 3-layer hypertree in leanVM, with Lean proofs |
| 3 | Should | **Bless threshold-derived encoding randomness**: ρ = H + i, where H = threshold-PRF(key, message) and i is the smallest integer that makes the encoding valid | Grinding then needs no secret, so it runs in the clear; H costs one non-interactive threshold evaluation, and its shares can ride on QBFT commit messages. Unpredictable to anyone below threshold, deterministic per message, and unbiasable (unlike commit-reveal). Verifiers can't tell the difference, so this works as a deviation today; the ask is to confirm it in the spec and proofs | suggested by EF researchers in discussion (Oct 2026) |
| 4 | Should (fallback) | **Key rotation without exit and re-deposit**, every ≤ 12–18 months | Only needed if keys stay single-layer: caps key generation at a yearly background job and allows operator changes at rotation | no rotation in leanSpec; *The Extremely Lean Chain* proposes one ("option 2") |
| 5 | Should | **A standard signature format with no proof-only shortcuts** | PRAWNS's output is a normal signature. Anything that ties signatures to per-key secret state (e.g. ZK proofs whose witness includes the signing seed) would force MPC proving | fine today |
| 6 | Should | **Index proposal keys by proposal duties assigned, not by slot** | Each validator has an attestation key *and* a proposal key covering every slot. Proposals are rare, so indexing the proposal key by the number of proposal duties assigned so far (deterministic from the proposer schedule, so a missed or orphaned block never reuses a leaf) shrinks it to a few thousand leaves and nearly **halves** key generation | both keys are slot-indexed |
| 7 | Should | **Higher maximum effective balance** | Cost is per key, not per ETH. 32 → 2048 ETH is 64× fewer keys. Going to 2¹⁷–2²⁰ ETH (131,072 / 262,144 / 524,288 / 1,048,576 ETH, i.e. six figures to low seven) is another 64–512× | 2048 ETH (2¹¹) |
| 8 | Should | **Chain steps per slot, v·(2^w − 1)** | Key generation cost is linear in it (294 for the draft set, 322 for devnets) | still being tuned (ots.golf) |
| 9 | Nice | **Hash choice** | An arithmetic-friendly hash (Poseidon over KoalaBear) would make MPC 2–10× cheaper than BLAKE2s at 3–4 parties and enable FHE alternatives. But Ethereum is moving to classic hashes for safety and is unlikely to switch back, so we plan for BLAKE | drifting to BLAKE (provable with Flock) |
| 10 | Nice | **Spec-level durable signing records** | Aligns client and DV slashing protection | leanSpec PR #1204 |
| 11 | Nice | **No reward gap on rotation or consolidation** | Today: queue + about 27 h without rewards ≈ 0.3% of annual reward per rotation | — |
| 12 | Nice | **Slashing semantics made explicit** | Sets the blast radius of mistakes. Note "equivocation requires both payloads to be valid" does **not** help us (below) | unspecified |

## Two-layer validator keys (the top ask)

### In plain terms

Today a leanSig key is like **a book of 4 billion single-use tickets**, one per slot. The public key is a fingerprint
of the whole book, so to publish the fingerprint you must print every ticket up front, even though you only use one
every 4 seconds. For a single validator that printing takes CPU-hours; for a DV it has to happen inside MPC, which is
the expensive part.

A two-layer key works like **a certificate chain** (as in TLS, a root CA certifying intermediates):
- **Top layer.** You print only a small *master* book: 65,536 single-use stamps. The public key is the fingerprint of
  the master book, so that's all you have to print up front.
- **Bottom layer.** Every ~3 days you print a fresh *ticket* book of 65,536 tickets and spend one master stamp to
  sign "this new ticket book is mine".
- **Validity.** A ticket counts if it comes from a ticket book carrying a valid master stamp.

You still get 65,536 books × 65,536 tickets = 2³² slots (≈ 544 years), but you only ever print one master book plus
the current ticket book.

### Two ways to run it

| | size per signature | verification (compressions) | protocol change |
|---|---|---|---|
| Today: one tree, 32-level path | 1,208 B | ~144 | — |
| **Option A, stateless:** every signature carries the bottom signature *and* the top stamp on its book | ~1,904 B (+58%) | ~256 (~1.8×) | signature scheme only |
| **Option B, certified books:** the stamp is posted once per window and consensus records the current book's root; slot signatures reference it | ~952 B (−21%) | ~128 (−11%) | a once-per-window certificate plus a small "current root" record per validator |

(Draft BLAKE2s parameters: 42 chains, 16-byte values. The top layer adds one one-time signature, 672 B, and one
randomizer, 24 B. The path stays 32 levels in total under option A and drops to 16 under option B.)

- **Option A** is a pure signature-scheme change, but it works against the lean team's stated goal of minimising
  verification hashing for aggregation: every slot re-verifies the same top stamp.
- **Option B** moves that cost from every slot to once per ~64k slots, at the price of consensus machinery. It
  matches *The Extremely Lean Chain*'s per-period key registration (§ below). If the stamp is checked *inside* that
  design's daily STARK, the link between windows also stays private.

### Prior art in the lean repos

- **leanSig already splits its tree** into a top tree over bottom-tree roots, but only to save memory: "During key
  generation, we first generate all bottom trees and store their roots, then we generate the top tree just from their
  roots" (`leanSig/src/signature/generalized_xmss.rs`). The change is to make the top tree's leaves one-time keys that
  *sign* bottom roots later, instead of the roots themselves.
- **leanVM already ships a hypertree.** leanSPHINCS, the account signature, is a 3-layer hypertree with a Rust
  implementation, aggregation-guest verification code and Lean proofs (`leanVM/crates/sphincs`, `leanVM/formal/sphincs`).
- **Key generation time was already a pain point.** Full-tree key generation is "~days (~64 GiB sk)", which is why
  activation intervals exist (lean-week Cambridge, KeyGen & API talk).
- **No explicit validator-level single- vs multi-layer discussion** turned up in the public notes we cloned.
  The implicit reason is the design goal "minimize the signature verification or generation hashes so that the
  prover … is easy" (pq-interop meeting 01), which option A works against and option B doesn't.
- **Origin of this proposal:** suggested by EF researchers in discussion (October 2026), alongside the
  threshold-derived ρ construction above.

### What it means for DVs

- **Upfront key generation:** the top tree plus the first bottom tree, roughly today's minimum-key cost: 0.2–0.6 TB
  per node, 26–78 minutes at 1 Gbps per validator.
- **Then one bottom tree per ~3 days, built ahead of time in the background:** ~100–300 GB per node, 13–40 minutes at
  1 Gbps. The amortised rate is unchanged at about 3–9 Mbps per validator.
- **Signing a new bottom root with the top key is ordinary PRAWNS signing**, once per window.
- **Storage:** the top layer's public table (kept for life, ~0.3 GB per key) plus the current and next bottom windows
  (~1.2 GB in total).
- **Unchanged:** key generation still needs MPC (the leakage argument applies to every layer), and an operator change
  still needs the top layer re-keyed (`F_hash`) or reshared (`F_lat`).

### Why it helps every validator, not only DVs

Every validator's key generation shrinks from "all slots in the activation interval" to "top tree plus one bottom
tree". No one has to choose a lifetime up front or hold a multi-gigabyte secret key.

### New safety rule it introduces

Each top one-time key must certify **exactly one** bottom root; its index is the window number. Certifying two
different roots for one window would let an attacker certify a bottom tree of their own, which is a full key
compromise, worse than an ordinary double vote. Clients and DVs need slashing-style protection for top-layer signing.

## Higher maximum balance

The reason given for stopping at 2048 ETH was sync committee selection. In a zk-verified chain that matters less, and
the EF is working on decoupled consensus. For DVs:
- **Per-ETH key generation cost becomes negligible.** At 2²⁰ ETH, a whole operator might run a handful of keys.
- **The value behind each key grows enormously.** That makes black-box or TEE shortcuts even less acceptable, and
  makes each key generation's liveness (completing before the rotation deadline) more important.

## Would "equivocation requires both payloads valid" remove the framing risk?

No. The framing attack in [`prawns.md`](prawns.md) §5.1 needs a message whose *encoding* dominates the honest
signature's on the chains the attacker doesn't know. The attacker doesn't grind the message, it grinds the
randomizer ρ, which is part of the signature and chosen freely by the signer. So it can take any valid alternative
payload (e.g. an attestation for another known head) and grind ρ alone. Grinding valid and invalid payloads costs
the same.

It would only help if ρ were fixed by the protocol, but then a Byzantine leader could search for two messages with
the same encoding (≈ 2⁶⁴), so that trade isn't attractive. The real fix stays the same: never use a black-box key
generation.

## The Extremely Lean Chain (Buterin, ethresear.ch, July 2026)

The proposal:
- **Phase 1** removes per-validator state: the public key lives in the deposit tree and signatures carry a Merkle
  proof; validators ZK-prove their own balance daily.
- **Phase 2** adds privacy: every validator registers a **fresh public key every day**, proven to descend from its
  deposit.

To keep slashing possible it suggests either:
1. deterministic daily keys from a seed fixed at deposit; or
2. a proof that walks previous slashings. This one "enables key rotation without a withdraw-and-deposit loop".

**What daily keys would mean for DVs** (BLAKE2s, both keys; needs a smaller-tree leanSig parameter set):

| | Yearly key | Daily key |
|---|---|---|
| MPC key generation per node | 12–35 TB, about 1–3 days at 1 Gbps | **32–96 GB, about 4–13 min at 1 Gbps** |
| Amortised bandwidth | 3–9 Mbps per validator | the same: 3–9 Mbps per validator |
| Public table to store | 74 GB per validator-year | **≈ 0.2 GB per validator, rolling** |
| Operator change | wait for rotation | next day |
| Long-lived key risk | up to a year | a day |
| New liveness duty | yearly key generation | **daily** key generation, and a daily balance-update STARK |

- **It's more appealing on several axes:** storage disappears, lumps become minutes, operator changes become routine
  and long-lived keys go away. Total work is unchanged.
- **Daily is a different operating model.** Every node must take part in a short MPC every day. A failed day means
  that day isn't attested, not slashing: the post says a validator that misses its proof simply can't attest until it
  submits.
- **The daily STARK needs no MPC** if its witness (the link between yesterday's and today's identity, balances,
  slashing scans) is known to all of the cluster's nodes. That is private towards the public, not between
  co-operators. Option 1 (keys derived from a deposit-time *seed*) is bad for DVs: proving would need the seed as a
  witness, so we'd prefer option 2.
- **Privacy versus DVT transparency.** Daily unlinkable keys hide cluster identity on-chain. That cuts both ways for
  monitoring and for the decentralisation metrics Obol has argued for in that thread.

**Ask.** If the Extremely Lean Chain direction proceeds:
- choose option 2 (rotation by proof, not seed-derived keys);
- keep each period's key generation inside a leanSig parameter set suited to small trees;
- give a grace window so a late daily key generation costs one missed period at most.
