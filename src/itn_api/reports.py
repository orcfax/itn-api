"""Reports we're generating"""

# pylint: disable=R0917,R0913,R0914

import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import List, Tuple

import apsw
import humanize
from fastapi import FastAPI

try:
    import helpers
    import simple_sign_helpers
except ImportError:
    try:
        from src.itn_api import helpers, simple_sign_helpers
    except ImportError:
        from itn_api import helpers, simple_sign_helpers


logger = logging.getLogger(__name__)


@dataclass
class LicenseHolder:
    staking: str
    staked: int
    licenses: List[str]
    alias: str = ""


def _search_aliases(aliases: list[simple_sign_helpers.Alias], addr: str):
    """Get the alias from the given list of aliases."""
    alias_found = ""
    for alias in aliases:
        if alias.staking != addr:
            continue
        alias_found = alias.alias
        break
    return alias_found


def _get_all_alias_addr_data(
    kupo_url: str, kupo_port: str, min_stake: int, license_no: str
):
    """Retrieve all alias and address data for all staking addresses.

    E.g. this is useful for understanding network state.
    """
    aliases = simple_sign_helpers.get_itn_alias(kupo_url, kupo_port)
    licenses = simple_sign_helpers.get_licenses(kupo_url, kupo_port)
    staked = simple_sign_helpers.get_staked(kupo_url, kupo_port, min_stake)
    license_holders = list(licenses.values())
    fact_holders = list(staked.keys())
    holders = list(set(license_holders).intersection(fact_holders))
    all_license_data = _collate_simple(holders, staked, licenses, aliases)
    if license_no:
        needle = f"Validator License {license_no}"
        return [lic for lic in all_license_data if needle in lic.licenses]
    return all_license_data


def get_all_license_holders(app: FastAPI, min_stake: int, license_no: str) -> dict:
    """Get all license holders."""
    alias_addr_data = _get_all_alias_addr_data(
        app.state.kupo_url, app.state.kupo_port, min_stake, license_no
    )
    return alias_addr_data


def get_all_license_holders_csv(app: FastAPI, min_stake: int, sort: str) -> str:
    """Return all license holder info as a CSV."""
    alias_addr_data = _get_all_alias_addr_data(
        app.state.kupo_url, app.state.kupo_port, min_stake, None
    )
    if sort.lower().strip() == "stake":
        alias_addr_data = sorted(
            alias_addr_data,
            key=lambda alias_addr_data: alias_addr_data.staked,
            reverse=True,
        )
    csv = "idx,staking,license,value\n"
    for idx, data in enumerate(alias_addr_data, 1):
        stake = humanize.intcomma(data.staked).replace(",", ".")
        csv = f"{csv}{idx:0>4}, {data.staking}, {' '.join(data.licenses)}, {stake}\n"
    return csv


def _collate_simple(
    holders: list, staked: dict, licenses: dict, aliases: list
) -> list[LicenseHolder]:
    """Collate all basic license holder info."""
    holders.sort()
    all_holders = []
    alias = ""
    for holder in holders:
        stake = staked[holder]
        held = []
        for license_name, address in licenses.items():
            if address == holder:
                held.append(license_name)
        if aliases:
            alias = _search_aliases(aliases, holder)
        all_holders.append(
            LicenseHolder(
                staking=holder,
                staked=int(stake / 1000000),
                licenses=held,
                alias=alias,
            )
        )
    all_holders = sorted(
        all_holders, key=lambda all_holders: all_holders.licenses, reverse=False
    )
    return all_holders


def _get_basic_addr_data(kupo_url: str, kupo_port: int):
    """Get all staking and license data for all staking addresses."""
    licenses = simple_sign_helpers.get_licenses(kupo_url, kupo_port)
    staked = simple_sign_helpers.get_staked(kupo_url, kupo_port)
    license_holders = list(licenses.values())
    fact_holders = list(staked.keys())
    holders = list(set(license_holders).intersection(fact_holders))
    all_license_data = _collate_simple(holders, staked, licenses, None)
    return all_license_data


def _get_unique_feeds(data: list) -> Tuple[list, list]:
    """Get unique feeds per address."""
    addresses = []
    feeds = []
    for item in data:
        addr = item[0]
        feed = item[2]
        feeds.append(feed)
        if addr in addresses:
            continue
        addresses.append(addr)
    feeds = list(set(feeds))
    return feeds, addresses


def _get_addr_minute_feed_dicts(data: list, addresses: list):
    """For all addresses, identify unique minutes collecting per feed
    and all unique feeds collected.
    """
    # Sort behaves like an index and improves the performance of the
    # next section of code organizing the data.
    addresses.sort()
    addr_minute_values = {}
    addr_feed_values = {}
    for addr in addresses:
        for item in data:
            if item[0] != addr:
                continue
            minutes = item[1].rsplit(":", 1)[0].strip()
            feed = item[2].strip()
            addr_minute_values = helpers.update_dict(
                addr_minute_values, addr, f"{feed}|{minutes}"
            )
            addr_feed_values = helpers.update_dict(addr_feed_values, addr, feed)
    return addr_minute_values, addr_feed_values


def _get_license_and_stake(
    address_data: list[LicenseHolder], addr: str
) -> Tuple[str, str]:
    """Get license and stake for a given address."""
    license_name = None
    staking = None
    for address in address_data:
        if address.staking != addr:
            continue
        license_name = ", ".join(address.licenses)
        staking = address.staked
    return license_name, staking


def _process_json_report(
    address_data: list[LicenseHolder],
    date_start: str,
    date_end: str,
    addr_minute_values: dict,
    addr_feed_values: dict,
    feeds: list,
) -> dict:
    """Create the JSON report from the given data."""
    # Combine counts into a report.
    minutes_in_range = helpers.get_minutes(date_start, date_end)
    days_in_range = minutes_in_range / helpers.MINUTES_DAY
    counts = {}
    for addr, value in addr_minute_values.items():
        total_mins = len(set(value))
        average_mins = total_mins / len(set(feeds))
        license_name, stake = _get_license_and_stake(address_data, addr)
        counts[addr] = {
            "license": license_name,
            "stake": stake,
            "total_data_points": total_mins,
            "average_mins_collecting_per_feed": int(average_mins),
            "total_mins_in_date_range": minutes_in_range,
            "number_of_feeds_collected": len(set(addr_feed_values[addr])),
            "feeds_count": [
                f"{key}: {value}"
                for key, value in Counter(addr_feed_values[addr]).items()
            ],
        }
    report = {}
    report["start"] = date_start
    report["end"] = date_end
    report["expected_number_of_feeds"] = len(feeds)
    report["max_possible_data_points"] = minutes_in_range * len(feeds)
    report["data"] = counts
    report["expected_feeds"] = feeds
    report["total_days_in_date_range"] = int(days_in_range)
    return report


@helpers.timeit
def get_participants_counts_date_range(
    app: FastAPI, date_start: str, date_end: str
) -> dict:
    """Return participants report by date range."""
    data = _get_participant_data_by_date_range(app, date_start, date_end)
    feeds, addresses = _get_unique_feeds(data)
    logger.info("no feeds: '%s'", len(feeds))
    logger.info("no addresses: '%s'", len(feeds))
    addr_minute_values, addr_feed_values = _get_addr_minute_feed_dicts(data, addresses)
    addr_minute_values = helpers.dedupe_dicts(addr_minute_values)
    address_data = _get_basic_addr_data(app.state.kupo_url, app.state.kupo_port)
    report = _process_json_report(
        address_data, date_start, date_end, addr_minute_values, addr_feed_values, feeds
    )
    return report


def _get_participant_data_by_date_range(
    app: FastAPI, date_start: str, date_end: str
) -> list:
    """Query the database and get the results."""
    participants = app.state.connection.execute(
        f"""
            select address, date_time, feed_id
            from data_points
            where date_time > date('{date_start}')
            and date_time < date('{date_end}')
            order by address;
        """
    )
    return list(participants)


def generate_participant_count_csv(report: dict) -> str:
    """Convert JSON data into a CSV for ease of use."""

    max_possible = report.get("max_possible_data_points")
    start = report.get("start")
    end = report.get("end")
    max_feeds = report.get("expected_number_of_feeds", 1)
    data = report.get("data", {})
    total_days_in_range = report.get("total_days_in_date_range", 0)
    feed_cols = [""] * (max_feeds * 2)
    rows = []
    for stake_addr, value in data.items():
        participant = stake_addr
        license_no = value.get("license", "").replace("Validator License", "").strip()
        stake = humanize.intcomma(int(value.get("stake", 0))).replace(",", ".")
        total_data_points = value.get("total_data_points", 0)
        average_per_feed = value.get("average_mins_collecting_per_feed", 0)
        total_collected = value.get("number_of_feeds_collected", 0)
        participant_feeds = [""] * max_feeds
        for idx, count in enumerate(value.get("feeds_count", [])):
            participant_feeds[idx] = ",".join([c.strip() for c in count.split(":")])
        row = (
            f'{participant}, "{license_no}", {stake}, {total_days_in_range}, '
            f'"{humanize.intcomma(max_possible)}",'
            f'{start}, {end}, "{humanize.intcomma(total_collected)}",'
            f'"{humanize.intcomma(total_data_points)}", '
            f' "{humanize.intcomma(average_per_feed)}", '
            f"{','.join(participant_feeds)}"
        )
        rows.append(row.strip())
    csv_header = (
        f"participant, license, stake, days_in_range, max_possible, start, end, "
        f"total_collected, total_data_points, avg_per_feed, {','.join(feed_cols)}"
    )
    csv = f"{csv_header}\n"
    for row in rows:
        csv = f"{csv}{row}\n"
    return csv


async def get_date_ranges(app: FastAPI):
    """Return min and max dates from the database."""
    min_max_dates = app.state.connection.execute(
        "select min(date_time), max(date_time) from data_points;"
    )
    dates = list(min_max_dates)[0]
    return {
        "earliest_date": dates[0],
        "latest_date": dates[1],
    }


async def get_locations(app: FastAPI) -> list:
    """Return locations from the database.

    Select one of each kind example:

      * https://stackoverflow.com/a/571487

    """
    try:
        unique_raw_data = app.state.connection.execute(
            """select node_id, raw_data, min(address), date_time
            from data_points
            where datetime(date_time) >= datetime('now', '-48 hours')
            group by address;
            """
        )
    except apsw.SQLError:
        return "zero collectors online"

    res = list(unique_raw_data)
    key_loc = {}
    for item in res:
        node = item[0]
        address = item[2]
        if address in key_loc:
            continue
        message = json.loads(item[1])
        try:
            loc = message["message"]["identity"]["location"]
            country = {
                "geo": loc.get("loc"),
                "region": loc.get("region"),
                "country": loc.get("country"),
            }
            key_loc[address] = country
        except KeyError as err:
            logger.error("node: '%s' not reporting location (%s)", node, err)
    return key_loc
