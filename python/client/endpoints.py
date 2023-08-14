from typing import cast

from web3 import Web3
from web3.middleware import geth_poa_middleware, construct_simple_cache_middleware
from web3.types import RPCEndpoint

# Eliminate unnecessary chainId queries.
# See: https://ethereum.stackexchange.com/questions/131768/how-to-reduce-the-number-of-eth-chainid-calls-when-using-web3-python
SIMPLE_CACHE_RPC_CHAIN_ID = cast(
    set[RPCEndpoint],
    (
        "web3_clientVersion",
        "net_version",
        "eth_chainId",
    ),
)

cache_chain_id_middleware = construct_simple_cache_middleware(
    rpc_whitelist=SIMPLE_CACHE_RPC_CHAIN_ID
)

CHAIN_ID_TO_RPC = {
    8453: 'https://mainnet.base.org',
    84531: 'https://goerli.base.org',
}


def make_web3(node_uri: str) -> Web3:
    if node_uri.startswith('http'):
        return Web3(Web3.HTTPProvider(node_uri))
    elif node_uri.startswith('ws'):
        return Web3(Web3.WebsocketProvider(node_uri))
    else:
        raise Exception(f'node_uri not valid: {node_uri}')


def make_complete_web3(node_uri: str) -> Web3:
    w3 = make_web3(node_uri)
    # Inject the POA middleware
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    # Always cache chain_id
    w3.middleware_onion.add(cache_chain_id_middleware, name="Cache chain_id")
    return w3


def make_web3_for_chain_id(chain_id: int) -> Web3:
    return make_complete_web3(CHAIN_ID_TO_RPC[chain_id])
