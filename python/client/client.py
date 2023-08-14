from typing import TypedDict, Optional, Iterable

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
from web3.types import Nonce, TxParams, TxReceipt, BlockData, EventData

from client.abi import VRF_ABI


class L2ChainClient(object):
    """Web3 client for an L2."""

    def __init__(self, w3: Web3, account: LocalAccount):
        self.w3 = w3
        self.account = account

        self.chain_id = self.w3.eth.chain_id
        self.gas_price_in_gwei = 0.001
        self.gas_limit = 1_000_000

    ####################
    # Build Tx
    ####################

    def build_base_tx(self) -> TxParams:
        """Build a basic transaction."""
        tx: TxParams = {
            'chainId': self.chain_id,
            'gas': self.gas_limit,
            'gasPrice': Web3.to_wei(self.gas_price_in_gwei, 'gwei'),
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
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
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

    def get_latest_block(self) -> BlockData:
        return self.w3.eth.get_block('latest')

    def get_latest_block_number(self) -> BlockNumber:
        return self.w3.eth.get_block_number()

    def next_nonce(self) -> Nonce:
        """Requests the next nonce from the server."""
        return self.w3.eth.get_transaction_count(self.account.address)

    def get_receipt_by_hash(self, tx_hash: HexStr) -> TxReceipt:
        """Given a transaction hash, wait for the blockchain to confirm it and return the tx receipt."""
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

    def get_balance_wei(self) -> int:
        """Get the native balance in wei."""
        return self.w3.eth.get_balance(self.account.address)

    def contract(self, address: ChecksumAddress, abi: str) -> Contract:
        """Generate a contract helper from the address and abi."""
        return self.w3.eth.contract(address=address, abi=abi, decode_tuples=True)


class RequestCommitment(TypedDict):
    blockNum: int
    subId: int
    callbackGasLimit: int
    numWords: int
    sender: ChecksumAddress


class L2ChainVrfClient(L2ChainClient):
    """Web3 client for an L2 with helpers for VRF."""

    def __init__(self, w3: Web3, account: LocalAccount, address: ChecksumAddress):
        super().__init__(w3, account)
        self.vrf_contract = self.contract(address, VRF_ABI)
        self.requested_event: ContractEvent = self.vrf_contract.events.RandomWordsRequested()
        self.fulfilled_event: ContractEvent = self.vrf_contract.events.RandomWordsFulfilled()
        self.requested_topic = HexBytes(event_abi_to_log_topic(self.requested_event.abi))
        self.fulfilled_topic = HexBytes(event_abi_to_log_topic(self.fulfilled_event.abi))

    def get_vrf_logs(self, from_block: int, to_block: int) -> tuple[Iterable[EventData], Iterable[EventData]]:
        logs = self.w3.eth.get_logs({
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': self.vrf_contract.address,
        })
        requested_logs = [log for log in logs if log['topics'][0] == self.requested_topic]
        fulfilled_logs = [log for log in logs if log['topics'][0] == self.fulfilled_topic]
        requested_events = self.requested_event.process_receipt({'logs': requested_logs}, errors=web3.logs.STRICT)
        fulfilled_events = self.fulfilled_event.process_receipt({'logs': fulfilled_logs}, errors=web3.logs.STRICT)
        return requested_events, fulfilled_events

    def fulfill_random_words(self, request_id: int, randomness: int, rc: RequestCommitment) -> Optional[HexStr]:
        cf = self.vrf_contract.functions.fulfillRandomWords(request_id, randomness, rc)
        tx = self.build_contract_tx(cf)
        return self.sign_and_send_tx(tx)
