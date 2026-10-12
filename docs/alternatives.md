# Alternatives and building blocks

Design rule: **a helper may cost liveness, never safety.** If it misbehaves, the worst outcome should be a missed
duty or a failed key generation, never a key compromise or a forgeable validator.

## 1. Which helpers fit the rule

| Helper | Sees secrets? | Failure mode | Verdict |
|---|---|---|---|
| Host or CDN for the public combiner table | no (public) | serves bad or no data, so signatures fail to verify | ✓ liveness only. Commit to the table's hash at key generation so tampering is detectable |
| Network relays | no | drops messages | ✓ liveness only |
| Untrusted FHE evaluator (keys threshold-shared in the cluster) | no (ciphertexts only) | wrong output, so the key or table is broken | ✓ liveness only, *if* the FHE decryption key stays with the cluster (§3) |
| PRAWNS dealer | yes (master key) | can forge anything until it erases | ✗ safety |
| Dealer inside a TEE | yes, behind hardware | enclave break or side channel means compromise | ✗ safety rests on hardware; **prototype step only** |
| Third party supplying MPC multiplication triples | yes, in effect: triples plus the values opened during MPC reveal the secrets | can learn every secret | ✗ safety. Nodes must generate their own preprocessing, ideally silently (PRSS/PCG). The 2025 doc in `../doc/` suggests otherwise; that is superseded |
| FHE provider whose own key-management network decrypts | yes, via its key holders | its key holders can decrypt | ✗ safety |

## 2. TEE dealer

- **Fastest path to a working prototype.** One machine generates the key, the shares and the public table, then
  erases. Compute is minutes per validator-year in plaintext.
- **Not a production answer.** Safety would rest on enclave integrity, attestation and erasure.
- **Rotation limits the damage.** The 12–18-month rotation bounds how long any prototype-era key lives.

## 3. FHE: an untrusted evaluator instead of a dealer

**Design.**
1. Nodes run a threshold-FHE key setup (lattice-based, linear, so cheap; Lattigo and OpenFHE ship multiparty modes)
   and encrypt their local PRF contributions.
2. An untrusted server evaluates the hash chains on ciphertexts.
3. Nodes threshold-decrypt **only the public outputs**: chain tops and the masked table.

Two independent evaluators running the same deterministic evaluation can be compared. Alternatively, spot-check by
decrypting a few hundred random slots and discarding them (they become unusable) before deposit.

**Blast radius.**
- **Evaluator misbehaves:** liveness only.
- **≥ t nodes collude:** the same assumption as the cluster itself.
- **FHE scheme broken:** a lattice-assumption failure, the same family as ML-KEM/ML-DSA.

**Cost decides it.** The work to hide is everything the dealer does on secret data, which is essentially all the
chain hashing:
- **BLAKE2s (expected):** about 4.6 × 10⁹ compressions, or roughly 10¹⁴ binary gates, per validator-year. That's
  about 15 CPU-minutes in the clear. Under FHE (gate bootstrapping, or bit-sliced BGV), our rough estimate is **months
  to years of GPU time per validator-year**. Today's FHE coprocessors and providers don't run anywhere near 10¹⁴ gates
  per validator-year.
- **Poseidon over KoalaBear (if kept):** KoalaBear's p − 1 = 2²⁴·127 suits BGV/BFV batching well. Packing one state
  word per ciphertext across ~32k chains avoids rotations. That's still about 10⁷ bootstraps per validator-year,
  roughly weeks to months of GPU time at 0.1–1 s per bootstrap. Highly uncertain; needs a benchmark.

**Verdict.** Under BLAKE, prefer the Boolean MPC key generation. FHE becomes interesting only if Ethereum keeps an
arithmetic-friendly hash. Then a 1–2 week spike measuring amortised Poseidon-16 over KoalaBear in multiparty BGV/BFV
on one GPU settles it. A third-party FHE provider is acceptable for *evaluation* only, with decryption keys held by
the cluster.

## 4. Stoffel MPC (stoffelmpc.com)

**What it is.** Stoffel Labs, founded 2025, about $1.6M pre-seed. An Apache-2.0 Rust reimplementation of
HoneyBadgerMPC (Lu et al., ePrint 2019/883), plus a DSL, a VM, SDKs and a QUIC networking crate.
- Version v0.1.x; about 230 commits on the MPC crate.
- An external audit is in progress, with findings numbered up to ~278, some high severity. No report is published yet.

**As a building block: weak fit.**
- No KoalaBear field. The VM/DSL is tied to ~255-bit curve fields; the engine is generic, but untested off them.
- Scalar per-share data structures with no SIMD; we estimate 10⁵–10⁶ multiplications per second per node.
- At n = 3t+1 (our 4/7/10-node clusters), preprocessing is detect-and-abort, not robust. Robust needs n ≥ 4t+1.
- The AVSS backend is passively secure by its own docs.
- Boolean/GF(2^k) support exists only on unmerged branches.
- QUIC TLS verification is skipped, and peer pinning is off by default.

**As something to learn from: good.**
1. **PRSS + DN07 preprocessing at n = 3t+1.** It detects cheating by up to t parties with probability 1, with no
   MACs, at about 2.7–2.9 elements per node per multiplication. It also shares PRAWNS `F_hash`'s key structure (one PRF
   key per subset of nodes), so one key-distribution step could serve both signing and key-generation preprocessing.
2. **A robust asynchronous online phase over abortable synchronous preprocessing**, with an explicit n ≥ 4t+1
   versus 3t+1 analysis.
3. **edaBit and Boolean/arithmetic conversion constructions**, if parts of the computation need both worlds.
4. **The audit-finding catalogue** as a pitfall checklist: sender-ID spoofing, session-ID aliasing, unbound
   execution context, and error correction "repairing" a malicious dealer's shares.

## 5. Flock (ePrint 2026/1329)

Bünz, Rothblum, Wang: a hash-based SNARK for batches of standard Boolean hashes. It proves 82k BLAKE3 compressions
per second on one M4 Max core (under 250× native), and covers hash chains and Merkle paths.

**Why it matters to us.** It explains Ethereum's drift from zk-friendly hashes (Poseidon2 → Poseidon1 → BLAKE):
aggregation can prove classic hashes efficiently. That pushes our key generation into Boolean MPC.

**What it doesn't do.** Proving isn't hiding, so it doesn't make hashing secrets in MPC or FHE cheaper. Its one
plausible use for us is making an evaluator's *public* outputs checkable. That can't remove the safety problem of a
helper that sees the secrets.
