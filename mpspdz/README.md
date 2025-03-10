## Poseidon2 over MPC

### Implementation

The file `poseidon2.mpc` implements the Poseidon2 hash function for the [MP-SPDZ framework](https://github.com/data61/MP-SPDZ) and is intended to be copied into the `MP-SPDZ/Programs/Source` directory. It supports the following 31-bit prime fields:

- Mersenne31
- BabyBear
- KoalaBear

This implementation focuses on hash chain calculations as required by XMSS signatures.

### Compilation

To compile the program for the KoalaBear prime, run the following command:

```bash
./compile.py poseidon2 -P 2130706433 <c> <w>
```

Where:
- `<c>`: Number of chunks in the XMSS instantiation
- `<w>`: Chunk width in bits

### Protocol Execution

To run a calculation over MPC with a specific protocol, use the following command:

```bash
./Scripts/<protocol>.sh poseidon2 -N <n> -S 31 -v
```

Where:
- `<protocol>`: Protocol name (e.g., `mascot`)
- `<n>`: Number of parties for the MPC calculation

It is also possible to average the timing results of multiple executions by running

```bash
./average_bench.sh <protocol> poseidon2 <num_parties> <num_runs>
```

Where:
- `<protocol>`: Protocol name that should correspond to a script in the `MP-SPDZ/Scripts` directory (e.g., `mascot`, `mal-shamir`, ...)
- `<num_parties>`: Total number of parties
- `<num_runs>`: Number of benchmark runs
