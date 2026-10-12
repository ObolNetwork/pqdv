"""Per-slot forgery probability spread under black-box-DKG leakage (leanSig set A).
For a slot whose honest codeword is c, p(c) = Pr[random layer codeword c' dominates c on the unknown chains].
An attacker who may target any already-signed slot goes after the slots with the largest p(c)."""
import math, random, sys
V, B, T = 46, 8, 200

def suffix_counts():
    # N[i][s] = number of ways chains i..V-1 sum to s
    N = [[0] * (T + 1) for _ in range(V + 1)]
    N[V][0] = 1
    for i in range(V - 1, -1, -1):
        for s in range(T + 1):
            N[i][s] = sum(N[i + 1][s - a] for a in range(B) if s - a >= 0)
    return N

N = suffix_counts()
LAYER = N[0][T]

def sample_codeword(rng):
    c, s = [], T
    for i in range(V):
        r = rng.randrange(N[i][s])
        for a in range(B):
            if s - a >= 0:
                if r < N[i + 1][s - a]:
                    c.append(a); s -= a; break
                r -= N[i + 1][s - a]
    return c

def p_dominate(c, known):
    dp = [0] * (T + 1); dp[0] = 1
    for i in range(V):
        lo = 0 if i < known else c[i]  # first `known` chains are the leaked ones
        nd = [0] * (T + 1)
        for s, n in enumerate(dp):
            if n:
                for a in range(lo, B):
                    if s + a <= T:
                        nd[s + a] += n
        dp = nd
    return dp[T] / LAYER

if __name__ == '__main__':
    known = int(sys.argv[1]); samples = int(sys.argv[2])
    rng = random.Random(1)
    logs = sorted(math.log2(max(p_dominate(sample_codeword(rng), known), 1e-300)) for _ in range(samples))
    q = lambda f: logs[min(int(f * samples), samples - 1)]
    print(f"known {known}/46, {samples} sampled slots: median 2^{q(.5):.1f}, 90th pct 2^{q(.9):.1f}, "
          f"99th 2^{q(.99):.1f}, best 2^{logs[-1]:.1f}")
