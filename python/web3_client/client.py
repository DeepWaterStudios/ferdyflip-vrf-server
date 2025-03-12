import concurrent
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import TypedDict, Optional

import web3.logs
from eth_account.datastructures import SignedTransaction
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress, BlockNumber
from eth_typing.encoding import HexStr
from eth_utils import event_abi_to_log_topic
from hexbytes import HexBytes
from web3 import Web3
from web3.contract import Contract
from web3.contract.contract import ContractFunction, ContractEvent
from web3.types import Nonce, TxParams, TxReceipt, EventData

from web3_client.abi import VRF_ABI


class ChainClient(object):
    """Web3 client.

    These settings might need to be modified per chain? Fine for now.
    """

    def __init__(self, w3: Web3, account: LocalAccount, max_gas_price_in_gwei: float):
        self.w3 = w3
        self.account = account

        self.chain_id = self.w3.eth.chain_id
        self.max_gas_price_in_gwei = max_gas_price_in_gwei
        self.priority_fee_in_gwei = 0.001
        self.gas_limit = 1_500_000

    ####################
    # Build Tx
    ####################

    def build_base_tx(self) -> TxParams:
        """Build a basic transaction."""
        if self.chain_id == 5000:
            # Special casing for mantle, for now.
            tx: TxParams = {
                'chainId': self.chain_id,
                # 'type': 0x0,
                'gasPrice': Web3.to_wei(self.max_gas_price_in_gwei, 'gwei'),
                'gas': self.gas_limit,
                'nonce': self.next_nonce(),
            }
        else:
            tx: TxParams = {
                'chainId': self.chain_id,
                'type': 0x2,
                'maxFeePerGas': Web3.to_wei(self.max_gas_price_in_gwei, 'gwei'),
                'maxPriorityFeePerGas': Web3.to_wei(self.priority_fee_in_gwei, 'gwei'),
                'gas': self.gas_limit,
                'nonce': self.next_nonce(),
            }
        return tx

    def build_contract_tx(self, contract_function: ContractFunction) -> TxParams:
        """Build a transaction that involves a deployment interation."""
        base_tx = self.build_base_tx()
        return contract_function.build_transaction(base_tx)

    ####################
    # Sign & send Tx
    ####################

    def sign_tx(self, tx: TxParams) -> SignedTransaction:
        """Sign the given transaction."""
        return self.w3.eth.account.sign_transaction(tx, self.account.key)

    def send_signed_tx(self, signed_tx: SignedTransaction) -> HexStr:
        """Send a signed transaction and return the tx hash."""
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        return self.w3.to_hex(tx_hash)

    def sign_and_send_tx(self, tx: TxParams) -> HexStr:
        """Sign a transaction and send it.

        Just a convenience wrap around the sign_tx/send_signed_tx functions.
        """
        signed_tx = self.sign_tx(tx)
        return self.send_signed_tx(signed_tx)

    ####################
    # Utils
    ####################

    def get_latest_block_number(self) -> BlockNumber:
        """Get the latest block number from the server."""
        return self.w3.eth.get_block_number()

    def next_nonce(self) -> Nonce:
        """Requests the next nonce from the server."""
        return self.w3.eth.get_transaction_count(self.account.address)

    def get_receipt_by_hash(self, tx_hash: HexStr) -> TxReceipt:
        """Given a transaction hash, wait for the blockchain to confirm it and return the tx receipt."""
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

    def contract(self, address: ChecksumAddress, abi: str) -> Contract:
        """Generate a contract helper from the address and abi."""
        return self.w3.eth.contract(address=address, abi=abi, decode_tuples=True)


class RequestCommitment(TypedDict):
    """Struct required by the VRF contract.

    The inputs all come from the RandomWordsRequested event.
    """
    blockNum: int
    subId: int
    callbackGasLimit: int
    numWords: int
    sender: ChecksumAddress


class ChainVrfClient(ChainClient):
    """Web3 client with helpers for VRF.

    Also caches the nonce locally and increments it when a tx is sent. This allows for multiple outstanding
    fulfillments at the same time.

    Take care to sync the nonce from the chain when we're sure it's actually updated. The nonce will report the wrong
    value when tx are in flight.
    """

    def __init__(self, w3: Web3, account: LocalAccount, address: ChecksumAddress, max_gas_price_in_gwei: float):
        super().__init__(w3, account, max_gas_price_in_gwei)
        self.vrf_contract = self.contract(address, VRF_ABI)
        self.requested_event: ContractEvent = self.vrf_contract.events.RandomWordsRequested()
        self.fulfilled_event: ContractEvent = self.vrf_contract.events.RandomWordsFulfilled()
        self.requested_topic = Web3.to_hex(event_abi_to_log_topic(self.requested_event.abi))
        self.fulfilled_topic = Web3.to_hex(event_abi_to_log_topic(self.fulfilled_event.abi))

        self._nonce = Nonce(-1)
        self.refresh_nonce()

    def next_nonce(self) -> Nonce:
        """Override nonce fetching to use the local cache."""
        return self._nonce

    def refresh_nonce(self):
        """Requests the next nonce from the server and caches it."""
        self._nonce = self.w3.eth.get_transaction_count(self.account.address)

    def build_base_tx(self) -> TxParams:
        """Override the base TX creation to increment the nonce after it has been used."""
        tx = super().build_base_tx()
        self._nonce += 1
        return tx

    def get_vrf_logs(self, from_block: int, to_block: int) -> tuple[list[EventData], list[EventData]]:
        """Efficiently fetch the logs for the two events we're interested in and convert them into EventData."""
        logs = self.w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': self.vrf_contract.address,
            'topics': [[self.requested_topic, self.fulfilled_topic]],
        })
        requested_logs = [log for log in logs if log['topics'][0] == self.requested_topic]
        fulfilled_logs = [log for log in logs if log['topics'][0] == self.fulfilled_topic]
        requested_events = self.requested_event.process_receipt({'logs': requested_logs}, errors=web3.logs.STRICT)
        fulfilled_events = self.fulfilled_event.process_receipt({'logs': fulfilled_logs}, errors=web3.logs.STRICT)
        return list(requested_events), list(fulfilled_events)

    def fulfill_random_words(self, request_id: int, randomness: int, rc: RequestCommitment) -> Optional[HexStr]:
        """Fulfill a randomness request."""
        cf = self.vrf_contract.functions.fulfillRandomWords(request_id, randomness, rc)
        tx = self.build_contract_tx(cf)
        return self.sign_and_send_tx(tx)


class MultisendChainVrfClient(ChainVrfClient):
    """VRF client that sends transactions to multiple RPC endpoints simultaneously.

    Imported from joepegs mint bot race client, still WIP.
    This is most important for Avalanche, but maybe we can use it for Base as well.
    """

    def __init__(self, providers: list[Web3], account: LocalAccount, address: ChecksumAddress,
                 max_gas_price_in_gwei: int):
        super().__init__(providers[0], account, address, max_gas_price_in_gwei)
        self.pool = ThreadPoolExecutor(max_workers=10)
        self.providers = providers
        self.send_timeout_sec = .5

    def fulfill_random_words(self, request_id: int, randomness: int, rc: RequestCommitment) -> Optional[HexStr]:
        """Fulfill a randomness request."""
        cf = self.vrf_contract.functions.fulfillRandomWords(request_id, randomness, rc)
        tx = self.build_contract_tx(cf)
        return self.sign_and_multisend_tx(tx)

    def sign_and_multisend_tx(self, tx: TxParams) -> HexStr:
        """Sign a transaction and sends it simultaneously via multiple providers."""
        signed_tx = self.sign_tx(tx)
        tx_hash = Web3.to_hex(signed_tx.hash)

        tx_futures: list[Future[HexBytes]] = []
        start = time.time()

        for client in self.providers:
            tx_f = self.pool.submit(client.eth.send_raw_transaction, signed_tx.raw_transaction)
            tx_futures.append(tx_f)
            # Perhaps we should move nonce handling here? That's where it is in other code we use.

        # We only want to wait a limited amount of time for the TX to get sent.
        # This may cause some of the slower providers to fail. It's no big
        # deal, the earlier ones will have picked it up.
        done, timed_out = concurrent.futures.wait(tx_futures, timeout=self.send_timeout_sec)
        took = round(time.time() - start, 3)
        accepted = [x for x in done if x.exception() is None]
        print(f'Sent {len(tx_futures)} requests in {took};'
              f' {len(done)} done  {len(accepted)} accepted {len(timed_out)} timed out')

        if not accepted and done:
            # Something is fundamentally screwy; we should always have some TX accepted.
            # If none were accepted, surface the exception for debugging.
            raise list(done)[0].exception()

        return tx_hash
