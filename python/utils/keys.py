import random

_CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_SHUFFLED_CHARSET = 'WSRQLbOkn7iJCyoPMgYw04VhBaj8dcl2xez5E3mrqHpftuNGFADK9sUTv6ZX1I'
_TABLE = str.maketrans(_CHARSET, _SHUFFLED_CHARSET)


def shuffle_charset() -> str:
    """Shuffle the charset to produce the one-time pad.

    Should be run one time per project and stored forever.
    """
    char_list = list(_CHARSET)
    random.shuffle(char_list)
    return ''.join(char_list)


def obfuscate_string(key: str) -> str:
    """Given a string, apply a reversible obfuscation.

    This is not intended to be secure against an attacker that knows the protocol.
    It's just a simple way to ensure anyone that somehow gets the obfuscated string
    can't immediately determine that it's a primary key.
    """
    return key.translate(_TABLE)
