from __future__ import annotations

import os
from typing import Optional

from dotenv import dotenv_values
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3

from utils.keys import deobfuscate_string
from web3_client.client import L2ChainVrfClient
from web3_client.endpoints import CHAIN_ID_TO_RPC, make_web3_for_chain_id


class Config(object):
    """Load config from dotfiles with an env override."""

    def __init__(self, dotenv_file: Optional[str] = None):
        self.config = {
            **dotenv_values(dotenv_file or '.env'),
            **os.environ,  # override loaded values with environment variables
        }

        self.chain_id = int(self.config.get('CHAIN_ID', 0))
        if self.chain_id not in CHAIN_ID_TO_RPC:
            raise ValueError(f'Unexpected chain id value: {self.chain_id}')

        self.delay_blocks = int(self.config.get('DELAY_BLOCKS', 0))

        self.alert_hook_url = self.config.get('ALERT_HOOK_URL')
        self.fulfillment_hook_url = self.config.get('FULFILLMENT_HOOK_URL')

        self.obfuscated_key = self.config.get('OBFUSCATED_KEY')
        if not self.obfuscated_key:
            raise ValueError('Expected OBFUSCATED_KEY to be set')

        try:
            print(f'Loaded {self.account.address}')
        except Exception as ex:
            raise ValueError('Expected OBFUSCATED_KEY to resolve to an account') from ex

        try:
            self.vrf_address = Web3.to_checksum_address(self.config.get('VRF_ADDRESS'))
        except Exception as ex:
            raise ValueError('Expected VRF_ADDRESS to resolve to an address') from ex

    @property
    def private_key(self) -> str:
        return deobfuscate_string(self.obfuscated_key)

    @property
    def account(self) -> LocalAccount:
        return Account.from_key(self.private_key)

    def create_client(self) -> L2ChainVrfClient:
        return L2ChainVrfClient(make_web3_for_chain_id(self.chain_id), self.account, self.vrf_address)
