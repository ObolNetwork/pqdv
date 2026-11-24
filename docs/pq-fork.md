# The `pq` emergency fork and EIP-8483, read for distributed validators

A snapshot from 2026-11-24 of two live designs, both moving weekly:
- **consensus-specs `pq` branch** (`specs/_features/pq`, at `4c296784b`): "an emergency fork for when elliptic curve
  cryptography can no longer be trusted". It keeps Gasper, swaps BLS for leanXMSS, and proves signatures with STARKs.
  The `pq-dc` branch is the same fork on decoupled consensus (EIP-8453).
- **[EIP-8483](https://ethereum-magicians.org/t/eip-8483-post-quantum-material-registration/30186)** (EIPs PR #12609,
  Draft; consensus-specs PR #5809): the registry the `pq` branch builds on. It is an alternative to
  [EIP-8450](eip-8450.md). The consensus-specs PR for EIP-8450 (#5782) was closed as "a different direction".
  Related: EIPs #12235 (PQ-ready deposit contract), #12604 (PQ PeerDAS), #11777 (PQ attestation aggregators).

Numbers come from `tools/cost_model.py --pq`.

## TL;DR

- **Gasper isn't the problem. Fixed leaf allocation is.** Every validator message except attestations signs at
  `8 × slot + offset`, so a bottom tree covers 8,192 slots (27 hours). Duties arrive about an epoch ahead, so a DV
  must build every window's tree: **34–103 GB of MPC per validator per node per day** (2.8–8.4 Mbps), or 12–36
  validators per node on half a 200 Mbps link. Dense allocation would make that **~100× smaller**. `pq-dc` is the same
  or slightly worse.
- **The VRF tree is big, but it doesn't block us.** It has one leaf per slot (depth 31). The owner can overwrite the
  root before the fork, but it's frozen from the fork on.
  - **Built in MPC**, 51 years of real leaves cost **0.6–3.9 TB per validator per node** (7–43 hours at 200 Mbps).
  - **Built in the clear** from a seed every operator holds, it costs an hour of CPU. Any one operator could then
    predict the validator's RANDAO reveals, just as a solo staker can predict its own. That loses a threshold
    property but costs no safety.
- **Registration goes only through the withdrawal address** (EIP-8483), and **unregistered validators are exited at the
  fork**. A DV's operators can generate the keys, but the stake owner's withdrawal address has to submit them. A
  withdrawal contract that can't call the new predeploy exits all of its validators.
- **Exits change.** Voluntary exits become execution-layer requests signed with leanXMSS at a reserved leaf, so
  pre-signed BLS exits stop working at the fork. Clusters need to pre-sign leanXMSS exits.
- **Helps DVs:**
  - attestations sign one leaf per target epoch, so that range is dense: one tree per ~291 days;
  - aggregators are sampled, so there are no selection proofs;
  - there are no sync committees.

## 1. What the fork specifies

| | `pq` branch |
|---|---|
| Consensus | Gasper (`pq-dc`: decoupled consensus, with a 1,024-member head-vote committee per slot) |
| Signature | leanXMSS, 2,404 B; blocks carry one STARK `proof` over their attestations' signatures |
| Leaf map | reserved leaves `[0, 2^15)` for exits, preregistrations and other one-offs; attestations at `2^15 + target_epoch`; builder bids in their own range; everything else at `2^15 + 2^29 + 2^30 + 8 × slot + offset` |
| Offsets per slot | proposer, aggregate, PTC, proposer preferences, payload envelope (`pq-dc` adds head vote) |
| RANDAO | the slot's VRF secret plus its Merkle branch, from a depth-31 tree registered before the fork |
| Aggregators | an aggregation committee per beacon committee, sampled by balance; no selection proofs |
| Registration | EIP-8483: 64 bytes (XMSS key + VRF root) from the **withdrawal address**, with a leanXMSS proof of possession checked by the predeploy |
| Unregistered | given an unusable key derived from the BLS key, exited at the fork, withdrawable 2^14 epochs later; `0x00` credentials stay locked |
| Deposits | no signature; a leanXMSS-signed preregistration binds key, withdrawal credentials and VRF root |
| Exits | execution-layer requests, leanXMSS-signed, verified by the system contract; anyone can submit one |

## 2. Issues for distributed validators

### Issue 1: fixed per-slot allocation costs ~100× the MPC

- **Why it bites.** A bottom tree covers 2^16 consecutive leaves. Fixed allocation spends 8 of them on every slot
  whether or not the validator has a duty there. Proposer, PTC, aggregation and head-vote assignments come about an
  epoch ahead, and a tree takes 36–109 minutes of MPC at 200 Mbps. So a DV can't wait to see its duties: it has to
  build every 27-hour window.
- **Filler helps a little.** Offsets the validator never signs at (3 of 8 on `pq`, 2 on `pq-dc`) can be random filler.
- **What it costs, per validator per node:**

  | allocation | MPC per tree | average load | validators per node on half of 200 Mbps |
  |---|---|---|---|
  | `pq`, slot duties | 34–103 GB per 27 h | 2.8–8.4 Mbps | 12–36 |
  | `pq-dc`, slot duties | 41–123 GB per 27 h | 3.3–10 Mbps | 10–30 |
  | attestations, one leaf per epoch | 55–164 GB per 291 days | 0.02–0.05 Mbps | ~2,000–5,700 |

- **Top layer.** With one top key per window, 34 years of slot duties need ~11,000 real top keys, not 2^12. That's
  9–27 GB at registration, still minutes.
- **This is pqdv ask #2.** We asked EIP-8450's switch fork for dense allocation; `pq` picks the fixed schedule.
- **Ask:** per-duty ranges with signer-chosen leaves, as attestations already do by target epoch. The verifier checks
  the range, and two messages at one leaf count as equivocation. A validator's slot duties come to a handful a day, so
  one tree would last months.

### Issue 2: the VRF tree, one secret per slot for life

- **The structure.**
  - Leaf `slot` is `keccak256("VRF_LEAF" ‖ secret ‖ slot)`, at depth 31.
  - The RANDAO reveal is the slot's secret plus its branch.
  - Before the fork, the owner can overwrite a registration, as long as both halves are new. From the fork on, the root
    "cannot be changed".
- **Three ways for a DV:**

  | approach | cost per validator per node | property |
  |---|---|---|
  | **every operator holds the VRF seed**; tree built in the clear | ~1 CPU-hour, no MPC | any one operator can predict the RANDAO reveals, like a solo staker. No forgery, no slashing risk. A departed operator keeps that knowledge for life |
  | **MPC, 51 years of real leaves**, filler elsewhere | 0.6–3.9 TB, 7–43 h at 200 Mbps | nobody can predict reveals; seed or secret shares are reshared on operator changes |
  | **MPC, 3 years of real leaves** | 40–242 GB, 27 min–2.7 h at 200 Mbps | needs a way to renew the root after the fork, which it forbids |

  1–2 Keccak-f per leaf: 1 if each secret is a local threshold-PRF term; 2 if it's derived from a Shamir-shared seed
  as the spec derives it, which keeps resharing simple.
- **Opening is cheap.** A proposal opens one secret: either a threshold-PRF reconstruction, or one Keccak-f in MPC
  computed during the proposer lookahead.
- **Upgrade path before the fork.** Register with a shared-seed tree now, then overwrite it with an MPC-built tree
  (and a new leanXMSS key) before the fork.
- **Ask:** let the VRF root be renewed after the fork, or give the VRF tree two layers like leanXMSS, so threshold signers can
  commit a few years at a time. Failing that, say that leaves a validator will never open may be arbitrary. Otherwise
  implementations may assume the whole tree derives from one seed.

### Issue 3: registration belongs to the withdrawal address

- **Who acts.** EIP-8483 honours a request only from the execution address in the withdrawal credentials. Operators
  generate the leanXMSS key, VRF root and proof of possession, and hand 64 bytes plus the proof to the owner.
- **Withdrawal contracts.** A contract can register only if it can call the predeploy. Upgradeable contracts and
  contracts with a generic call can. Immutable ones can't, so their validators are exited at the fork.
- **No operator path.** EIP-8450's BLS-authorized registration doesn't exist here. charon's role is to produce the
  material and the proof; the owner submits.
- **Overwrites.** The owner can overwrite a registration at any time. If a key generation is rerun, the cluster
  keeps signer state for every key it handed over until the fork settles which one is registered.

### Issue 4: deposits, preregistrations and exits use reserved leaves

- **Each one-off message consumes a reserved leaf.** The proof of possession (leaf 0 in EIP-8483), preregistrations
  and each pre-signed exit take one of 2^15 reserved leaves, in bottom tree 0. That tree can be a few real one-time keys plus filler.
- **Pre-signed exits.** Today's pre-signed BLS exits are void after the fork. Clusters that hand exits to stake
  owners need to pre-sign leanXMSS exit requests. Each uses a fresh reserved leaf, so a cluster has to record which
  leaves it has spent.
- **Deposit front-running.** New validators preregister, signed at a reserved leaf, before depositing. That's one
  more threshold signature in the cluster-creation flow.

### Issue 5: STARK aggregation for aggregators

- **Who proves.** Aggregators prove the signatures they aggregate with a STARK, in a 2.4-second budget.
- **Only one node needs to.** The inputs are public, so one node in the cluster can prove; the others check and
  co-sign the `AggregateAndProof`.
- **Open question:** prover cost per aggregate on operator hardware.

## 3. What it means for the roadmap

- **Under EIP-8483, the VRF tree must be final by the fork.** Registration carries the VRF root. Overwrites are allowed
  until the fork, so an MPC-built tree can replace a shared-seed one. The top layer is minutes; the VRF tree
  dominates.
- **Under an emergency fork, timing is set from outside.** Validators that haven't registered are exited, so
  registration tooling, including the owner hand-off, has to exist before the fork is scheduled.
- **The shared-seed VRF is the fallback.** If an emergency comes first, a cluster can register with an in-the-clear
  VRF tree and the MPC leanXMSS top layer: minutes per validator.
- **charon's build order:**
  1. top-layer MPC with the proof of possession;
  2. VRF tree, shared seed first, MPC later;
  3. owner hand-off of the 64 bytes and the proof;
  4. leanXMSS pre-signed exits.

  BLS-authorized registration stays useful only if EIP-8450's path survives.
