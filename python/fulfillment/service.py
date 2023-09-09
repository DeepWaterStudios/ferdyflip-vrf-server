import secrets
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from web3.types import EventData

from utils.discord import send_hook
from web3_client.client import L2ChainVrfClient


class Fulfiller(object):
    """Scan the VRF contract for randomness requested events, and fulfill them.

    Will operate in 'catch up' mode at first if the start block is too far in the past.
    """

    def __init__(self, client: L2ChainVrfClient, alert_url: Optional[str], fulfillment_url: Optional[str],
                 delay_blocks: int):
        self.client = client
        self.alert_url = alert_url
        self.fulfillment_url = fulfillment_url
        self.delay_blocks = delay_blocks

        # Limit outstanding fulfillment tx to 5, which should be plenty.
        self.executor = ThreadPoolExecutor(max_workers=5)

        # These two are used to determine if we should try and sync the nonce from the chain.
        self.last_fulfill_action = 0
        self.outstanding_fulfillments = 0

        # Since we scan a range of blocks, we need to track items we've already fulfilled.
        self.fulfilled_ids = set()

    def start_scan(self, run_from_block: int):
        print("Starting scan from", run_from_block)
        last_block = run_from_block

        while True:
            try:
                # This might need to change for some chains (arb?). But it's fine for Base.
                time.sleep(.5)
                current_block = self.client.get_latest_block_number()

                # No progress since last poll, do nothing.
                # Or, alternatively, the Base RPC is legitimately being retarded and decided go back 1k blocks.
                if current_block <= last_block:
                    time.sleep(.5)
                    continue

                # Base testnet seemed kind of flaky in terms of supplying events accurately, so I shifted to fetching
                # the last 50 blocks and using a local cache of fulfilled IDs to prevent duplicate fulfills.
                scan_block = last_block - 50

                # Account for more weirdness. Can only scan for 2k blocks, but the start block might have been messed
                # up when it was fetched from Base.
                scan_end_block = min(scan_block + 1900, current_block)

                print(f"scanning from {scan_block} to {scan_end_block}")
                if scan_end_block != current_block:
                    print(f'Originally used {current_block} as end block')
                requested, fulfilled = self.client.get_vrf_logs(scan_block, scan_end_block)

                # If we saw fulfillments in the block, strip out matching requests for fulfillment.
                fulfilled_ids = [x['args']['requestId'] for x in fulfilled]
                pending_requested = [x for x in requested if x['args']['requestId'] not in fulfilled_ids]

                # If we already fulfilled it locally, strip it out. We need this because the block window is large and
                # we will see the same events repeatedly.
                pending_requested = [x for x in pending_requested if x['args']['requestId'] not in self.fulfilled_ids]

                # This server could be running in 'delay' mode. If it is, we want to exclude events that are newer
                # than the start of the lookback window. The primary fulfiller will pick those up. This is just to add
                # some extra reliability in fulfillment.
                delay_block = scan_end_block - self.delay_blocks
                pending_requested = [x for x in pending_requested if x['blockNumber'] <= delay_block]

                print(f'fetched events: {len(requested)} / {len(fulfilled)} / {len(pending_requested)}')
                for pending in pending_requested:
                    self.fulfilled_ids.add(pending['args']['requestId'])
                    self.submit_fulfill_event(pending)

                # The TX haven't finished submitting yet, but they're out for processing, so keep going.
                last_block = scan_end_block

            except Exception as e:
                traceback.print_exc()
                send_hook(self.alert_url, e)
                time.sleep(2)

    def submit_fulfill_event(self, event: EventData):
        """Submits a task to fulfill a randomness requested event to the executor.

        The client will track the current nonce, so it's safe to have multiple TX in flight, and necessary if we want
        good throughput. Don't want to wait for a TX to be completed before we can send another fulfill, or it will
        prevent us from fulfilling more than 1 per block.
        """
        # It's not clear exactly when we would want to refresh the nonce, but when we're not actively fulfilling
        # anything, and we've been idle for a while seems like a good candidate.
        if not self.outstanding_fulfillments and time.time() - self.last_fulfill_action > 4:
            self.client.refresh_nonce()

        # We never really want the delay fulfiller to fulfill anything, so warn if that happens. The primary is borked.
        if self.delay_blocks:
            send_hook(self.alert_url, f'Unexpectedly fulfilling from a server with delay_blocks set')

        self.last_fulfill_action = time.time()
        self.outstanding_fulfillments += 1
        self.executor.submit(self.fulfill_event, event)

    def fulfill_event(self, event: EventData):
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
            send_hook(self.fulfillment_url, f'{status} - {close_block_number - block_number} blocks - tx {tx_hash}')
        except Exception as ex:
            traceback.print_exc()
            send_hook(self.alert_url, f'Failed to fulfill {request_id}: {ex}')
        finally:
            # We want the nonce refresh to be trigger-able after the last fulfill has completed.
            self.last_fulfill_action = time.time()
            self.outstanding_fulfillments -= 1
