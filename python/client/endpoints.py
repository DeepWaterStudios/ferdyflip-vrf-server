from web3 import Web3
from web3.middleware import geth_poa_middleware

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
    provider = make_web3(node_uri)
    # Inject the POA middleware
    provider.middleware_onion.inject(geth_poa_middleware, layer=0)
    return provider


def make_web3_for_chain_id(chain_id: int) -> Web3:
    return make_complete_web3(CHAIN_ID_TO_RPC[chain_id])
