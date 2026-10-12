# pqdv: post-quantum distributed validators

Can a distributed validator (DV) still exist once Ethereum moves its validators to post-quantum, hash-based
signatures that are aggregated with zero-knowledge proofs? This repo is Obol's working answer.

**Status (October 2026).** We are evaluating [PRAWNS](https://eprint.iacr.org/2026/2142) (Boneh, Bünz, Justin D.,
Litchev, Nazirkhanova; ePrint 2026/2142), a threshold scheme for hash-based signatures. In short:

- **Signing fits a DV.** PRAWNS signing needs no interaction between signers and no hashing of secrets.
- **Key generation is the hard part.** Removing the trusted dealer costs hours of MPC per validator-year of key with
  a good protocol, and is untenable for a full 2³² lifetime.
- **It is early.** The paper is a three-week-old preprint with no code, parameters or benchmarks.

Our 2025 work on computing hash chains inside generic MPC is kept as [prior work](#repo-map).

This page explains what changes and why, for readers who know today's Ethereum and DVT well. The math and
cost models live in [`docs/`](docs/).

---

## 1. Today: why BLS made distributed validators easy

A BLS secret key is a number `sk`, and the public key is `pk = sk·G`. Everything about it is **linear**:

- **Threshold signing.** Shamir-split `sk` into shares. Each node signs with its share, and any `t` partial
  signatures combine (Lagrange interpolation, "in the exponent") into the one signature `pk` expects. Charon's
  `ceil(2n/3)` threshold and QBFT agreement sit on top of that.
- **DKG.** Because `pk` is linear in `sk`, nodes can jointly create a key nobody ever holds (each contributes a
  random polynomial and publishes commitments). It takes seconds.
- **Aggregation.** Thousands of signatures add up into one. The protocol never needs to know a validator is a DV.
- **No signing state.** Signing twice is a *slashing* question about what you sign, not a cryptographic break.

## 2. Tomorrow: what changes in a post-quantum, zk-aggregated Ethereum

The lean consensus effort ([leanSpec](https://github.com/leanEthereum/leanSpec),
[leanSig](https://github.com/leanEthereum/leanSig), [leanVM](https://github.com/leanEthereum/leanVM)) replaces BLS
with a hash-based signature called **leanSig**, a generalized XMSS.

- **A key is a seed plus a tree.** For every slot the key will ever sign, the seed derives a *one-time* Winternitz
  key: 46 secret starting values, each extended by a **hash chain** of 7 steps. The public key is the root of a
  Merkle tree over all those one-time keys (52 bytes).
- **Signing reveals chain positions.** A message is encoded into 46 numbers in `0..7` with a fixed sum. The signature
  reveals, for each chain, the value that many steps up, plus a Merkle path (about 2.5 KB in total). The verifier
  hashes the rest of each chain to the top and checks the path to the root.
- **The key is stateful.** Each one-time key may sign **exactly one** message, so each slot's key must never sign
  twice. Signing twice is not just slashable: it leaks enough to forge. Nodes need a durable never-sign-twice record.
- **Aggregation by proof.** Hash-based signatures don't add up. Instead, an aggregator proves in a zkVM (leanVM) that
  many standard signatures verify. **A DV must therefore emit an ordinary leanSig signature.** A proof, or a bundle of
  `t` signatures, would not be aggregatable.
- **Timing and usage.** Slots are 4 s, made of five 800 ms intervals: propose at 0, attest at 0.8 s, aggregators
  collect at 1.6 s. Every validator attests every slot, with **two keys** (attestation and proposal). A key covers a
  range of slots fixed at key generation. There is no key rotation today, and generation cost scales with that range.

| | BLS (today) | leanSig (post-quantum) |
|---|---|---|
| Secret | one number | a seed that expands to millions of hash chains |
| Public key | `sk·G`, linear | Merkle root over chain ends, non-linear (hashes) |
| Threshold signing | partial signatures combine algebraically | no algebra: needs a new idea (PRAWNS) |
| DKG | seconds | needs hashing of secrets inside MPC (§5) |
| Aggregation | add signatures | zk proof over standard signatures |
| State | slashing protection | cryptographic: each slot key signs once, ever |

## 3. Why threshold hash-based signatures are hard

There is no algebra to share, so earlier approaches each break something:

1. **Concatenate `t` signatures.** Not a standard signature: aggregators and verifiers would have to change.
2. **Prove `t` signatures in a SNARK.** Same problem, plus heavy proving.
3. **Run signing inside MPC.** The secret chain values must be hashed jointly. Even with an MPC-friendly hash that is
   hundreds of network rounds per signature: 4–39 s for Poseidon, minutes for BLAKE2s. It misses the slot.
4. **Precompute everything at key generation** and store secret shares of every chain value. Signing becomes a
   single round, but every node stores about 10 KiB of secret shares per slot per key (about 163 GB per
   validator-year), and key generation still needs MPC.

![One lean slot](docs/fig/slot.svg)

## 4. PRAWNS in one paragraph

A **dealer** builds the key, splits a **threshold PRF** key among the nodes, and publishes a large **public helper
table** (`cpk`): every intermediate chain value, each masked with a PRF output. To sign, each node sends its **PRF
shares** for the chain positions the message selects. A combiner rebuilds the masks from any `t` shares, unmasks the
right table entries, and outputs a **standard leanSig signature**.

- **Non-interactive.** No node hashes any secret, and there are no extra signer-to-signer rounds beyond agreeing the
  encoding randomness.
- **Context-aware shares.** Each share is bound to its message, so shares for different messages cannot be mixed
  into a forgery. This is the paper's key idea.
- **Fits charon's threshold.** One condition: `t > (n + f)/2`, so two disjoint quorums can't sign different
  messages for one slot. Charon's `ceil(2n/3)` already meets it at the usual BFT `f`.
- **Hidden setup.** The public key doesn't reveal `n` or `t`.
- **Two PRF options:**
  - **Hash-based (`F_hash`).** Exact, adaptively secure, cheap at our cluster sizes (84 keys per node at 7-of-10).
    Changing an operator means a new key, and so a new validator.
  - **Lattice (`F_lat`).** Allows resharing without changing the public key. Only statically secure, heavier, and no
    parameters are given.

Detail, proofs status and caveats: [`docs/prawns.md`](docs/prawns.md).

## 5. The catch: key generation

The public key needs the **top of every hash chain** for every slot the key covers, and the helper table needs every
step. Without a dealer, those hashes have to run **inside MPC**. Kondi and Kumar
([ePrint 2026/2194](https://eprint.iacr.org/2026/2194)) prove there's no shortcut: any key generation that hashes in
the clear leaks enough chain secrets to forge, even with 4 parties.

That is 322 Poseidon hashes (about 95k MPC multiplications) per slot per key, two keys per validator. Every chain is
independent, so the whole DKG needs only a few hundred network rounds. **Bandwidth, not latency, sets the cost.**

| The key covers | MPC traffic per node, per validator | Time at 1 Gbps (best protocol → measured malicious Shamir) |
|---|---|---|
| ≈ 6 days (the minimum key) | 0.1–0.8 TB | **13 min → 1.7 h** |
| 1 year | 6–47 TB | **13 h → 4.4 days** (1.3–10.5 h at 10 Gbps) |
| 5 years | 30–237 TB | 3 → 22 days |
| full 2³² slots (≈ 544 years) | petabytes | **untenable** |

- **Steady-state view.** Amortised, the DKG costs about **1.5–12 Mbps per node per validator**. Tens of validators per
  cluster is plausible; thousands are not, unless the protocol changes (key rotation) or MPC gets cheaper.
- **Hash choice.** leanSig devnets use Poseidon. The draft spec has moved to BLAKE2s as a placeholder. BLAKE2s is 10–90×
  *deeper* in MPC, which is fatal for signing in MPC. For a parallel DKG that only adds minutes of latency, but it costs
  **2–10× more bandwidth** with a 3–4-party MPC, and 18–76× with larger committees.
- **Storage.** The public helper table is about **163 GB per validator-year**, and every node that may combine needs it.

Derivations, assumptions and what moves the numbers: [`docs/dkg-and-mpc-costs.md`](docs/dkg-and-mpc-costs.md).
leanSig parameters and key structure: [`docs/leansig.md`](docs/leansig.md).

## 6. A validator's life with threshold leanSig

![Lifecycle](docs/fig/lifecycle.svg)

| Stage | What happens | Bottleneck / resources |
|---|---|---|
| Key generation, option A: dealer | one machine (ideally a TEE) builds key, shares and table, then erases | CPU-hours per validator-year; trust in erasure |
| Key generation, option B: MPC | all nodes jointly hash every chain | §5 table: TBs and hours–days; all nodes online, so it must be restartable |
| Distribute public table | ship `cpk` to every node that may combine | ≈ 163 GB per validator-year |
| Every slot | QBFT agree → agree rho → PRF shares → combine → publish | ~1.5 KiB per node, milliseconds of compute; fits inside 0.8 s |
| Every ~3 days | nothing (table precomputed), or an MPC refresh to save storage | refresh costs the same as the DKG, amortised |
| Operator change | `F_hash`: new key, new validator. `F_lat`: reshare, same key | open research |
| Key range ends | no rotation in the protocol today: exit and re-key | protocol ask |

## 7. The journey and its critical path

![Roadmap](docs/fig/roadmap.svg)

What sits on the critical path to a dealer-free threshold leanSig:

1. **Protocol asks** to the leanSig / lean consensus teams:
   - encoding randomness that a threshold signer can agree jointly;
   - a durable per-slot signing record;
   - **key rotation or extension**, which turns one giant DKG into small rolling ones;
   - keep an MPC-friendly chain hash, or at least weigh the DV cost of each option;
   - keep `v·(2^w − 1)` chain steps per slot in mind, since DKG cost scales with it.
2. **A security proof at the XMSS / leanSig level.** The paper proves the one-time scheme; XMSS is a sketch.
3. **A dealer-based prototype** in charon on a lean devnet, for real signing, combining and storage numbers.
4. **A purpose-built parallel MPC DKG.** Target the 6-day key in under an hour, then 1-year keys, restartable.

Off the critical path but needed before production: robustness (the paper has none), operator changes without
re-keying, and storage and prefetch for the helper table.

## 8. Verdict

- **Maturity: low.** Preprint, no venue, no code, no parameters. Proofs cover the one-time scheme only, and there is
  no robustness.
- **Viability of signing: good.** It is non-interactive, cheap, outputs standard signatures and fits the slot.
- **The DKG: not untenable, not cheap.** Minutes for the minimum 6-day key; hours (good protocol, fast links) to days
  (off-the-shelf) per validator-year; untenable for the full lifetime. A dealer, ideally in a TEE, is the practical
  bootstrap today.
- **Readiness for Ethereum: research.** The direction is promising. The biggest levers are protocol choices still
  open at Ethereum (rotation, randomness, hash) and a real MPC DKG implementation.

## Repo map

| Path | What |
|---|---|
| [`docs/prawns.md`](docs/prawns.md) | PRAWNS construction, security conditions, statefulness, Kondi–Kumar impossibility, open problems |
| [`docs/dkg-and-mpc-costs.md`](docs/dkg-and-mpc-costs.md) | cost model: per-hash MPC costs (Poseidon, BLAKE2s, Keccak), DKG tables, what to move into MPC |
| [`docs/leansig.md`](docs/leansig.md) | leanSig parameter sets, key generation structure, slot usage, aggregation interface |
| [`tools/cost_model.py`](tools/cost_model.py) | reproduces every number above (`python3 tools/cost_model.py`) |
| [`tools/figs.py`](tools/figs.py) | regenerates `docs/fig/*.svg` |
| [`doc/`](doc/), [`mpspdz/`](mpspdz/) | **prior work (2025)**: *Towards Threshold Hash-Based Signatures for Post-Quantum Distributed Validators* (A. Adomnicăi, DV Labs) and MP-SPDZ Poseidon2 benchmarks. Cited by PRAWNS as ref [2]. Its measured MPC costs calibrate our model; its parameters and its approach (signing inside generic MPC) are superseded. |

Sources: PRAWNS (ePrint 2026/2142); Kondi & Kumar (ePrint 2026/2194); [lclhost.org/blog/prawns](https://lclhost.org/blog/prawns/);
leanEthereum leanSig / leanSpec / leanVM / pm repositories (October 2026); this repo's 2025 benchmarks.
