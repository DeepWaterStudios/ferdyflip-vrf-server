from concurrent.futures import ThreadPoolExecutor

from absl import flags, app

from scanner.config import Config

# from utils.dump import dump
# from utils.environment import Config

FLAGS = flags.FLAGS
flags.DEFINE_bool('restart', False, 'Restart from first block if true')
flags.DEFINE_string('dotenv', '', 'Alternate dotenv file to use instead of .env')


def main(_: list[str]):
    config = Config(dotenv_file=FLAGS.dotenv)
    client = config.make_client()
    pool = config.make_db_conn()
    force_restart = FLAGS.restart
    chain_id = config.chain_id

    dump([f'{x.address} : {type(x)}-{x.topic_id}' for x in indexer_config])

    last_block = chain_id.start_block
    if not force_restart:
        with pool.connection() as conn:
            last_block = max(last_block, fetch_last_block(conn))

    # Just to get buffer, go back 10K blocks. This is only a few seconds of processing and is safe.
    last_block -= 10_000
    indexer = Indexer(pool, client, indexer_config, config.alert_hook_url)

    executor = ThreadPoolExecutor()
    print('starting indexer')
    executor.submit(indexer.start_scan, last_block)

    executor.shutdown()





if __name__ == '__main__':
    app.run(main)
