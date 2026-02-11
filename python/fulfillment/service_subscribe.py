import asyncio
import secrets
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import web3.logs
from web3 import AsyncWeb3
from web3.providers import WebSocketProvider
from web3.types import EventData

from utils.discord import send_hook
from web3_client.client import MultisendChainVrfClient


class SubscribeFulfiller(object):
    """Subscribe to the VRF contract for randomness requested events and fulfill them.

    Uses WebSocket subscription for near-instant event detection instead of polling.
    Falls back to a backfill poll on startup and reconnect to catch missed events.
    """

    def __init__(self, client: MultisendChainVrfClient, wss_endpoint: str,
                 alert_url: Optional[str], fulfillment_url: Optional[str],
                 delay_blocks: int):
        self.client = client
        self.wss_endpoint = wss_endpoint
        self.alert_url = alert_url
        self.fulfillment_url = fulfillment_url
        self.delay_blocks = delay_blocks

        self.executor = ThreadPoolExecutor(max_workers=5)

        self.last_fulfill_action = 0
        self.outstanding_fulfillments = 0

        self.fulfilled_ids: set[int] = set()

        # Grab event metadata from the sync client for log decoding and topic filtering.
        self.vrf_address = self.client.vrf_contract.address
        self.requested_event = self.client.requested_event
        self.fulfilled_event = self.client.fulfilled_event
        self.requested_topic = self.client.requested_topic
        self.fulfilled_topic = self.client.fulfilled_topic

    async def start(self):
        """Main entry point. Connects via WebSocket and subscribes, reconnecting on failure."""
        while True:
            try:
                await self._run_subscription()
            except Exception as e:
                traceback.print_exc()
                send_hook(self.alert_url, f'WebSocket error, reconnecting: {e}')
            print("[subscribe] Reconnecting in 2s...")
            await asyncio.sleep(2)

    async def _run_subscription(self):
        """Connect, backfill missed events, then listen for new ones via subscription."""
        print(f"[subscribe] Connecting to {self.wss_endpoint[:60]}...")
        async with AsyncWeb3(WebSocketProvider(self.wss_endpoint)) as ws_w3:
            print("[subscribe] Connected")

            # Backfill: poll recent blocks via HTTP to catch anything missed.
            await self._backfill()

            # Subscribe to both requested and fulfilled events from the VRF contract.
            sub_id = await ws_w3.eth.subscribe("logs", {
                "address": self.vrf_address,
                "topics": [[self.requested_topic, self.fulfilled_topic]],
            })
            print(f"[subscribe] Subscribed: {sub_id}")

            async for msg in ws_w3.socket.process_subscriptions():
                log = msg["result"]
                topic0 = log["topics"][0]

                if topic0 == self.requested_topic:
                    events = self.requested_event.process_receipt(
                        {"logs": [log]}, errors=web3.logs.STRICT)
                    for event in events:
                        self._handle_requested_event(event)

                elif topic0 == self.fulfilled_topic:
                    events = self.fulfilled_event.process_receipt(
                        {"logs": [log]}, errors=web3.logs.STRICT)
                    for event in events:
                        request_id = event['args']['requestId']
                        self.fulfilled_ids.add(request_id)
                        print(f"[subscribe] Saw fulfillment for request {request_id}")

    async def _backfill(self):
        """Poll recent blocks via the HTTP client to catch events missed while disconnected."""
        try:
            current_block = self.client.get_latest_block_number()
            backfill_from = max(current_block - 200, 1)
            print(f"[backfill] Scanning {backfill_from} to {current_block}")

            requested, fulfilled = self.client.get_vrf_logs(backfill_from, current_block)

            fulfilled_ids = [x['args']['requestId'] for x in fulfilled]
            pending = [x for x in requested if x['args']['requestId'] not in fulfilled_ids]
            pending = [x for x in pending if x['args']['requestId'] not in self.fulfilled_ids]

            if self.delay_blocks:
                delay_block = current_block - self.delay_blocks
                pending = [x for x in pending if x['blockNumber'] <= delay_block]

            print(f"[backfill] {len(requested)} requested / {len(fulfilled)} fulfilled"
                  f" / {len(pending)} pending")

            for event in pending:
                self._handle_requested_event(event)

        except Exception as e:
            traceback.print_exc()
            print(f"[backfill] Error: {e}")

    def _handle_requested_event(self, event: EventData):
        """Process a RandomWordsRequested event."""
        request_id = event['args']['requestId']

        if request_id in self.fulfilled_ids:
            return

        self.fulfilled_ids.add(request_id)
        block_number = event['blockNumber']
        print(f"[subscribe] RandomWordsRequested at block {block_number}, id {request_id}")
        self._submit_fulfill_event(event)

    def _submit_fulfill_event(self, event: EventData):
        """Submit a fulfillment task to the thread pool."""
        if not self.outstanding_fulfillments and time.time() - self.last_fulfill_action > 4:
            self.client.refresh_nonce()

        if self.delay_blocks:
            send_hook(self.alert_url, 'Unexpectedly fulfilling from a server with delay_blocks set')

        self.last_fulfill_action = time.time()
        self.outstanding_fulfillments += 1
        self.executor.submit(self._fulfill_event, event)

    def _fulfill_event(self, event: EventData):
        """Given a RandomWordsRequested event, submit a fulfillment tx."""
        args = event['args']
        request_id = args['requestId']
        try:
            randomness = secrets.randbelow(2 ** 256)
            block_number = event['blockNumber']
            rc = {
                'blockNum': block_number,
                'subId': args['subId'],
                'callbackGasLimit': args['callbackGasLimit'],
                'numWords': args['numWords'],
                'sender': args['sender'],
            }
            tx_hash = self.client.fulfill_random_words(request_id, randomness, rc)
            result = self.client.get_receipt_by_hash(tx_hash)
            status = 'SUCCESS' if result['status'] else 'FAILURE'
            close_block_number = result['blockNumber']
            send_hook(self.fulfillment_url,
                      f'{status} - {close_block_number - block_number} blocks - tx {tx_hash}')
        except Exception as ex:
            traceback.print_exc()
            send_hook(self.alert_url, f'Failed to fulfill {request_id}: {ex}')
        finally:
            self.last_fulfill_action = time.time()
            self.outstanding_fulfillments -= 1
