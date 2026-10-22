# PRAWNS for distributed validators: technical notes

Source: Boneh, Bünz, Justin D., Litchev, Nazirkhanova, *PRAWNS: Threshold Hash-Based Signatures from Threshold
PRFs*, IACR ePrint 2026/2142 (received 2026-09-21, preprint, no venue, no code). Page numbers are the paper's.
Related: Kondi & Kumar, *A Black-Box Impossibility Result for Threshold Signing …*, ePrint 2026/2194.

Labels: **[P]** = stated in PRAWNS, **[KK]** = stated in Kondi–Kumar, **[us]** = our inference for Obol / leanSig.

## 1. Construction

**What is thresholdized [P §3.1, pp. 8–9].** Only the secret values of each Winternitz one-time key. Chain `i`,
position `j` has value `y[i,j] = f^j(x_i)`.

**Key generation (dealer).**
1. Run the threshold-PRF setup to get a master key `msk` and shares `sk_1..sk_n`.
2. Set every chain start to `x_i = F(msk, (i, 0))`.
3. Hash each chain to its top and publish `pk` (for XMSS, the Merkle root over the tops).
4. Publish the **combiner public key** `cpk[i,j] = y[i,j] ⊕ F(msk, (i, j))` for every middle position. Top values are
   published in the clear.

`cpk` has ℓ·(d−1) entries per one-time key (Remark 2). It is public: "the combiner holds no secrets" (§3.4, p. 13).

**Signing.** The message determines a "cut" `(j_1..j_ℓ)`, one position per chain. Each signer `k` sends
`σ_k[i] = Eval(sk_k, (i, j_i), ec = m)`, with the **message as the evaluation context**.

**Combining.** From `t` shares the combiner rebuilds `F(msk,(i,j_i))`, then outputs per chain:
- position 0: the PRF value itself;
- middle positions: `cpk[i,j_i] ⊕ F`;
- the top position: the public top value.

The result is a plain WOTS/XMSS signature, and **verification is unchanged**.

**Why "context-aware" [P §2, Remark 3].** Shares made under different contexts must not combine. Otherwise an
attacker pools shares from different messages (about 1.5t, even 4t/3, in total) and assembles a signature for a new
cut. The paper calls context-awareness its main contribution (p. 16).

### The two threshold PRFs

| | `F_lat` (lattice, §4) | `F_hash` (combinatorial, §5) |
|---|---|---|
| Basis | key-homomorphic LWR PRF ⌊⟨H(x), msk⟩⌉_p, Shamir-shared `msk`, plus Shamir zero-shares bound to (context, quorum) | replicated sharing: one key `k_S` per (t−1)-subset `S`; output = ⊕ F(k_S, x); pairwise masks give context-awareness |
| Keys per node | O(n log n), or O(n) with Brakerski et al. points | C(n−1, t−1): 3 (3-of-4), 15 (5-of-7), 84 (7-of-10) |
| Combine | approximate (error ≤ t): try 2t+1 candidates, or 3–4 if low bits are dropped (p. 17) | exact XOR / field sum |
| Security | **static** only (Thm 4.1, LWE via a new Poly-LWR assumption, random oracles) | **adaptive** (Thm 5.1, PRF + random oracle; loss 2·C(n, t−1)) |
| Scales to | large n, t ("practical for, say, a 30-out-of-40", p. 16) | small n, t only (C(n,t) must be small) |
| Resharing / changing n or t keeping `pk` | "standard update protocols" (§6, p. 27); no protocol given | changes the PRF itself, so `cpk` and the chain starts change: new key |
| Concrete parameters / benchmarks | none | none |

[us] For n ≤ 10, `F_hash` is the natural choice. Its weakness is operator changes. `F_lat`'s proof condition
(B_χ·N^{4N}·p/q negligible) suggests q around 2^300 at N = 10, so LWE dimensions in the thousands: heavy, but only
on the signing side.

## 2. Statefulness and the threshold condition

- **The condition [P p. 4, Fig. 3].** No signer coordination is assumed. To stop two disjoint quorums signing two
  messages under one one-time key, the scheme requires **t > (n + f)/2**. "If at most f ≤ n/3 parties are corrupt,
  then the threshold … must satisfy t > (2/3)n. This is inherent … where the signers do not communicate with each
  other" (p. 4).
- **Charon's threshold meets it [us].** `t = ceil(2n/3)` satisfies `f < 2t − n` at BFT `f`:

  | n | t | f allowed | BFT f |
  |---|---|---|---|
  | 4 | 3 | ≤ 1 | 1 |
  | 7 | 5 | ≤ 2 | 2 |
  | 10 | 7 | ≤ 3 | 3 |

  QBFT agreement before signing adds a second layer.
- **The per-node rule [P].** Never sign two messages for the same one-time key (Fig. 3). [us] That needs a durable
  per-slot record (leanSpec PR #1204 is adding one for single signers). A node that loses its record counts toward `f`.
- **Few-time schemes [P p. 4].** HORS/FORS need t > (wn + f)/(w+1) to keep w-time security. Not relevant to leanSig,
  which is one-time per slot.
- **leanSig encoding randomness [us].** leanSig grinds a randomizer ρ until the encoding hits the target sum, and
  derives ρ from the *secret seed*. Two different ρ for the same slot give two cuts, which breaks one-time security.
  - **Construction (suggested by EF researchers, Oct 2026):** ρ = H + i, where H = threshold-PRF(key, message),
    computed with the same context-aware threshold PRF, and i is the smallest integer that makes the encoding valid.
    Grinding is then public hashing; only H needs the secret.
    - Nodes attach their H shares to QBFT commit messages, so it costs no extra round.
    - It is unpredictable below threshold, deterministic per message, and has no last-revealer bias (unlike
      commit-reveal).
    - The paper discusses the same issue for eTCR encodings (Remark 4) and hypertree pruning (§3.4, p. 15).
  - **The context should bind (slot, message, ρ).**
  - **Status:** the leanXMSS threshold sketch derives the randomizer base from a threshold PRF in the same way, and
    EIP-8450 makes randomizer derivation "not consensus-critical". Its security proof still assumes a seed-derived
    ρ.

## 3. Security model and gaps

- **Theorem 3.1:** adaptively secure threshold WOTS, if:
  - the threshold PRF is adaptively secure;
  - the cut function is collision-resistant and cover-free;
  - `f` is second-preimage resistant on (d−1)-iterates (a new assumption);
  - `H` is target-collision-resistant.

  Tweakable hashes as in SPHINCS+/leanSig "work equally well" (Remark 1).
- **Only the one-time scheme is fully proven.** XMSS, XMSS-MT, FORS/PORS and hypertree pruning are prose sketches (§3.4).
- **No robustness [P p. 15].** "Both constructions, as described, are not designed to detect a party that is trying to
  actively disrupt the PRF evaluation process." Suggested fixes are leveled homomorphic signatures or NIZKs, not
  worked out.
  - [us] A bad share shows up as a failed verification or no matching candidate, but isn't attributable.
  - [us] With n − t spare nodes the combiner can retry other quorums. Shares are quorum-specific (`Eval` takes the
    quorum `J`, p. 15), so a retry needs fresh shares.

## 4. Key generation: the limitation

- **Abstract (p. 1):** "One limitation of the framework is that it does not support an efficient distributed key
  generation protocol (DKG)."
- **§6 (p. 27):** "A DKG protocol for our scheme would require evaluating the one-way function f : Y → Y in an MPC to
  generate the combiner's public key cpk. This can be costly, although recent work [35] suggests that for small n it is
  not impractical thanks to recent advances in MPC. An interesting direction for future work is to design an efficient
  DKG protocol for hash-based signatures that is practical for modest values of n and t, say for a 20-out-of-30
  scheme." ([35] is *Dealing Haystack*, ePrint 2026/1804.)
- **Hybrid idea (§3.4, p. 14), for XMSS-MT:** run an MPC to generate `cpk` per tree, "the MPC only needs to run once
  every few hundred signatures". [us] Today's leanSig is a single tree, so this doesn't apply directly; with
  [two-layer keys](two-layer-keys.md) it does, and it becomes our primary design: one MPC per ~3-day window.
- **The paper gives no cost figures.** Ours are in [`dkg-and-mpc-costs.md`](dkg-and-mpc-costs.md).

**What a dealer-free DKG computes [us].** Per slot per key, inside MPC: shared chain starts, the 7 chain steps on
each of 46 chains, and the masks. Then it opens the masked middle values and the tops. Leaves and the Merkle tree over
the tops are public, so they are computed in the clear.

The two PRFs differ sharply here:
- **`F_hash`:** each node computes its `F(k_S, ·)` terms locally, which yields additive shares of chain starts and
  masks for free. Only the chain hashing needs MPC.
- **`F_lat`:** the PRF itself needs a rounding step inside MPC (bit decomposition), plus conversion into KoalaBear
  field elements. That is substantially more expensive, and unquantified.

**Dealer options.** Single operator, TEE with attestation and erasure, or a ceremony. The dealer knows `msk` and can
sign anything until it erases. With `F_lat`, a dealer bootstrap followed by a distributed reshare could at least make
later operator changes dealer-free.

## 5. Kondi–Kumar: why the hashing must be inside MPC

**The result [KK].**
- **Model.** A "valid ROM-DKG" is any key generation in which parties use the hash only as a black box (every hash
  query is made in the clear by some party). Correctness is all that's required.
- **Extractability.** W-OTS+ is *extractable*: a valid generator must query each chain's base preimage, otherwise
  roughly 1/w of messages couldn't be signed.
- **Theorem 5.1.** With extraction size `m`, an `n = m + k` party ROM-DKG allows forgery under `m` corruptions. "For
  W-OTS+ … no secure black-box protocol for threshold signing W-OTS+ can exist for n > 67 parties. For XMSS … as low
  as n > 87."
- **Small n (§6).** Pigeonhole: in any black-box m-party DKG, m−1 corrupted parties learn at least ℓ − ⌊ℓ/m⌋ chain
  bases with probability ≥ 1/m. Table 1 (w = 16, ℓ = 64) gives forgery probability > 2⁻²² at m = 4. The paper:
  m = 2 "essentially halves the 256-bit security".
- **Where PRAWNS sits.** KK lists PRAWNS among "limited trusted dealer schemes".

**Implications [us].**
- PRAWNS *signing* makes no hash queries on secrets, so KK doesn't touch it.
- Dealer-free key generation must evaluate the chain hash **inside** MPC. "Each party hashes its own chains in the
  clear" is ruled out.
- Even in honest-majority settings the pigeonhole bound bites. One corrupt node of 4, holding 16 of 64 chain bases,
  forges with probability about 2⁻⁸⁴ per trial in our recomputation of KK's dynamic program. That is a large
  concrete-security loss, and leanSig's grinding helps the attacker.

### 5.1 Our numbers: honest-majority and Minimmit-style corruption, leanSig encoding [us]

Kondi–Kumar's small-n table assumes all parties but one are corrupt, so the attack gets *easier* as n grows (> 2⁻¹⁶
per try at 6 parties). Our model is Byzantine instead: a black-box DKG spreads chain-base queries across the nodes,
so `f` colluders learn about `f/n` of each one-time key's chains. We computed exactly how likely a forgery is, for
leanSig's target-sum encoding (46 chains, base 8, sum 200), with `tools/kk_leak.py`. With no leak the model gives
2⁻¹²⁸, matching leanSig's design target.

| corruption model | chains known (of 46) | average slot | best of 3,000 slots | extrapolated best of a year's slots | attack work incl. ~2¹⁰ grinding |
|---|---|---|---|---|---|
| BFT, f < n/3 (n = 4…10) | 12–14 | 2⁻⁴⁰…2⁻⁴⁵ | 2⁻³⁴…2⁻³⁸ | ~2⁻²²…2⁻²⁷ | **~2³²–2³⁷** |
| Minimmit-style, f ≤ n/5 | 8–9 | 2⁻⁵³…2⁻⁵⁸ | 2⁻⁴⁷…2⁻⁵⁰ | ~2⁻³⁵…2⁻³⁹ | **~2⁴⁵–2⁴⁹** |

(`tools/kk_multitarget.py` samples the per-slot spread. The year-level column extrapolates the sampled tail at about
one bit per bit of target selection, so it's an estimate.)

**What a forgery buys.**
- **Slots not yet signed are safe.** Forging one needs about 18 known chains, beyond either corruption model, because
  the unknown chains' public tops alone exceed the target sum.
- **Signed slots are not.** After the DV signs a slot, the colluders can forge a *second* signature for it. That is
  equivocation, i.e. slashing evidence that frames the validator. Slashing evidence doesn't need to be timely, so they
  can grind offline and pick the weakest of millions of signed slots.
- **Timing only blocks some uses.** Real-time forgeries (a competing vote or block within the slot) are out of reach.
- **Other nodes' slashing protection is irrelevant.** The forgery is built offline by the attacker alone.

Across a large operator's validators this becomes correlated slashing. So black-box DKGs are rejected at any n.

**Related caveat (ρ).** If leanSig's encoding randomizer ρ were derived from public data, whoever picks the message
(e.g. a Byzantine QBFT leader) could search for two messages with the same encoding. That is a birthday search over
the roughly 2¹²⁸ valid encodings, so about 2⁶⁴ work by our estimate, and one honest signature would then cover both
messages. The threshold-PRF construction (§2: ρ = threshold-PRF(key, message) + i) closes this. Nobody below
threshold can predict ρ for a candidate message, so the offline search is impossible.

## 6. Open problems (authors' list, §6) and ours

| Item | Owner | Matters for Obol because |
|---|---|---|
| Efficient DKG | authors, us | cost model in `dkg-and-mpc-costs.md` |
| Adaptive security for `F_lat` | authors | `F_lat` is the only variant with key-preserving resharing |
| Changing n/t, proactive refresh | authors (asserted standard for `F_lat`) | operator changes (charon cluster edits) |
| Robustness / identifiable abort | authors, us | a Byzantine node can stall combining |
| Silent setup | authors | not needed for DVs |
| XMSS-level proof with leanSig's target-sum encoding and ρ handling | us, leanSig team | correctness of the whole stack |
| Two-layer validator keys (or rotation) in lean consensus | Ethereum | turns one huge DKG into a small one-off plus per-window jobs ([two-layer-keys.md](two-layer-keys.md)) |
