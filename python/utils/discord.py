from typing import Optional

from discord_webhook import DiscordWebhook


def send_hook(hook_url: Optional[str], msg: any):
    """Send a discord webhook, never throws an exception.

    Always logs the message to the console, will only send the hook if hook_url is provided.
    """
    try:
        print('sending hook:', msg)
        if hook_url:
            DiscordWebhook(url=hook_url, content=str(msg),
                           rate_limit_retry=True, timeout=5).execute()
    except Exception as ex:
        print('failed to send hook:', ex)
