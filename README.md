# Post-Quantum Distributed Validators

Research project on practical threshold hash-based signatures for distributed validators over the Beam Chain.

## Poseidon2 over MPC

Experimental benchmarks were conducted using the [MP-SPDZ framework]<https://github.com/data61/MP-SPDZ>.
The file `poseidon2.mpc` implements the Poseidon2 hash function for this framework and is aimed to be copied into `MP-SPDZ/Programs/Source`.
It supports the prime fields defined by Mersenne31, BabyBear and KoalaBear 31-bit primes.
Because this work targets XMSS signatures, it focuses on hash chain calculations.
One can compile the program for the KoalaBear prime by running `./compile.py poseidon2 -P 2130706433 <c> <w>` where `<c>` and `<w>` refer to the number of chunks and their width (in bits), respectively, of the XMSS instantiation.
Then one can run the protocol of their choice by running `./Scripts/<protocol>.sh poseidon2 -N <n> -S 31 -v` where `<n>` refers to the number of parties for the MPC calculation.
For benchmarks over different machines, this repo contains a script `average_bench.sh` which is meant to be run on each machine separately to run a protocol for a given number of iterations in order to average the results over multiple runs.
It requires to run `./Scripts/setup-ssl.sh` on a single machine, copy the resulting keys/certificates in `MP-SPDZ/Player-Data` to the other machines and run `c_rehash MP-SPDZ/Player-Data`.
It also requires to have a file named `HOSTS` which contains the ip adresses of all players. Note that communications is handled with TCP over ports 5000:5009, one can run `sudo ufw allow 5000:5009/tcp` if necessary. Then running `./average_bench.sh <protocol> poseidon2 <num_parties> <party_index> <num_runs>` on each machine for a given `<protocol>` (i.e. `malicious-shamir-party.x`) should work fine.
