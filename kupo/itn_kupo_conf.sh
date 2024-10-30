#! /usr/bin/bash

./bin/kupo \
  --node-socket "/tmp/node.socket" \
  --node-config "/home/orcfax/cardano/network/mainnet/config.json" \
  --since "102295827.1da4e08c0cae0445b85c27688786a00bbd4a478be5cddbb9308ae4c9575b36d4" \
  --defer-db-indexes \
  --workdir ./itn_db \
  --host 0.0.0.0 \
  # License NFT.
  --match "0c6f22bfabcb055927ca3235eac387945b6017f15223d9365e6e4e43.*" \
  # Fact token policy.
  --match "a3931691f5c4e65d01c429e473d0dd24c51afdb6daf88e632a6c1e51.*"
