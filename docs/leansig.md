# leanSig: what a threshold scheme has to produce

Snapshot from the leanEthereum repositories (leanSig, leanSpec, leanVM, pm) and `ethereum/cryptography-specs`,
October 2026. Paths are relative to each repository.

## Two parameter sets in flight

| | **A. Devnet set** (leanSig `Devnet 4`, leanSpec `PROD_CONFIG`) | **B. Draft spec** (leanVM `doc/xmss`, cryptography-specs `Xmss/`) |
|---|---|---|
| Hash | **Poseidon1** over KoalaBear (p = 2³¹ − 2²⁴ + 1), x³ S-box; width 16 for chain steps (8 full + 20 partial rounds), width 24 for tree and leaf | **BLAKE2s**, truncated to 128 bits ("a placeholder; SHA2, SHA3, BLAKE3 are actively considered") |
| Chains × steps | 46 chains, base 8 (7 steps per chain) | 42 chains, chain length 8 (7 steps) |
| Encoding | target sum 200 (mean would be 161), aborting hypercube message hash | target sum 195, randomizer ground ~2^14.85 tries |
| Lifetime | 2³² slots | 2³² leaves |
| Public key / signature | 52 B / 2,536 B | 32 B / 1,208 B |
| Chain-start PRF | SHAKE128 keyed by a 32-byte seed | the same tweakable BLAKE2s hash from the seed |

Sources:
- **Set A:** `leanSpec/src/lean_spec/spec/crypto/xmss/constants.py`,
  `leanSig/src/signature/generalized_xmss/instantiations_aborting.rs`, `leanSig/src/symmetric/tweak_hash/poseidon.rs`.
- **Set B:** `leanVM/crates/xmss/src/lib.rs`, `cryptography-specs/EthCryptographySpecs/Xmss/Constants.lean`.

Devnets run set A. Set B is where the cryptography track is heading. Nothing we found says leanSpec has switched.

## Key generation structure (the DKG cost driver)

- **The key commits to its whole range up front.**
  - `key_gen(activation_epoch, num_active_epochs)` (`leanSig/src/signature/generalized_xmss.rs`,
    `leanSpec/.../xmss/interface.py`) snaps the range to whole **bottom trees of 2¹⁶ leaves**, with a minimum of two
    (2¹⁷ slots, about 6 days).
  - It builds every bottom tree in the range plus a top tree over their roots, so the public key fixes every chain
    top in the range.
  - Positions outside the range are random filler, so cost scales with the range, not with 2³².
- **`advance_preparation` only saves memory.** It re-derives the next bottom tree from the seed, so the secret key holds
  two bottom trees. It does not extend the key; extending requires a new public key.
- **Per leaf (set A):** 46 SHAKE128 calls, **322 Poseidon chain steps**, 25 sponge permutations for the leaf, and about
  one Merkle node. Only the 322 chain steps involve secrets.
- **Single-signer timings found:**
  - roughly "1–2 hours in Rust" for a 2¹⁸ activation range on early devnets;
  - "about three hours on your laptop" for 2²⁴ leaves with older parameters;
  - "~days" for the full 2³² tree.

  (pm meeting notes; there's no current-parameter benchmark in leanBench.)

## How validators use keys

- **Slots.** 4 s each, five 800 ms intervals. Block production at interval 0, attestation at interval 1, aggregation at
  interval 2 (`leanSpec/src/lean_spec/spec/forks/lstar/config.py`, `timeline.py`). The XMSS "epoch" is the slot.
- **Every validator attests every slot.**
- **Two keys per validator:** `attestation_public_key` and `proposal_public_key`
  (`leanSpec/.../containers/validator.py`), so key generation cost doubles.
- **No key rotation:** "Fixed lifetime (2³²) to avoid key rotation complexity … Validators can generate fewer keys
  for shorter activation periods" (pm, leanConsensus meeting 08).

## Signing and state

- **Signing steps.**
  1. Grind ρ = PRF(seed, slot, msg, counter) until the encoding hits the target sum (~900 tries for set A, ~2¹⁵ for
     set B).
  2. Walk each chain the encoded number of steps: 200 chain hashes in total (195 for set B).
  3. Attach the Merkle path.
- **The verifier can't tell how ρ was derived.** A threshold signer could agree ρ jointly instead, which needs the
  leanSig team's sign-off on the proofs.
- **State.** "A secret key must never sign two different messages for the same slot" (`interface.py`).
  - leanSpec PR #1204 adds a persistent signing-records table (claim committed before signing): "Concurrent nodes
    sharing a key keep separate records, so exclusive key-store access remains an operational requirement."
  - leanVM PR #279 hardens the one-time-per-epoch invariant in the aggregator.

## Aggregation interface

`leanVM/crates/rec_aggregation/src/aggregation.rs`: `aggregate(children, raw_xmss: Vec<(XmssPublicKey, LeafIndex,
Message, XmssSignature)>, …)`, where "raw signatures are assumed valid". Aggregators need only standard signatures,
so a threshold scheme whose output is a normal leanSig signature needs no protocol change.

## Threshold / DVT in the lean repos

A search across leanSig, leanSpec, leanVM, leanBench, pm, sig.golf and ots.golf found **no** mention of threshold
signing, distributed validators, MPC or PRAWNS in the signature context. This is a gap worth raising with the
leanSig / lean consensus teams: rotation, joint ρ and the hash choice all move the DV cost by large factors
(see [`dkg-and-mpc-costs.md`](dkg-and-mpc-costs.md) §5).

## Maturity and timeline

- **leanSig:** last commit "Devnet 4" (2026-04).
- **leanVM:** moved to BLAKE2s in September 2026. XMSS details are still changing (open PRs on tweaks; digests
  differ between leanVM and cryptography-specs).
- **ots.golf** is still optimising one-time signature verification cost, so v and w may change.
- **No ship date** for post-quantum consensus appears anywhere. The only dated hint is "crypto specs by end-2026;
  2027 for compiler stack and consensus specs/implementations", from a formal-verification talk.
