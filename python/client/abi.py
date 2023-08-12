import os


def load_abi_file(filename: str) -> str:
    """Read the ABI for a file name into memory."""
    dirname = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(dirname, 'abis', filename)
    with open(path, 'r') as f:
        return f.read()


# Load ABIs statically loaded into memory at startup.
VRF_ABI = load_abi_file('ferdy_vrf_coordinator.abi')
