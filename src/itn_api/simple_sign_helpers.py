"""Helpers for working with simple-sign to retrieve license data.
"""

import binascii
import copy
from dataclasses import dataclass
from typing import Final

import pycardano as pyc
from simple_sign.backend import KupoContext
from simple_sign.types import Alias


@dataclass
class LicenseHolder:
    staking_addr: str
    licenses: list[str]
    fact_held: int


FACT_POLICY: Final[str] = "a3931691f5c4e65d01c429e473d0dd24c51afdb6daf88e632a6c1e51"
MIN_FACT: Final[int] = 500000
ORCFAX_MINT: Final[str] = "addr1w98nyxrtep2x0y5m008zcp4lc5aplssydy3gsajm5s7494sdle4kd"
LICENSE_POLICY: Final[str] = "0c6f22bfabcb055927ca3235eac387945b6017f15223d9365e6e4e43"
NFT_SUFFIX_UNUSED: Final[str] = "000de140"
ITN_ALIAS_VALUE: Final[int] = 1246010
METADATA_TAG: Final[str] = "674"


def get_staked(kupo_url: str, kupo_port: int, min_stake=MIN_FACT):
    """Get $FACT staking values."""
    context = KupoContext(kupo_url, kupo_port)
    staking = context.retrieve_staked_holders(
        token_policy=FACT_POLICY,
    )
    for k, v in copy.deepcopy(staking).items():
        if v > min_stake:
            continue
        del staking[k]
    return staking


def get_licenses(kupo_url: str, kupo_port: int):
    """Get license holders."""
    context = KupoContext(kupo_url, kupo_port)
    md = context.retrieve_nft_holders(
        policy=LICENSE_POLICY,
        deny_list=[ORCFAX_MINT],
    )
    holders = {}
    for k, v in md.items():
        name = (
            k.replace(LICENSE_POLICY, "")
            .replace(".", "")
            .replace(NFT_SUFFIX_UNUSED, "")
        )
        name = binascii.unhexlify(name).decode()
        holders[name] = v
    return holders


def identify_aliases_callback(md: list[dict]) -> list[Alias]:
    """Return an alias from retrieved kupo metadata."""
    addresses = []
    for item in md:
        try:
            value = item["schema"]["674"]["map"][0]["v"]["list"]
        except KeyError:
            continue
        try:
            action = value[0]["string"]
            project = value[1]["string"]
            vkh = value[2]["string"]
        except IndexError:
            continue
        try:
            if (
                action.upper().strip() != "REGISTER"
                and project.upper().strip() != "ITN"
            ):
                continue
        except ValueError:
            continue
        try:
            network = pyc.Network.MAINNET
            verification_key_hash = pyc.VerificationKeyHash.from_primitive(vkh)
            address = pyc.Address(verification_key_hash, network=network)
            addresses.append(
                Alias(
                    alias=str(address),
                    address=item["address"],
                    staking=item["staking"],
                    tx=item["transaction"],
                )
            )
        except ValueError:
            continue
    return addresses


def get_itn_alias(kupo_url: str, kupo_port: str):
    """Get builder festival aliased addresses."""
    context = KupoContext(kupo_url, kupo_port)
    aliases = context.retrieve_metadata(
        value=ITN_ALIAS_VALUE,
        tag=METADATA_TAG,
        policy=LICENSE_POLICY,
        callback=identify_aliases_callback,
    )
    return aliases
