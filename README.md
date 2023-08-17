# FerdyFlip VRF (RNG)

## Why this exists

On Avalanche, we use Chainlink VRF to fulfill our games. Unfortunately Chainlink is not deployed on Base, and it will
not be in the near future.

So instead we created our own RNG.

## How it works

To minimize changes, we've just deployed our own VRFCoordinator contract (basically a copy of the Chainlink one with
some stuff stripped out) and we call it from this server.

It's extremely simple and stupid. The VRF coordinator requires a 'randomness' seed, which we provide using the standard
python 'secrets' library.

> The secrets module is used for generating cryptographically strong random numbers suitable for managing data such as
> passwords, account authentication, security tokens, and related secrets.

```python
randomness = secrets.randbelow(2 ** 256)
```

That's the whole thing. Note that this is not actually VRF. We may convert to generating VRF the same way Chainlink
does in the future, but VirtualQuery threatened to beat me if I did not complete this quickly.

## Setup

Need to define the following environment variables:

```
# The chain ID, e.g. 84531 for base testnet
CHAIN_ID=84531
# The obfuscated private key, see utils/keys.py for more details
OBFUSCATED_KEY=...
# The address of the deployed VRFCoordinator for the chain
VRF_ADDRESS=0x...
# Discord webhook URL where important alerts are sent
ALERT_HOOK_URL=https://discord.com/api/webhooks/...
# Discord webhook URL where fulfillment info events are sent
FULFILLMENT_HOOK_URL=https://discord.com/api/webhooks/...
```

## Deployment

We use the Dockerfile to build a container, push it to AWS ECR, and deploy two instances using AWS ECS.

One instance is deployed in the 'immediate' mode to minimize time to fulfillments, the other is deployed in a 'delay'
mode to ensure that if a fulfillment somehow gets dropped by the immediate fulfiller, the other one will pick it up.
