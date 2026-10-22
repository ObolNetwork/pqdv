# Lean Ethereum design decisions that make or break distributed validators

Ranked by impact on whether threshold leanXMSS (PRAWNS signing plus MPC key generation) is viable. Numbers come from [`dkg-and-mpc-costs.md`](dkg-and-mpc-costs.md) (`tools/cost_model.py`).

## Ranked list

[EIP-8450](eip-8450.md) (October 2026) settles the top of our earlier list: two-layer keys, one key for all duties, a
classic hash, signer-chosen leaf indices and replacement without exit. What remains, ranked:

| # | Priority | Decision | Why it matters | Current state (Oct 2026) |
|---|---|---|---|---|
| 1 | **Top ask** | **A much higher maximum effective balance: 2048 → 2¹⁷–2²⁰ ETH** | Every post-quantum cost is per key, not per ETH: registrations, registry state, 2.4 KB signatures to aggregate, grinding, and for DVs the MPC. Consolidated stake needs 64–512× fewer keys | 2048 ETH |
| 2 | **Ask** | **Recommend dense leaf allocation; keep the switch fork allocation-agnostic** | Every bottom tree is an MPC for a DV. Dense allocation (synchronized attestations, counter ranges for other duties) needs one tree per 2¹⁶ signatures; a fixed schedule of 8 leaves per slot costs up to **128×** more | EIP-8450 allows both, and gives fixed allocation with *k* = 8 as an example |
| 3 | **Ask** | **State the bottom-tree rule as an outcome**: a top key never certifies two roots, and the signer records a certification before releasing signatures from the tree | Threshold signers have no seed to derive bottom trees from | EIP-8450: "MUST be derived deterministically from the seed" |
| 4 | **Ask** | **Key-authorized replacement**: the registered key signs its successor at a reserved leaf | Post-quantum rotation for validators whose withdrawal contract can't make the owner-path request, plus operator changes and version migrations | replacement only through the withdrawal address |
| 5 | **Ask** | **A threshold profile for EIP-8310 keystores** | Shares, public tables and certification records instead of a seed | EIP-8310 stores a seed |
| 6 | Helps | **Weigh grinding against verification** when the duty cadence is fixed | 2²⁰ trials per signature (0.1–0.4 s CPU) sit after consensus for threshold signers, and add up with per-slot attesting | ~2²⁰ trials |
| 7 | Principle | **Keep staking in groups an explicit design goal** | Keeps every other choice compatible by default | DVs named in EIP-8450's rationale; leanXMSS sketches a threshold signer |
| — | ✅ settled | Two-layer keys (2¹⁶ × 2¹⁶) | Bounds every MPC to 2¹⁶ one-time keys | EIP-8450 |
| — | ✅ settled | Threshold-derived randomness, ρ = threshold-PRF(key, message) + i | Grinding becomes public; shares ride on QBFT commits | leanXMSS threshold sketch; "not consensus-critical" |
| — | ✅ settled | One key for all duties, signer-chosen leaves | Replaces the attestation/proposal key pair: halves DV key generation | EIP-8450 |
| — | ✅ settled | Classic hash, standard signature format | Keccak-f has AND-depth 24, so DV key generation is a few dozen MPC rounds | Keccak-256 |
| — | ✅ settled | Replacement without exit | Bad keys and migrations don't force exits | owner path |
| — | dropped | Certified windows ("option B") | Same MPC as the stateless form; only signature size differs | EIP-8450 chose stateless: +944 B per signature, no per-block certifications |

## Two-layer validator keys

The structure has its own page: [`two-layer-keys.md`](two-layer-keys.md). It covers the explanation, the stateless and
certified options, safety rules, the DV design, costs and prior art. The DV reading of EIP-8450 is in
[`eip-8450.md`](eip-8450.md).

## Higher maximum balance

Post-quantum signatures make every validator key expensive, for everyone. Under EIP-8450, each key costs:

| cost | per key | at a million keys |
|---|---|---|
| Registration on-chain | 2,541 B, capped at 8 per block | ~17 days of full blocks |
| Registry state | 33 B | 33 MB |
| Each signature to aggregate | 2,404 B, 186 Keccak-f to prove | 2.4 GB of signatures per attestation round |
| Signing | ~2²⁰ Keccak-f of grinding | |
| DV key generation | 55–164 GB of MPC per bottom tree, per node | |

None of these depend on stake. Raising the cap from 2048 ETH to 2¹⁷–2²⁰ ETH (131,072–1,048,576) lets consolidated stake
run on **64–512× fewer keys**.
- **For DVs:** a cluster that runs sixteen 2048-ETH keys today could run one, cutting its MPC sixteen-fold. Registration
  becomes one ceremony per operator, not per 2048 ETH.
- **For Ethereum:** fewer signatures per slot to aggregate is the most direct lever on proving cost, independent of any
  signature-scheme tuning.

**The trade-offs:**
- **More value behind each key.** That makes custody matter more. It's an argument for threshold keys and cold top
  layers, and against black-box or TEE shortcuts.
- **Consolidation is voluntary.** The saving depends on operators consolidating; small stakers are unaffected.
- **Per-key penalties grow with balance.** Slashing and correlation penalties scale with balance, which may slow
  institutional uptake.

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

**What daily keys would mean for DVs** (earlier BLAKE2s estimate with two keys; needs a smaller-tree parameter set):

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
- **A natural home for certified roots.** EIP-8450 carries the top certification in every signature. If a later key
  version moves to certified roots ([option B](two-layer-keys.md#2-two-ways-to-verify)), the once-per-period proof is
  where the certificate can be checked, *privately*: "I hold a valid top-layer certificate for this new root, under
  some registered key".
- **What a DV needs:**
  - the per-period key generation is the two-layer bottom tree;
  - the proof's inputs are known to every node in the cluster, so no MPC proving is needed.

**Ask.** If this direction proceeds:
- check certified roots inside the periodic proof, if a later key version uses them;
- prefer option 2 (rotation by proof) over seed-derived keys;
- keep a grace window so a late key generation costs one missed period at most.
