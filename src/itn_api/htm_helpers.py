"""Helpers specifically for outputting HTML, i.e. for HTMX."""

import logging

import humanize

logger = logging.getLogger(__name__)


def aliases_to_html(alias_report: dict) -> str:
    """Take the alias report and convert it to HTML.

    e.g.

        LicenseHolder(
            staking='stake1uxta2uanum3zphefxkeu5nr5umykkr5rqz0exujddalhadgtmzxas',
            staked=500000,
            licenses=['Validator License #099'],
            alias=''
        )

    """

    logging.info("formatting alias table")

    if not alias_report:
        return "no alias data available"

    head = """
<table>
    <tr>
        <th>Stake Key</th>
        <th>Staked</th>
        <th>Licenses</th>
        <th>Alias</th>
    </tr>

    """.strip()

    rows = ""
    for alias in alias_report:
        row = f"""
<tr>
    <td>{alias.staking}</td>
    <td nowrap>&nbsp;{humanize.intword(alias.staked)}&nbsp;</td>
    <td nowrap>&nbsp;{", ".join(alias.licenses)}&nbsp;</td>
    <td>{alias.alias}</td>
</tr>
        """.strip()

        rows = f"{rows}{row}\n"

    return f"{head}\n{rows}</table>\n"


def participants_count_table(participants_count_total):
    """Return a table with active participant counts."""

    logging.info("formatting participants table")

    if not participants_count_total:
        return "zero collectors online"

    head = """
<table>
    <tr>
        <th>Stake Key</th>
        <th>Count</th>
    </tr>
    """.strip()

    rows = ""
    for stake_key, count in participants_count_total.items():
        row = f"""
<tr>
    <td>{stake_key}</td>
    <td nowrap>&nbsp;{humanize.intcomma(count)}&nbsp;</td>
</tr>
        """.strip()

        rows = f"{rows}{row}\n"

    return f"{head}\n{rows}</table>\n"


def locations_table(locations):
    """Create a table for participant locations."""

    logging.info("formatting participants table")

    if not locations:
        return "no locations available"

    head = """
<table>
    <tr>
        <th>Region</th>
        <th>Country</th>
    </tr>
    """.strip()

    seen = []
    rows = ""
    for locale in locations:
        region = locale["region"]
        country = locale["country"]
        if (region, country) in seen:
            continue
        row = f"""
<tr>
    <td>{region}</td>
    <td nowrap>&nbsp;{country}&nbsp;</td>
</tr>
        """.strip()
        seen.append((region, country))
        rows = f"{rows}{row}\n"

    return f"{head}\n{rows}</table>\n"
