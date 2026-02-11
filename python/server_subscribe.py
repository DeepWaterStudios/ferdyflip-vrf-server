import asyncio

from absl import flags, app

from fulfillment.service_subscribe import SubscribeFulfiller
from utils.config import Config
from utils.discord import send_hook

FLAGS = flags.FLAGS
flags.DEFINE_string('dotenv', '', 'Alternate dotenv file to use instead of .env')


def main(_: list[str]):
    config = Config(dotenv_file=FLAGS.dotenv)

    if not config.wss_endpoint:
        raise ValueError('WSS_ENDPOINT is required for the subscribe server')

    send_hook(config.alert_hook_url,
              f'Starting subscribe fulfiller for {config.chain_id}'
              f' using {config.account.address}'
              f' watching {config.vrf_address}'
              f' delay {config.delay_blocks}')

    client = config.create_multisend_client()
    fulfiller = SubscribeFulfiller(client, config.wss_endpoint,
                                   config.alert_hook_url, config.fulfillment_hook_url,
                                   config.delay_blocks)

    asyncio.run(fulfiller.start())


if __name__ == '__main__':
    app.run(main)
