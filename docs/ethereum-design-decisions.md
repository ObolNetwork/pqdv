# Lean Ethereum design decisions that make or break distributed validators

Ranked by impact on whether threshold leanSig (PRAWNS signing plus MPC key generation) is viable. "Must" means
DVs don't work without it. Numbers come from [`dkg-and-mpc-costs.md`](dkg-and-mpc-costs.md) (`tools/cost_model.py`).

## Ranked list

| # | Priority | Decision | Why it matters for DVs | Current state (Oct 2026) |
|---|---|---|---|---|
| 1 | **Must** | **Encoding randomness ρ may be supplied by the signer after the message is fixed** (not required to be derived from the secret seed) | leanSig grinds ρ = PRF(secret seed, slot, msg, counter). A threshold signer has no seed: computing that PRF inside MPC on every signature is about 2¹⁵ BLAKE2s calls per signature (≈ 150 Mbps per validator, misses the slot). The verifier can't tell how ρ was made, so this is about the spec and its security proofs, not the wire format. ρ must still be unpredictable to whoever picks the message, or a Byzantine leader can search for two messages with one encoding (≈ 2⁶⁴ work) | leanSig derives ρ from the seed; proofs assume it |
| 2 | **Must** | **Keep "stake in groups / MPC-friendly" as an explicit design goal** | Without it every choice below drifts against DVs by default. Vitalik on ethresear.ch (2026-07): "I'm personally strongly in favor of this continuing to be a goal." | stated support, no spec commitment |
| 3 | Should | **Key rotation without exit and re-deposit**, every ≤ 12–18 months (or daily, see below) | Key generation cost scales with the slots a key covers. Rotation turns "pay for the whole lifetime up front" into a yearly background job (12–35 TB per node per validator), and lets operator changes happen at rotation instead of needing key-preserving resharing. Without it: pick a range at key generation (years = days of MPC per year covered) and exit at its end | no rotation in leanSpec; *The Extremely Lean Chain* (§ below) proposes rotation without a withdraw-and-deposit loop ("option 2") |
| 4 | Should | **A standard signature format with no proof-only shortcuts** | PRAWNS's output is a normal signature. Anything that ties signatures to per-key secret state (e.g. ZK proofs whose witness includes the signing seed) would force MPC proving | fine today |
| 5 | Should | **Index proposal keys by proposal duties assigned, not by slot** | Each validator has an attestation key *and* a proposal key covering every slot. Proposals are rare, so indexing the proposal key by the number of proposal duties assigned so far (deterministic from the proposer schedule, so a missed or orphaned block never reuses a leaf) shrinks it to a few thousand leaves and nearly **halves** key generation | both keys are slot-indexed |
| 6 | Should | **Higher maximum effective balance** | Cost is per key, not per ETH. 32 → 2048 ETH is 64× fewer keys. Going to 2¹⁷–2²⁰ ETH (131,072 / 262,144 / 524,288 / 1,048,576 ETH, i.e. six figures to low seven) is another 64–512× | 2048 ETH (2¹¹) |
| 7 | Should | **Chain steps per slot, v·(2^w − 1)** | Key generation cost is linear in it (294 for the draft set, 322 for devnets) | still being tuned (ots.golf) |
| 8 | Nice | **Hash choice** | An arithmetic-friendly hash (Poseidon over KoalaBear) would make MPC 2–10× cheaper than BLAKE2s at 3–4 parties and enable FHE alternatives. But Ethereum is moving to classic hashes for safety and is unlikely to switch back, so we plan for BLAKE | drifting to BLAKE (provable with Flock) |
| 9 | Nice | **Spec-level durable signing records** | Aligns client and DV slashing protection | leanSpec PR #1204 |
| 10 | Nice | **No reward gap on rotation or consolidation** | Today: queue + about 27 h without rewards ≈ 0.3% of annual reward per rotation | — |
| 11 | Nice | **Slashing semantics made explicit** | Sets the blast radius of mistakes. Note "equivocation requires both payloads to be valid" does **not** help us (below) | unspecified |

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
