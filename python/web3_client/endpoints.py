from typing import Optional

from web3 import Web3
from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware

# Every supported chain needs a mapping from chain id to rpc endpoint.
CHAIN_ID_TO_RPC = {
    # Base Mainnet
    8453: 'https://mainnet.base.org',
    # Base Testnet
    84531: 'https://goerli.base.org',
    # Avax Mainnet
    43114: 'https://api.avax.network/ext/bc/C/rpc',
    # Avax testnet
    43113: 'https://api.avax-test.network/ext/bc/C/rpc',
    # Mantle
    5000: 'https://rpc.mantle.xyz',
    # MEVM devnet
    336: 'https://mevm.devnet.m1.movementlabs.xyz/v1',
    # BTC L1
    132008: 'https://rpc.bitcoinl1.net/main/evm/132008',
    # Monad
    10143: 'https://testnet-rpc.monad.xyz',
    # MegaETH
    6342: 'https://carrot.megaeth.com/rpc',
}

CHAIN_ID_TO_RPC_LIST = {
    # Avax Mainnet
    43114: [
        'https://api.avax.network/ext/bc/C/rpc',
        'https://rpc.ankr.com/avalanche',
        'https://avalanche.blockpi.network/v1/rpc/public',
        'https://avalanche-c-chain.publicnode.com',
        'https://ava-mainnet.public.blastapi.io/ext/bc/C/rpc',
        'https://1rpc.io/avax/c',
    ],
    # Avax testnet
    43113: [
        'https://api.avax-test.network/ext/bc/C/rpc',
        'https://rpc.ankr.com/avalanche_fuji',
        'https://avalanche-fuji.blockpi.network/v1/rpc/public',
    ],
    132008: [
        'https://rpc.bitcoinl1.net/main/evm/132008',
    ],
    10143: [
        'https://testnet-rpc.monad.xyz',
    ],
    6342: [
        'https://carrot.megaeth.com/rpc',
    ],
}

# Every supported chain needs a mapping from chain id to max gas in gwei.
CHAIN_ID_TO_MAX_GAS = {
    # Base Mainnet
    8453: 2,
    # Base Testnet
    84531: 2,
    # Avax Mainnet
    43114: 100,
    # Avax testnet
    43113: 40,
    # BTC L1
    132008: .002,
    # Monad
    10143: 60,
    # MegaETH
    6342: .003,
}


def make_web3(node_uri: str) -> Web3:
    """Creates a web3 from a node uri, accounting for websocket vs http."""
    if node_uri.startswith('http'):
        return Web3(Web3.HTTPProvider(node_uri))
    elif node_uri.startswith('ws'):
        return Web3(Web3.WebsocketProvider(node_uri))
    else:
        raise Exception(f'node_uri not valid: {node_uri}')


def make_complete_web3(node_uri: str) -> Web3:
    """Given a node uri, creates a web3 properly configured."""
    w3 = make_web3(node_uri)
    # Inject the POA middleware
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def make_web3_for_chain_id(chain_id: int, rpc_endpoint_override: Optional[str] = None) -> Web3:
    """Given a chain id, creates a web3 properly configured."""
    return make_complete_web3(rpc_endpoint_override or CHAIN_ID_TO_RPC[chain_id])


def make_web3_list_for_chain_id(chain_id: int, rpc_endpoint_override: Optional[str] = None) -> list[Web3]:
    """Given a chain id, creates a list of web3 properly configured.

    If the override is specified, makes sure that it's the first one in the list.
    """
    options = list(CHAIN_ID_TO_RPC_LIST[chain_id])
    if rpc_endpoint_override:
        if rpc_endpoint_override in options:
            options.remove(rpc_endpoint_override)
        options.insert(0, rpc_endpoint_override)
    return [make_complete_web3(rpc) for rpc in options]
