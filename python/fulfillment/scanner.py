import secrets
import time
import traceback
from typing import Optional

from web3.types import BlockIdentifier, EventData

from client.client import L2ChainVrfClient
from utils.discord import send_hook


class Fulfiller(object):
    def __init__(self, client: L2ChainVrfClient, alert_url: Optional[str]):
        self.client = client
        self.alert_url = alert_url

    def start_scan(self, run_from_block: int):
        print("Starting scan from", run_from_block)
        last_block = run_from_block
        current_block = self.client.get_latest_block_number()

        # catchup mode if more than 50 blocks behind
        if current_block - run_from_block > 50:
            print('executing catchup mode')
            self.catchup_mode(run_from_block, current_block)
            last_block = current_block

        first_pass = True
        while True:
            try:
                time.sleep(1)  # TODO: should be configurable
                current_block = self.client.get_latest_block_number()

                # No progress since last poll, do nothing
                if current_block == last_block:
                    continue

                fa = {'fromBlock': last_block + 1, 'toBlock': current_block}
                print(f"scanning from {fa}")
                requested = self.client.vrf_contract.events.RandomWordsRequested().create_filter(
                    fromBlock=last_block + 1, toBlock=current_block).get_all_entries()

                for pending in requested:
                    self.fulfill_event(pending, test_run=first_pass)

                # If we're here, the tx for the block range committed successfully.
                last_block = current_block
                first_pass = False

            except Exception as e:
                traceback.print_exc()
                send_hook(self.alert_url, e)
                time.sleep(2)

    def catchup_mode(self, from_block: BlockIdentifier, to_block: BlockIdentifier):
        current_start = from_block
        requested = []
        fulfilled = []
        while current_start < to_block:
            try:
                # Limit catchup to 10 QPS max
                time.sleep(.1)

                # Get at most 2K blocks
                current_end = min(to_block, current_start + 2000)
                fa = {'fromBlock': current_start + 1, 'toBlock': current_end}
                print(f"catchup from {fa}")

                # Fetch data for both sets of events
                local_r = self.client.vrf_contract.events.RandomWordsRequested().create_filter(
                    fromBlock=current_start + 1, toBlock=current_end).get_all_entries()
                local_f = self.client.vrf_contract.events.RandomWordsFulfilled().create_filter(
                    fromBlock=current_start + 1, toBlock=current_end).get_all_entries()

                # We got them both successfully so update our bulk storage
                requested += local_r
                fulfilled += local_f

                # Bump up the start window to the current end.
                current_start = current_end

            except Exception as e:
                traceback.print_exc()
                send_hook(self.alert_url, e)
                time.sleep(2)

        # Determine which requests have not been fulfilled, if any.
        fulfilled_ids = [x.args['requestId'] for x in fulfilled]
        pending_requested = [x for x in requested if x.args['requestId'] not in fulfilled_ids]

        for pending in pending_requested:
            self.fulfill_event(pending)

    def fulfill_event(self, event: EventData, test_run=False):
        args = event['args']
        request_id = args['requestId']
        randomness = secrets.randbelow(2 ** 256)
        rc = {
            'blockNum': event['blockNumber'],
            'subId': args['subId'],
            'callbackGasLimit': args['callbackGasLimit'],
            'numWords': args['numWords'],
            'sender': args['sender'],
        }
        print(f'fulfilling {request_id}')
        tx_hash = self.client.fulfill_random_words(request_id, randomness, rc)
        result = self.client.get_receipt_by_hash(tx_hash)
        send_hook(self.alert_url, f'fulfilled {request_id} with status {result["status"]} tx: {tx_hash}')
