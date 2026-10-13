# Lean Ethereum design decisions that make or break distributed validators

Ranked by impact on whether threshold leanSig (PRAWNS signing plus MPC key generation) is viable. "Must" means
DVs don't work without it. Numbers come from [`dkg-and-mpc-costs.md`](dkg-and-mpc-costs.md) (`tools/cost_model.py`).

## Ranked list

| # | Priority | Decision | Why it matters | Current state (Oct 2026) |
|---|---|---|---|---|
| 1 | **Top ask** | **Two-layer validator keys, each window certified once** (["option B"](two-layer-keys.md)) | Turns DV key generation into a few-hour one-off plus a 1–3-hour background job per ~3-day window (200 Mbps). For every validator: 21% smaller signatures, 11% cheaper aggregation, key generation in minutes, no lifetime to choose, and a long-lived key that can stay cold | single tree; its top/bottom split only saves memory. Hypertrees already exist in leanVM (leanSPHINCS) |
| 2 | **Ask** | **Bless threshold-derived signing randomness**: ρ = H + i, where H = threshold-PRF(key, message) and i is the smallest valid increment | Grinding becomes public hashing; H's shares ride on QBFT commit messages, so there's no extra round. Unpredictable below threshold, deterministic, unbiasable. Verifiers can't tell the difference, so it works as a deviation today; the ask is to cover it in the spec and proofs | leanSig derives ρ from the seed |
| 3 | **Principle** | **Keep staking in groups / MPC-friendliness as an explicit design goal** | Keeps every other choice compatible by default | supported in public discussion |
| 4 | Helps | **Index proposal keys by proposal duties assigned, not by slot** | A missed or orphaned block never reuses a leaf, and the proposal key shrinks to a few thousand leaves: about **halves** DV key generation | slot-indexed |
| 5 | Helps | **Higher maximum effective balance** | Cost is per key, not per ETH: 2048 → 2¹⁷–2²⁰ ETH (131,072 / 262,144 / 524,288 / 1,048,576) is 64–512× fewer keys | 2048 ETH |
| 6 | Helps | **Fewer chain steps per slot, v·(2^w − 1)** | Key generation is linear in it (294 in the draft set) | being tuned |
| 7 | Helps | **A standard signature format with no proof-only shortcuts** | Keeps PRAWNS output valid as is | fine today |
| 8 | Nice | **Hash choice** | Arithmetic-friendly hashes would make MPC 2–10× cheaper, but classic hashes are the safer choice and we plan for BLAKE | classic hash |
| 9 | Nice | **Spec-level durable signing records** (slots and window certificates) | Aligns client and DV slashing protection | leanSpec PR #1204 |
| 10 | Nice | **Slashing semantics made explicit**, including double window certificates | Sets the blast radius of mistakes | unspecified |
| 11 | Fallback | **Key rotation without exit**, every ≤ 12–18 months, with no reward gap | Only needed if keys stay single-layer | not in leanSpec |

## Two-layer validator keys

The top ask has its own page: [`two-layer-keys.md`](two-layer-keys.md). It covers the plain-terms explanation, the
stateless and certified options, safety rules, the DV design, costs, tuning and prior art in the lean repos.

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

## The Extremely Lean Chain (ethresear.ch, July 2026)

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
- **Privacy versus DVT transparency.** Daily unlinkable keys hide cluster identity on-chain, which cuts both ways for
  monitoring and decentralisation metrics.

**How it fits two-layer keys.**
- **A natural home for the certificate.** The once-per-period proof is where the window certificate ([option
  B](two-layer-keys.md)) can be checked, *privately*: "I hold a valid top-layer certificate for this new root, under
  some deposited key".
- **What a DV needs:**
  - the per-period key generation is the two-layer bottom tree;
  - the proof's inputs are known to every node in the cluster, so no MPC proving is needed.

**Ask.** If this direction proceeds:
- check the window certificate inside the periodic proof;
- prefer option 2 (rotation by proof) over seed-derived keys;
- keep a grace window so a late key generation costs one missed period at most.
