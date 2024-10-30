"""ITN API.

API for querying the Orcfax Validator Database and returning the results
in a sensible way, e.g. for rewarding license operators.
"""

from src.itn_api import api


def main():
    """Primary entry point for this script."""
    api.main()


if __name__ == "__main__":
    main()
