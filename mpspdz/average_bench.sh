#!/bin/bash

if [ "$#" -ne 4 ]; then
    echo "Usage: $0 <protocol> <program> <num_parties> <num_runs>"
    exit 1
fi

PROTOCOL=$1
PROGRAM=$2
NUM_PARTIES=$3
NUM_RUNS=$4
SECURITY_PARAM=31    # Modify if necessary

total_online_time=0
total_offline_time=0
LOG_FILE="mpc_bench_log_$PROTOCOL_$NUM_PARTIES.txt"

for ((i=1; i<=NUM_RUNS; i++)); do
    echo "Run $i/$NUM_RUNS..."

    ./Scripts/$PROTOCOL.sh $PROGRAM -N $NUM_PARTIES -S $SECURITY_PARAM -v  > "$LOG_FILE" 2>&1
    
    sleep .5

    # Extract the online and offline execution times
    ONLINE_TIME=$(grep -oP 'Spent \K[0-9]+\.[0-9]+(?= seconds \(.* MB, .* rounds\) on the online phase)' "$LOG_FILE")
    OFFLINE_TIME=$(grep -oP 'and \K[0-9]+\.[0-9]+(?= seconds \(.* MB, .* rounds\) on the preprocessing/offline phase)' "$LOG_FILE")
    
    if [[ -n "$ONLINE_TIME" ]]; then
        total_online_time=$(echo "$total_online_time + $ONLINE_TIME" | bc)
    else
        echo "Warning: Could not extract online time from output. Skipping..."
        cat "$LOG_FILE"
    fi
    
    if [[ -n "$OFFLINE_TIME" ]]; then
        total_offline_time=$(echo "$total_offline_time + $OFFLINE_TIME" | bc)
    else
        echo "Warning: Could not extract offline time from output. Skipping..."
    fi

    rm -f "$LOG_FILE"
done


# Compute and print the average times
if [[ "$NUM_RUNS" -gt 0 ]]; then
    average_online_time=$(echo "scale=6; $total_online_time / $NUM_RUNS" | bc)
    average_offline_time=$(echo "scale=6; $total_offline_time / $NUM_RUNS" | bc)
    echo "Average online execution time over $NUM_RUNS runs: $average_online_time seconds"
    echo "Average offline execution time over $NUM_RUNS runs: $average_offline_time seconds"
else
    echo "No valid runs recorded. Please check the output formatting."
fi
