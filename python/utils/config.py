from __future__ import annotations

import os
from typing import Optional

from dotenv import dotenv_values

from client.endpoints import CHAIN_ID_TO_RPC


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

        self.alert_hook_url = self.config.get('ALERT_HOOK_URL')
