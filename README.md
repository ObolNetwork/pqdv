# pqdv: post-quantum distributed validators

Can a distributed validator (DV) still exist once Ethereum moves its validators to post-quantum, hash-based
signatures that are aggregated with zero-knowledge proofs? This repo is Obol's working answer (October 2026).

## TL;DR

- **Threshold signing is sorted.** PRAWNS[^prawns] (Boneh, Bünz, Justin D., Litchev, Nazirkhanova, 2026):
  - every node signs alone, with no MPC and no hashing of secrets;
  - the output is a standard signature, so aggregation and verification are unchanged;
  - it fits in milliseconds inside a 4-second slot.
- **Key generation is a heavy process that runs in parallel to your validator.** Generating a key without a trusted
  dealer means hashing secrets inside a multi-party computation (MPC).
  - For a 12-month key that is **12–35 TB of traffic per node** (1–3 days at 1 Gbps, hours at 10 Gbps).
  - Run in the background, that is about **3–9 Mbps per node per validator**.
  - Storage is modest: 11–25 GB per node per validator-year with Reed–Solomon across the cluster, down to about
    1 GB if the public table lives remotely. If the table is lost, it can be rebuilt by MPC; losing it costs liveness,
    never safety.
- **It prefers a key rotation every 12–18 months.** One heavy key generation per year, overlapped with the live key,
  rather than paying for decades up front. That needs Ethereum to support cheap rotation or consolidation.
- **A few Ethereum design choices matter.** Must-haves: encoding randomness the signers can fix after the message,
  and keeping staking in groups as a design goal. Strongly preferred: key rotation without exit (yearly, or daily as
  in *The Extremely Lean Chain*[^elc]) and higher maximum balances ([§8](#8-ethereum-design-decisions-that-make-or-break-dvs)).
- **Verdict.** Signing is good to go. Minimising trust (no single point of failure) still needs work: a dealer-free
  key generation for safety, and its liveness risks at runtime (periodic MPC, table availability).
- **Maturity: research.** PRAWNS is a weeks-old preprint with no code. The rest of this page explains why the
  answer looks like this. The math lives in [`docs/`](docs/).

---

## 1. Today: why BLS made distributed validators easy

A BLS secret key is a number `sk`, and the public key is `pk = sk·G`. Everything about it is **linear**:

- **Threshold signing.** Shamir-split `sk`. Each node signs with its share, and any `t` partial signatures combine
  (Lagrange interpolation, "in the exponent") into the signature `pk` expects. Charon's `ceil(2n/3)` threshold and
  QBFT agreement sit on top.
- **DKG.** Because `pk` is linear in `sk`, nodes can jointly create a key nobody ever holds, in seconds.
- **Aggregation.** Thousands of signatures add up into one. The protocol never needs to know a validator is a DV.
- **No signing state.** Signing twice is a slashing question, not a cryptographic break.

## 2. Tomorrow: what changes in a post-quantum, zk-aggregated Ethereum

The lean consensus effort ([leanSpec](https://github.com/leanEthereum/leanSpec),
[leanSig](https://github.com/leanEthereum/leanSig), [leanVM](https://github.com/leanEthereum/leanVM)) replaces BLS
with **leanSig**, a hash-based signature (a generalized XMSS).

- **A key is a seed plus a tree.** For every slot the key will ever sign, the seed derives a *one-time* Winternitz key:
  about 42–46 secret starting values, each extended by a **hash chain** of 7 steps. The public key is the root of a
  Merkle tree over all those one-time keys.
- **Signing reveals chain positions.** A message is encoded into numbers in `0..7` with a fixed sum. The signature
  reveals, for each chain, the value that many steps up, plus a Merkle path (1.2–2.5 KB). The verifier hashes to the
  top of each chain and checks the path.
- **The key is stateful.** Each slot's one-time key may sign **exactly one** message. Signing twice leaks enough to
  forge, so nodes need a durable never-sign-twice record.
- **Aggregation by proof.** An aggregator proves in a zkVM that many standard signatures verify. **So a DV must emit an
  ordinary leanSig signature.** A proof, or a bundle of `t` signatures, would not be aggregatable.
- **The hash is still being chosen.** Devnets use Poseidon (a zk-friendly hash). The draft spec uses BLAKE2s as a
  placeholder, and the direction is towards classic hashes proven with fast batch provers such as
  [Flock](https://eprint.iacr.org/2026/1329). **This page assumes BLAKE.**
- **Timing and usage.** Slots are 4 s: propose at 0, attest at 0.8 s, aggregators collect at 1.6 s. Every validator
  attests every slot, with **two keys** (attestation and proposal). A key covers a range of slots fixed at generation,
  and there is no rotation today.

| | BLS (today) | leanSig (post-quantum) |
|---|---|---|
| Secret | one number | a seed that expands into millions of hash chains |
| Public key | `sk·G`, linear | Merkle root over chain ends (hashes) |
| Threshold signing | partial signatures combine algebraically | needs a new idea (PRAWNS) |
| DKG | seconds | hashing of secrets inside MPC: hours to days per key-year |
| Aggregation | add signatures | zk proof over standard signatures |
| State | slashing protection | cryptographic: each slot key signs once, ever |

## 3. Why threshold hash-based signatures are hard

There is no algebra to share, so earlier approaches each break something:

1. **Concatenate `t` signatures, or prove them in a SNARK.** Not a standard signature, so aggregators and verifiers
   would have to change.
2. **Run signing inside MPC.** The secret chain values must be hashed jointly: thousands of network rounds per
   signature with BLAKE. It misses the slot by minutes.
3. **Precompute everything at key generation** and keep secret shares of every chain value. Signing is then one
   round, but every node stores large secret material, and key generation still needs MPC.

![One lean slot](docs/fig/slot.svg)

## 4. PRAWNS in one paragraph

A **dealer** builds the key, splits a **threshold PRF** key among the nodes, and publishes a large **public table**
(`cpk`): every intermediate chain value, each masked with a PRF output. To sign, each node sends its **PRF shares** for
the chain positions the message selects. A combiner rebuilds the masks from any `t` shares, unmasks the right table
entries, and outputs a **standard leanSig signature**.

- **Context-aware shares.** Shares are bound to their message, so they can't be mixed across messages.
- **Fits charon's threshold.** The only requirement is `t > (n + f)/2`, which `ceil(2n/3)` meets.
- **Two PRF options:**
  - **hash-based (`F_hash`):** cheap at our cluster sizes, but changing an operator means a new key;
  - **lattice (`F_lat`):** allows resharing, but heavier and only statically secure.

Details: [`docs/prawns.md`](docs/prawns.md).

## 5. Key generation: the heavy part

The public key needs the **top of every hash chain** for every slot the key covers, and the public table needs every
step. Without a trusted dealer, those hashes must run on secret data **inside MPC**.

**Why not hash in the clear?** It would be dramatically cheaper (see the last column below), but a "black-box" DKG
hands colluding nodes some of the chain secrets ([Kondi–Kumar](https://eprint.iacr.org/2026/2194)).
- **What it buys an attacker.** The minority can later forge a *second* signature for a slot the validator already
  signed, which is slashing evidence that frames the DV. They can grind for it offline, on whichever signed slot is
  weakest.
- **How cheap that is.** About 2³²–2³⁷ hash work under BFT assumptions, and about 2⁴⁵–2⁴⁹ even if at most a fifth of
  nodes are faulty (Minimmit-style). That's GPU-hours to GPU-days, against leanSig's 128-bit target.

Details: [`docs/prawns.md`](docs/prawns.md) §5.

BLAKE2s key generation per validator (both keys), per node, with a 3–4-party Boolean MPC:

| The key covers | MPC traffic per node | MPC at 1 Gbps | MPC at 10 Gbps | Black-box (insecure), one 16-core box |
|---|---|---|---|---|
| 1 day (daily keys; smaller-tree parameters) | 32–96 GB | 4–13 min | 26–77 s | <1 s |
| ≈ 6 days (the minimum key) | 0.2–0.6 TB | 26–78 min | 3–8 min | ~1 s |
| **12 months** | **12–35 TB** | **26 h – 3.2 days** | **2.6–7.8 h** | ~1 min |
| 18 months | 18–53 TB | 1.6–4.9 days | 4–12 h | ~1.5 min |
| 5 years | 58–175 TB | 5–16 days | 13–39 h | ~5 min |

- **Bandwidth is the cost, not latency.** Every chain is independent, so the whole computation is only a few thousand
  rounds deep (about 15 minutes of latency in total).
- **The cost is per key, not per ETH.** Consolidated 2048-ETH validators make this up to 64× cheaper per ETH than
  32-ETH ones.

Model, assumptions and the Poseidon alternative: [`docs/dkg-and-mpc-costs.md`](docs/dkg-and-mpc-costs.md).

## 6. Storage, and what can be prepared in advance

**Storage is far smaller than the traffic.** Secret material per node is kilobytes (PRF keys plus the
never-sign-twice record). The large item is the **public** table, which is safe to host anywhere: a bad host can only
cost liveness, never safety.

| Where the public table lives | Local storage per validator (12-month key, BLAKE2s) | Validators per 2 TB |
|---|---|---|
| every node keeps it all | 74 GB | ~27 |
| only f+1 combiner replicas | 30–37 GB average | ~55–65 |
| Reed–Solomon across the cluster (any n−f shards rebuild; Merkle-committed shards) | 11–25 GB | ~80–190 |
| untrusted object store, 6 days prefetched locally | ~1.2 GB (+74 GB remote, ≈ $2/month) | 1,000+ |

**Losing the table costs liveness, not safety, and it can be rebuilt.**
- **Effect:** without it the combiner can't produce signatures, so the validator stops signing for the affected
  slots.
- **Rebuild:** chain starts derive deterministically from the nodes' PRF key shares (kilobytes, easy to back up), so
  any t nodes can rerun the MPC for just the lost range: about 100–300 GB per node, 13–40 minutes at 1 Gbps, per
  ~3-day window. The values come out identical and are checkable against the commitment made at key generation.
- **Mirrors:** the table is public, so anyone can host one.
- **Not Ethereum blobs:** they're pruned after about 18 days and priced per byte, so they suit short-term
  distribution at most.

**What can be prepared ahead of time:**
- **MPC preprocessing.** The random correlations the MPC consumes don't depend on the key. They can be generated
  continuously at low priority, nearly free in bandwidth with pseudorandom secret sharing.
- **The key itself.** Slots are independent, so key generation splits into resumable chunks. It can be throttled,
  scheduled off-peak and restarted per chunk. Next year's key is built during the current key's last month or two.
- **Encoding randomness.** It must be fixed *after* the message is agreed (§10). Its commit-reveal can ride on QBFT
  messages, adding no extra round.
- **The first key.** It can be short (6 days, under an hour to generate) so a validator activates fast, then rotate
  to a 12-month key. That costs one extra rotation.

## 7. A validator's life with threshold leanSig

![Lifecycle](docs/fig/lifecycle.svg)

| Stage | What happens | Resources |
|---|---|---|
| Key generation (MPC) | all nodes jointly hash every chain; resumable chunks | §5 table; background, overlapped with the live key |
| Store the public table | f+1 replicas, or an untrusted remote store with prefetch | §6 table |
| Every slot | QBFT agree → reveal ρ → PRF shares → combine → publish | ~1.5 KiB per node; milliseconds of compute |
| Every ~3 days | prefetch the next window of the table | ~0.6 GB per validator |
| Operator change | `F_hash`: rotate early (new key). `F_lat`: reshare | one extra rotation, or open research |
| Every 12–18 months | rotate to the pre-built next key | ~0.3% of annual reward today (queue plus ~27 h without reward) |

## 8. Ethereum design decisions that make or break DVs

| Priority | Decision | Why |
|---|---|---|
| **Must** | encoding randomness ρ supplied by the signer after the message is agreed (not derived from the secret seed) | otherwise every signature needs a PRF inside MPC (≈ 2¹⁵ BLAKE2s calls), which misses the slot |
| **Must** | staking in groups stays an explicit design goal | Vitalik, ethresear.ch 2026-07: "personally strongly in favor"[^elc] |
| Should | key rotation without exit and re-deposit, every ≤ 12–18 months (the Extremely Lean Chain's "option 2") | caps key generation at a yearly background job; operator changes at rotation. Without it: pick a key range up front and exit at its end |
| Should | index proposal keys by proposal duties assigned, not by slot | nearly halves key generation |
| Should | higher maximum balance (2¹⁷–2²⁰ ETH, i.e. 131k–1.05M ETH) | another 64–512× fewer keys per ETH after 2048 |
| Should | fewer chain steps per slot, v·(2^w − 1) | cost is linear in it |
| Nice | arithmetic-friendly hash | 2–10× cheaper MPC than BLAKE2s and enables FHE alternatives, but Ethereum is moving to classic hashes for safety; we plan for BLAKE |
| Nice | no ~27 h reward gap on rotation; spec-level signing records; explicit slashing rules | small costs and clarity |

- **Equivocation rules don't help.** "Slashing requires both payloads to be valid" doesn't stop a forgery: the
  attacker grinds the free randomizer ρ, not the payload.
- **Daily keys would suit DVs.** *The Extremely Lean Chain* (daily fresh public keys) shrinks each key generation to
  minutes and the public table to about 0.2 GB per validator, at the cost of a daily MPC liveness duty.

Full analysis: [`docs/ethereum-design-decisions.md`](docs/ethereum-design-decisions.md).

## 9. The journey and its critical path

![Roadmap](docs/fig/roadmap.svg)

1. **Ethereum asks** (ranked in §8).
   - encoding randomness that a threshold signer can fix after the message (must);
   - staking in groups kept as a design goal (must);
   - cheap key rotation or consolidation every 12–18 months, without the reward gap;
   - durable per-slot signing records;
   - awareness that each chain step per slot costs DV key generation linearly.
2. **An XMSS / leanSig-level security proof.** The paper proves the one-time scheme; XMSS is a sketch.
3. **A dealer-based prototype** in charon on a lean devnet, for real signing, combining and storage numbers.
4. **A purpose-built Boolean MPC key generation** for BLAKE2s: 3–4 parties, pseudorandom preprocessing, chunked and
   resumable. First target the 6-day key, then 12-month keys.

Alongside, but needed before production: robustness (identify and evict a misbehaving node), operator changes, and
an audit.

## 10. Things easy to miss

- **Bandwidth costs money on metered cloud.** 12–35 TB per node per validator-year is roughly $0.6k–3k per node at
  typical cloud egress prices. That's a large share of a 32-ETH validator's reward, negligible for consolidated
  validators or unmetered links.
- **ρ must be unpredictable to whoever picks the message.** If ρ were derived from public data, a Byzantine leader
  could search for two messages with the same encoding (about 2⁶⁴ work), and one honest signature would then sign both.
- **Key generation is a new liveness risk.** A multi-day MPC with one Byzantine node can abort. It needs identifiable
  abort and per-chunk restart. Twelve-month keys under an 18-month cap leave six months of slack.
- **Lean consensus slashing rules aren't final.** The cost of the black-box attack above (framing) depends on them.
- **Combiner availability.** Whoever combines needs the public table. Keep f+1 replicas, or the remote store.
- **Backups are easy.** Secret shares are kilobytes, and the public table can be re-downloaded or rebuilt.

**Beyond these, worth considering:**
- **The migration burst.** When BLS validators move to PQ keys, every DV needs a key generation at roughly the same
  time. Fleet-wide MPC capacity becomes the bottleneck, so stagger it, and plan for a quantum-emergency rush.
- **The dual-stack period.** During the transition a DV may run BLS and leanSig duties side by side.
- **The aggregator role.** Lean aggregators produce zk proofs (leanVM). That needs no secrets, so one node can do it,
  but it needs proving hardware.
- **Network-level privacy.** With daily keys, the cluster's daily MPC traffic pattern could link otherwise unlinkable
  identities.
- **Ceremony UX.** A key generation that takes hours to days needs progress reporting, checkpointing and clear
  failure handling in tooling such as the launchpad and charon.
- **Joint asks with other DVT teams.** SSV and Anchor will face the same Ethereum design decisions; aligned asks carry more weight.
- **Formal verification.** The EF has machine-checked XMSS proofs in Lean; extending them to the threshold setting
  would de-risk the XMSS-level proof gap.

## 11. Verdict

- **Signing: good to go (in principle).** Non-interactive, cheap, standard output, fits the slot.
- **Trust minimisation, meaning no single point of failure: needs work.**
  - *Safety:* a dealer-free key generation (Boolean MPC over BLAKE2s), because a dealer or TEE is a single point of
    compromise and black-box shortcuts are insecure[^kk].
  - *Liveness at runtime:* the periodic MPC must complete before each rotation, and the public table must stay
    available (Reed–Solomon or mirrors; rebuildable by MPC).
- **Key generation cost: viable as a background process with yearly rotation.** Untenable for multi-decade keys.
  Black-box shortcuts are insecure. A TEE dealer is acceptable only as a prototype step. FHE only makes sense if
  Ethereum keeps an arithmetic-friendly hash ([`docs/alternatives.md`](docs/alternatives.md)).
- **Readiness for Ethereum: research.** Preprint-stage cryptography, no implementation, and protocol choices still
  open at the EF (rotation, hash, randomness) that move the cost by large factors.

## References

[^prawns]: Boneh, Bünz, Justin D., Litchev, Nazirkhanova. *PRAWNS: Threshold Hash-Based Signatures from Threshold PRFs*. IACR ePrint 2026/2142. <https://eprint.iacr.org/2026/2142>; research preview <https://lclhost.org/blog/prawns/>
[^kk]: Kondi, Kumar. *A Black-Box Impossibility Result for Threshold Signing Standard Hash-Based Signatures*. IACR ePrint 2026/2194. <https://eprint.iacr.org/2026/2194>
[^elc]: Buterin. *The Extremely Lean Chain*. ethresear.ch, July 2026. <https://ethresear.ch/t/the-extremely-lean-chain/25369>

Further reading: Bünz, Rothblum, Wang, *Flock: Fast Proving for Batch Boolean Computations*, ePrint 2026/1329
<https://eprint.iacr.org/2026/1329> · leanSig <https://github.com/leanEthereum/leanSig> · leanSpec
<https://github.com/leanEthereum/leanSpec> · leanVM <https://github.com/leanEthereum/leanVM> · Stoffel MPC
<https://stoffelmpc.com> · HoneyBadgerMPC, ePrint 2019/883 <https://eprint.iacr.org/2019/883>

## Repo map

| Path | What |
|---|---|
| [`docs/prawns.md`](docs/prawns.md) | PRAWNS construction, security conditions, statefulness, Kondi–Kumar and our leakage numbers |
| [`docs/dkg-and-mpc-costs.md`](docs/dkg-and-mpc-costs.md) | cost model: per-hash MPC costs, BLAKE2s and Poseidon DKG tables, storage, preprocessing |
| [`docs/ethereum-design-decisions.md`](docs/ethereum-design-decisions.md) | ranked Ethereum asks, maximum balance, equivocation rules, The Extremely Lean Chain |
| [`docs/alternatives.md`](docs/alternatives.md) | helpers that may only cost liveness, TEE, FHE, Stoffel MPC, Flock |
| [`docs/leansig.md`](docs/leansig.md) | leanSig parameter sets, key generation structure, slot usage, aggregation interface |
| [`tools/`](tools/) | `cost_model.py` (all cost tables; `--blake` for §5–6), `kk_leak.py` / `kk_multitarget.py` (leakage), `figs.py` |
| [`doc/`](doc/), [`mpspdz/`](mpspdz/) | **prior work (2025)**: *Towards Threshold Hash-Based Signatures for Post-Quantum Distributed Validators* (A. Adomnicăi, DV Labs) and MP-SPDZ Poseidon2 benchmarks, cited by PRAWNS as ref [2]. Superseded, but its measured MPC costs calibrate our model. |

Sources: PRAWNS (ePrint 2026/2142); Kondi & Kumar (ePrint 2026/2194); Flock (ePrint 2026/1329); Buterin, *The Extremely Lean Chain* (ethresear.ch/t/25369);
[lclhost.org/blog/prawns](https://lclhost.org/blog/prawns/); leanEthereum leanSig / leanSpec / leanVM / pm (October
2026); Stoffel Labs repositories; this repo's 2025 benchmarks.
