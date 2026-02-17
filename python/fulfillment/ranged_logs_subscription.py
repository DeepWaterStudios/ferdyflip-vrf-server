"""RangedLogsSubscription — LogsSubscription with fromBlock/toBlock support.

web3.py's built-in LogsSubscription strips non-standard params like fromBlock
and toBlock. This subclass preserves them so MegaETH's pending miniblock
subscriptions work correctly.
"""

from typing import Any, Dict, List, Optional, Union

from eth_typing import Address, ChecksumAddress, HexStr
from web3.types import BlockIdentifier, FilterParams, LogReceipt
from web3.utils.subscriptions import EthSubscription, LogsSubscriptionHandler


class RangedLogsSubscription(EthSubscription[LogReceipt]):
    """Logs subscription that supports fromBlock/toBlock (e.g. 'pending')."""

    def __init__(
        self,
        address: Optional[
            Union[Address, ChecksumAddress, List[Address], List[ChecksumAddress]]
        ] = None,
        topics: Optional[List[HexStr]] = None,
        handler: LogsSubscriptionHandler = None,
        handler_context: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
        from_block: Optional[BlockIdentifier] = None,
        to_block: Optional[BlockIdentifier] = None,
    ) -> None:
        self.address = address
        self.topics = topics

        logs_filter: FilterParams = {}
        if address:
            logs_filter["address"] = address
        if topics:
            logs_filter["topics"] = topics
        if from_block:
            logs_filter["fromBlock"] = from_block
        if to_block:
            logs_filter["toBlock"] = to_block
        self.logs_filter = logs_filter

        super().__init__(
            subscription_params=("logs", logs_filter),
            handler=handler,
            handler_context=handler_context,
            label=label,
        )
