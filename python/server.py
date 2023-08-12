from concurrent.futures import ThreadPoolExecutor

from absl import flags, app

from fulfillment.scanner import Fulfiller
from utils.config import Config

FLAGS = flags.FLAGS
flags.DEFINE_string('dotenv', '', 'Alternate dotenv file to use instead of .env')


def main(_: list[str]):
    config = Config(dotenv_file=FLAGS.dotenv)
    client = config.create_client()

    # For buffer, go back 10K blocks. This is only a few seconds of processing and is safe.
    # Will run in catchup mode until it gets close to head.
    last_block = client.get_latest_block_number() - 10_000
    indexer = Fulfiller(client, config.alert_hook_url)

    executor = ThreadPoolExecutor()
    print('starting indexer')
    executor.submit(indexer.start_scan, last_block)

    # TODO:
    # 1) use async stuff
    # 2) figure out how to fulfill in parallel
    # 3) 'look back' mode for 2nd fulfiller
    # 4) deployment instructions

    executor.shutdown()


if __name__ == '__main__':
    app.run(main)
