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

### Benchmarking Across Machines

For benchmarking across multiple machines, the repository provides a script `average_bench.sh` to run the calculation for a specified number of iterations and average the results.

#### Setup Instructions
1. Run the SSL setup script on one machine:

   ```bash
   ./Scripts/setup-ssl.sh
   ```

2. Copy the generated keys and certificates from `MP-SPDZ/Player-Data` to the other machines.
3. On each machine, run:

   ```bash
   c_rehash MP-SPDZ/Player-Data
   ```

4. Create a `HOSTS` file listing the IP addresses of all players.
5. Allow TCP traffic on ports 5000–5009 if necessary:

   ```bash
   sudo ufw allow 5000:5009/tcp
   ```

#### Running Benchmarks
On each machine, execute:

```bash
./average_bench.sh <protocol> poseidon2 <num_parties> <party_index> <num_runs>
```

Where:
- `<protocol>`: Protocol name (e.g., `malicious-shamir-party.x`)
- `<num_parties>`: Total number of parties
- `<party_index>`: Index of the machine (starting from 0)
- `<num_runs>`: Number of benchmark runs

