"""Kondi-Kumar style partial-key-leakage forgery probability for leanSig's target-sum Winternitz.

A black-box (hash-in-the-clear) DKG lets the corrupted parties learn the chain *bases* they queried. With k of v
chain bases known, plus one honest signature (codeword c), a forger needs another valid codeword c' whose digits are
>= c on every *unknown* chain (it can hash those upward) and arbitrary on known chains. Target-sum: every valid
codeword has digit sum T. We compute P = Pr_{c,c' uniform in the layer}[c'_i >= c_i on unknown chains], exactly.
"""
import math, sys

def layer_pairs(v, base, T, k):
    """Exact count of pairs (c, c') in the sum-T layer with c'_i >= c_i on the v-k unknown chains."""
    # state: dict over (sum_c, sum_c') -> count, pruned to sums <= T
    U = [(a, b) for a in range(base) for b in range(base) if b >= a]
    K = [(a, b) for a in range(base) for b in range(base)]
    cur = {(0, 0): 1}
    for idx in range(v):
        moves = K if idx < k else U
        nxt = {}
        for (s, t), n in cur.items():
            for a, b in moves:
                s2, t2 = s + a, t + b
                if s2 <= T and t2 <= T:
                    key = (s2, t2)
                    nxt[key] = nxt.get(key, 0) + n
        cur = nxt
    return cur.get((T, T), 0)

def layer_size(v, base, T):
    cur = {0: 1}
    for _ in range(v):
        nxt = {}
        for s, n in cur.items():
            for a in range(base):
                if s + a <= T:
                    nxt[s + a] = nxt.get(s + a, 0) + n
        cur = nxt
    return cur.get(T, 0)

if __name__ == '__main__':
    v, base, T = 46, 8, 200  # leanSig devnet set A
    L = layer_size(v, base, T)
    for k in [int(a) for a in sys.argv[1:]] or [0, 8, 12, 14, 23, 31, 35, 38]:
        p = layer_pairs(v, base, T, k) / (L * L)
        print(f"known chains {k:2d}/46: forgery probability per random codeword ~ 2^{math.log2(p):.1f}")
