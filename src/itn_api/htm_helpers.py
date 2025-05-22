"""Helpers specifically for outputting HTML, i.e. for HTMX."""

import logging

import folium
import humanize

logger = logging.getLogger(__name__)


async def aliases_to_html(alias_report: dict) -> str:
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
    count = 0
    for alias in alias_report:
        if alias.alias != "":
            count += 1
        row = f"""
<tr>
    <td>{alias.staking}</td>
    <td nowrap>&nbsp;{humanize.intword(alias.staked)}&nbsp;</td>
    <td nowrap>&nbsp;{", ".join(alias.licenses)}&nbsp;</td>
    <td>{alias.alias}</td>
</tr>
        """.strip()

        rows = f"{rows}{row}\n"

    count_row = f"""
<tr>
    <td><b>Count</b></td>
    <td nowrap>&nbsp;{count}&nbsp;</td>
    <td nowrap></td>
    <td></td>
</tr>
    """
    return f"{head}\n{rows}\n{count_row}</table>\n"


async def participants_count_table(
    participants_count_total,
    participants_count_24hr,
    participant_count_24h_feed_average,
    participant_count_1h_feed_average,
    participant_count_1m_feed_average,
):
    """Return a table with active participant counts."""

    logging.info("formatting participants count table")

    if not participants_count_total:
        return "zero collectors online"

    head = """
<table>
    <tr>
        <th>Stake Key</th>
        <th>Count (Total)</th>
        <th>Count (24hr)</th>
        <th>Per feed (24hr) (max 1440)</th>
        <th>Per feed (1hr) (max 60)</th>
        <th>Per feed (1min) (max 1)</th>
    </tr>
    """.strip()

    rows = ""
    for stake_key, count in participants_count_total.items():
        count_24hr = participants_count_24hr.get(stake_key, 0)
        average_24hr = participant_count_24h_feed_average.get(stake_key, 0)
        average_1hr = participant_count_1h_feed_average.get(stake_key, 0)
        average_min = participant_count_1m_feed_average.get(stake_key, 0)
        row = f"""
<tr>
    <td>{stake_key}</td>
    <td nowrap>&nbsp;{humanize.intcomma(count)}&nbsp;</td>
    <td nowrap>&nbsp;{humanize.intcomma(count_24hr)}&nbsp;</td>
    <td nowrap>&nbsp;{humanize.intcomma(average_24hr)}&nbsp;</td>
    <td nowrap>&nbsp;{humanize.intcomma(average_1hr)}&nbsp;</td>
    <td nowrap>&nbsp;{humanize.intcomma(average_min)}&nbsp;</td>
</tr>
        """.strip()

        rows = f"{rows}{row}\n"

    return f"{head}\n{rows}</table>\n"


async def locations_table(locations):
    """Create a table for participant locations."""

    logging.info("formatting participants location table")

    if not locations or not isinstance(locations, dict):
        logger.error("locations table: locations is incorrect: %s", locations)
        return "no locations available"

    head = """
<table>
    <tr>
        <th>Stake</th>
        <th>Region</th>
        <th>Country</th>
    </tr>
    """.strip()

    seen = []
    rows = ""
    idx = 0
    if not locations:
        return "problem gathering collectors, please try again shortly"
    for addr, locale in locations.items():
        idx += 1
        region = locale["region"]
        country = locale["country"]
        row = f"""
<tr>
    <td>{addr}</td>
    <td>{region}</td>
    <td nowrap>&nbsp;{country}&nbsp;</td>
</tr>
        """.strip()
        seen.append((region, country))
        rows = f"{rows}{row}\n"
    country_count = f"""
<tr>
    <td><b>Count</b></td>
    <td nowrap>&nbsp;{idx}&nbsp;</td>
</tr>
        """.strip()
    return f"{head}\n{rows}\n{country_count}</table>\n"


async def locations_map(locations):
    """Create a map for participant locations."""

    logging.info("formatting participants map")

    if not locations or not isinstance(locations, list):
        logger.error("locations map: locations is incorrect: %s", locations)
        return "no locations available"

    collectors_map = folium.Map(
        location=[0.0, 0.0], zoom_start=1, min_zoom=1, zoom_control=False, attr=" "
    )

    seen = []

    collector_count = len(locations)

    collector_count_html = f"""
        <div style="position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
                    background-color: rgba(255, 255, 255, 0.8); padding: 5px 10px;
                    border-radius: 5px; font-size: 16px; font-weight: bold; z-index: 9999;">
            Collector Count: {collector_count}
        </div>
    """

    collectors_map.get_root().html.add_child(folium.Element(collector_count_html))

    if not locations:
        return "problem gathering collectors, please try again shortly"
    for locale in locations:
        region = locale["region"]
        country = locale["country"]
        latitude = locale["latitude"]
        longitude = locale["longitude"]

        if (region, country) in seen:
            continue

        folium.Marker(
            location=[latitude, longitude],
            popup=f"{region}, {country}",
            icon=folium.Icon(color="blue", prefix="fa", icon="computer"),
        ).add_to(collectors_map)

        seen.append((region, country))

    collectors_map_html = collectors_map._repr_html_()  # pylint: disable=W0212

    collectors_map_html = collectors_map_html.replace(
        '<div style="width:100%;">',
        '<div style="width:800px; height:600px; margin: 0 auto;">',
    )

    return collectors_map_html


async def price_comparisons_section(price_data: dict) -> str:
    """Output the ITN price comparison table so that we can start
    to understand deviation better.
    """

    feeds = []
    try:
        feeds = [item for item in price_data.keys()]
    except AttributeError as err:
        # TODO: remove this once we understand server anomalies.
        logger.error("feeds error: %s, '%s'", err, feeds)

    htm = ""

    threshold = 1

    for feed in feeds:
        htm = f"{htm}<div><h3>{feed}</h3>\n"
        summary = "<h4>summary</h4>\n"
        htm = f"{htm}{summary}\n"

        o1 = f"min values in last hour greater than {threshold}%: {price_data[feed]['breached_hourly_min']} | range diff (%): {price_data[feed]['min_min_hourly_diff']}"
        o2 = f"max values in last hour greater than {threshold}%: {price_data[feed]['breached_hourly_max']} | range diff (%): {price_data[feed]['max_max_hourly_diff']}"
        o3 = f"min values in last day greater than {threshold}%: {price_data[feed]['breached_daily_min']} | range diff (%): {price_data[feed]['min_min_daily_diff']}"
        o4 = f"max values in last day greater than {threshold}%: {price_data[feed]['breached_daily_max']} | range diff (%): {price_data[feed]['max_max_daily_diff']}"

        htm = f"{htm}\n<pre>{o1}\n{o2}\n{o3}\n{o4}</pre>\n</div>\n"

    for feed in feeds:
        htm = f"{htm}<div>\n"
        summary = f"<h4>detailed: {feed}</h4>\n"
        htm = f"{htm}{summary}\n"
        htm = f"{htm}<table><th>price (min hour)</th><th>key</th>\n"
        for item in price_data[feed]["min_price_hour"]:
            price = item[0]
            key = item[1]
            tr = f"<tr><td>{price:1.7f}</td><td>{key}</td></tr>"
            htm = f"{htm}{tr}\n"
        htm = f"{htm}</table>\n<br>\n"
        htm = f"{htm}<table><th>prices (max hour)</th><th>key</th>\n"
        for item in price_data[feed]["max_price_hour"]:
            price = item[0]
            key = item[1]
            tr = f"<tr><td>{price:1.7f}</td><td>{key}</td></tr>"
            htm = f"{htm}{tr}\n"
        htm = f"{htm}</table>\n<br>\n"
        """
        htm = f"{htm}<table><th>prices (min day)</th><th>key</th>\n"
        for item in price_data[feed]["min_price_day"]:
            price = item[0]
            key = item[1]
            tr = f"<tr><td>{price:1.7f}</td><td>{key}</td></tr>"
            htm = f"{htm}{tr}\n"
        htm = f"{htm}</table>\n<br>\n"
        htm = f"{htm}<table><th>prices (max day)</th><th>key</th>\n"
        for item in price_data[feed]["max_price_day"]:
            price = item[0]
            key = item[1]
            tr = f"<tr><td>{price:1.7f}</td><td>{key}</td></tr>"
            htm = f"{htm}{tr}\n"
        htm = f"{htm}</table>\n<br>\n"
        """

    return htm
