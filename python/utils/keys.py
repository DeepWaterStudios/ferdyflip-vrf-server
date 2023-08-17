import random
import secrets

from eth_account import Account
from eth_account.signers.local import LocalAccount

_CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_SHUFFLED_CHARSET = 'WSRQLbOkn7iJCyoPMgYw04VhBaj8dcl2xez5E3mrqHpftuNGFADK9sUTv6ZX1I'
_OBFUSCATE_TABLE = str.maketrans(_CHARSET, _SHUFFLED_CHARSET)
_DEOBFUSCATE_TABLE = str.maketrans(_SHUFFLED_CHARSET, _CHARSET)


def shuffle_charset() -> str:
    """Shuffle the charset to produce the one-time pad.

    Should be run one time per project and stored forever.
    """
    char_list = list(_CHARSET)
    random.shuffle(char_list)
    return ''.join(char_list)


def new_account() -> LocalAccount:
    """Helper to create a new account for testing purposes."""
    return Account.from_key("0x" + secrets.token_hex(32))


def obfuscate_string(key: str) -> str:
    """Given a string, apply a reversible obfuscation.

    This is not intended to be secure against an attacker that knows the protocol.
    It's just a simple way to ensure anyone that somehow gets the obfuscated string
    can't immediately determine that it's a primary key.
    """
    return key.translate(_OBFUSCATE_TABLE)


def deobfuscate_string(key: str) -> str:
    """Given a string, apply a reversible obfuscation.

    This is not intended to be secure against an attacker that knows the protocol.
    It's just a simple way to ensure anyone that somehow gets the obfuscated string
    can't immediately determine that it's a primary key.
    """
    return key.translate(_DEOBFUSCATE_TABLE)
