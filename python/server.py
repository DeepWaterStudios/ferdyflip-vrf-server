from concurrent.futures import ThreadPoolExecutor

from absl import flags, app

from fulfillment.service import Fulfiller
from utils.config import Config
from utils.discord import send_hook

FLAGS = flags.FLAGS
flags.DEFINE_string('dotenv', '', 'Alternate dotenv file to use instead of .env')


def main(_: list[str]):
    config = Config(dotenv_file=FLAGS.dotenv)

    send_hook(config.alert_hook_url,
              f'Starting fulfiller for {config.chain_id}'
              f' using {config.account.address}'
              f' watching {config.vrf_address}'
              f' delay {config.delay_blocks}')

    # Not strictly necessary but I had planned to run watchdog tasks. Leaving it in for later.
    executor = ThreadPoolExecutor()

    client = config.create_multisend_client()
    indexer = Fulfiller(client, config.alert_hook_url, config.fulfillment_hook_url,
                        config.delay_blocks, config.poll_delay)

    # For buffer, go back 2K blocks. This shouldn't take any time to catch up. The 1900 is because there's a buffer
    # for the -50 block lookback.
    last_block = max(client.get_latest_block_number() - 1_900, 1)
    # Start scanning.
    executor.submit(indexer.start_scan, last_block)

    # Wait forever.
    executor.shutdown()


if __name__ == '__main__':
    app.run(main)
