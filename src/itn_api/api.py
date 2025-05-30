"""ITN Validator API.

Output stats from the Orcfax Validator Database in order to report on
the ITN output.

    `uvicorn src.itn_api.api:app --reload`

The database for this app is configured by the DATABASE_PATH environment
variable.
"""

# pylint: disable=W0621

import argparse
import decimal
import importlib
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Final

import mariadb
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

try:
    import htm_helpers
    import reports
except ImportError:
    try:
        from src.itn_api import htm_helpers, reports
    except ImportError:
        from itn_api import htm_helpers, reports


# Set up logging.
logging.basicConfig(
    format="%(asctime)-15s %(levelname)s :: %(filename)s:%(lineno)s:%(funcName)s() :: %(message)s",  # noqa: E501
    datefmt="%Y-%m-%d %H:%M:%S",
    level="INFO",
    handlers=[
        logging.StreamHandler(),
    ],
)

# Format logs using UTC time.
logging.Formatter.converter = time.gmtime


logger = logging.getLogger(__name__)


# API description.
API_DESCRIPTION: Final[str] = "Orcfax ITN API"

# OpenAPI tags delineating the documentation.
TAG_STATISTICS: Final[str] = "statistics"
TAG_INFO: Final[str] = "information"
TAG_HTMX: Final[str] = "htmx"

# Metadata for each of the tags in the OpenAPI specification. To order
# their display on the page, order the tags in this block.
tags_metadata = [
    {
        "name": TAG_STATISTICS,
        "description": "ITN statistics endpoints",
    },
    {
        "name": TAG_INFO,
        "description": "Endpoints to help with other information retrieval",
    },
    {
        "name": TAG_HTMX,
        "description": "Endpoints designed to be used with HTML elements",
    },
]


def _get_database_connection() -> mariadb.Connection:
    """Get a MriaDB database connection."""
    connection = mariadb.connect(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        host=os.environ.get("DB_URL", "0.0.0.0"),
        port=int(os.environ.get("DB_PORT", 3306)),
        database=os.environ["DB_DATABASE"],
        autocommit=True,
    )
    return connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the database connection for the life of the app.s"""
    app.state.connection = _get_database_connection()
    app.state.kupo_url = os.environ["KUPO_URL"]
    app.state.kupo_port = os.environ["KUPO_PORT"]
    yield


app = FastAPI(
    title="api.itn.orcfax.io",
    description=API_DESCRIPTION,
    version="2024-11-19.0001",
    contact={
        "Github": "https://github.com/orcfax/ITN-Phase-1/",
    },
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    root_path="/api",
)

origins = [
    "http://127.0.0.1:24001",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Content-type"],
)


#### API Entry Points ####


@app.get("/", include_in_schema=False)
def redirect_root_to_docs():
    """Redirect a user calling the API root '/' to the API
    documentation.
    """
    return RedirectResponse(url="/api/docs")


@app.get("/get_active_participants", tags=[TAG_STATISTICS])
async def get_active_participants():
    """Return participants in the ITN database."""
    cursor = app.state.connection.cursor()
    try:
        cursor.execute("select distinct address from data_points;")
    except mariadb.Error as err:
        return {"error": f"{err}"}
    data = [participant[0] for participant in cursor]
    cursor.close()
    return data


@app.get("/get_participants_counts_total", tags=[TAG_STATISTICS])
async def get_participants_counts_total():
    """Return participants total counts."""
    cursor = app.state.connection.cursor()
    try:
        cursor.execute(
            "select count(*) as count, address from data_points group by address order by count desc;"
        )
    except mariadb.Error as err:
        return {"error": f"{err}"}
    res = list(cursor)
    cursor.close()
    return res


@app.get("/get_participants_counts_day", tags=[TAG_STATISTICS])
async def get_participants_counts_day(
    date_start: str = "1970-01-01", date_end: str = "1970-01-03"
):
    """Return participants in ITN."""
    report = await reports.get_participants_counts_date_range(app, date_start, date_end)
    return report


@app.get(
    "/get_participants_counts_csv", tags=[TAG_STATISTICS], response_class=HTMLResponse
)
async def get_participants_counts_day_csv(
    date_start: str = "1970-01-01", date_end: str = "1970-01-03"
) -> str:
    """Return participants in ITN."""
    logger.info("generating participant csv: get db data")
    report = await reports.get_participants_counts_date_range(app, date_start, date_end)
    logger.info("data retrieved for participant csv: creating count csv")
    csv_report = await reports.generate_participant_count_csv(report)
    return csv_report


@app.get("/date_range", tags=[TAG_INFO])
async def get_date_range():
    """Return the date range of all statistics."""
    return await reports.get_date_ranges(app)


@app.get("/itn_aliases_and_staking", tags=[TAG_INFO])
async def get_itn_aliases_and_staking(min_stake: int = 500000, license_no: str = None):
    """Return ITN aliases and stake values.

    Optionally: enter a license number, e.g. `#001` to see the details
    of a specific license.
    """
    return reports.get_all_license_holders(app, min_stake, license_no)


@app.get("/itn_aliases_and_staking_csv", tags=[TAG_INFO], response_class=HTMLResponse)
async def get_itn_aliases_and_staking_csv(
    min_stake: int = 500000, sort: str = "stake"
) -> str:
    """Return ITN aliases and stake values."""
    return reports.get_all_license_holders_csv(app, min_stake, sort)


@app.get("/geo", tags=[TAG_STATISTICS])
async def get_locations():
    """Return countries participating in the ITN."""
    return await reports.get_locations(app)


@app.get("/validator_price_stats", tags=[TAG_STATISTICS])
async def validator_price_stats() -> dict:
    """Count active participants."""
    cursor = app.state.connection.cursor()

    try:
        cursor.execute(
            """SELECT distinct feed_id
            from data_points
            where date_time > (select date_sub(now(), interval 1 day ))
            """
        )
    except mariadb.Error as err:
        logger.error("problem retrieving feeds in last day: %s", err)
        return "zero collectors online"
    feeds = list(cursor)
    try:
        cursor.execute(
            """select address, feed_id, min(source_price), max(source_price)
            from data_points
            where date_time > (select date_sub(now(), interval 1 hour ))
            group by address, feed_id;
            """
        )

    except mariadb.Error as err:
        return {"error": f"{err}"}
    hour_data = list(cursor)
    try:
        cursor.execute(
            """select address, feed_id, min(source_price), max(source_price)
            from data_points
            where date_time > (select date_sub(now(), interval 1 day ))
            group by address, feed_id;
            """
        )
    except mariadb.Error as err:
        return {"error": f"{err}"}
    day_data = list(cursor)

    out = await reports._analyze_price_stats(feeds, hour_data, day_data)

    cursor.close()
    return out


# HTMX #################################################################
# HTMX #################################################################
# HTMX #################################################################


@app.get("/participants", tags=[TAG_HTMX], response_class=HTMLResponse)
async def get_itn_participants() -> str:
    """Return ITN aliases and licenses."""
    all_holders = reports.get_all_license_holders(app, 0, None)
    htmx = await htm_helpers.aliases_to_html(all_holders)
    return htmx.strip()


@app.get("/online_collectors", tags=[TAG_HTMX], response_class=HTMLResponse)
async def get_online_collectors() -> str:
    """Return ITN aliases and collector counts."""
    cursor = app.state.connection.cursor()
    try:
        cursor.execute(
            """SELECT address, COUNT(*) AS total_count,
            SUM(CASE WHEN date_time >= (SELECT DATE_SUB(NOW(), INTERVAL 1 DAY))
            THEN 1 ELSE 0 END) AS count_24hr
            FROM data_points
            GROUP BY address ORDER BY total_count DESC;
            """
        )
    except mariadb.Error as err:
        logger.error("problem retrieving online collectors in last day: %s", err)
        return "zero collectors online"

    participants_count = list(cursor)

    try:
        cursor.execute(
            """SELECT distinct feed_id
            from data_points
            where date_time >= (SELECT DATE_SUB(NOW(), INTERVAL 1 DAY));
            """
        )
    except mariadb.Error as err:
        logger.error("problem retrieving feeds from last day: %s", err)
        return "zero collectors online"

    feed_count = list(cursor)

    no_feeds = len(list(feed_count))

    # FIXME: These can all be combined better, e.g. into a dataclass or
    # somesuch. This is purely for expediency to have something up and
    # running.
    participants_count_total = {}
    participants_count_24hr = {}
    participant_count_24h_feed_average = {}
    participant_count_1h_feed_average = {}
    participant_count_1m_feed_average = {}

    for row in participants_count:
        address, total_count, count_24hr = row
        participants_count_total[address] = total_count
        participants_count_24hr[address] = count_24hr
        try:
            participant_count_24h_feed_average[address] = int(count_24hr / no_feeds) + 1
            participant_count_1h_feed_average[address] = (
                int(count_24hr / no_feeds / 24) + 1
            )
            participant_count_1m_feed_average[address] = round(
                count_24hr / no_feeds / 24 / 60, 4
            )
        except ZeroDivisionError:
            participant_count_24h_feed_average[address] = 0
            participant_count_1h_feed_average[address] = 0
            participant_count_1m_feed_average = 0
        except decimal.InvalidOperation:
            participant_count_24h_feed_average[address] = 0
            participant_count_1h_feed_average[address] = 0
            participant_count_1m_feed_average[address] = 0

    htmx = await htm_helpers.participants_count_table(
        participants_count_total,
        participants_count_24hr,
        participant_count_24h_feed_average,
        participant_count_1h_feed_average,
        participant_count_1m_feed_average,
    )
    return htmx.strip()


@app.get("/locations", tags=[TAG_HTMX], response_class=HTMLResponse)
async def get_locations_hx():
    """Return countries participating in the ITN."""
    locations = await reports.get_locations_stake_key(app)
    return await htm_helpers.locations_table(locations)


@app.get("/locations_map", tags=[TAG_HTMX], response_class=HTMLResponse)
async def get_locations_map_hx():
    """Return countries participating in the ITN."""
    locations = await reports.get_locations(app)
    return await htm_helpers.locations_map(locations)


@app.get("/count_active_participants", tags=[TAG_HTMX], response_class=HTMLResponse)
async def count_active_participants():
    """Count active participants."""
    cursor = app.state.connection.cursor()
    try:
        cursor.execute("select count(distinct address) as count from data_points;")
    except mariadb.Error as err:
        return {"error": f"{err}"}
    data = list(cursor)
    cursor.close()
    return f"{data[0][0]}"


@app.get("/validator_price_stats_hx", tags=[TAG_HTMX], response_class=HTMLResponse)
async def htmx_validator_price_stats() -> str:
    price_data = await validator_price_stats()
    return await htm_helpers.price_comparisons_section(price_data)


def main():
    """Primary entry point for this script."""

    parser = argparse.ArgumentParser(
        prog="itn-api",
        description="ITN API",
        epilog="for more information visit https://docs.orcfax.io/itn-overview",
    )

    parser.add_argument(
        "--port",
        help="provide a port on which to run the app",
        required=False,
        default=24001,
    )

    parser.add_argument(
        "--reload",
        help="enable reload in development mode",
        required=False,
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--workers",
        help="enable more workers",
        required=False,
        default=1,
        type=int,
    )

    args = parser.parse_args()

    logger.info(
        "attempting API startup, try setting `--port` arg if there are any issues"
    )

    import_str = "src.itn_api.api"
    try:
        importlib.import_module(import_str)
        import_str = f"{import_str}:app"
    except ModuleNotFoundError:
        import_str = "itn_api.api:app"
        logger.info("importing from %s", import_str)

    logging.info("ensure that environment is configured (e.g. SERVER_AUTH='badf00d')")

    uvicorn.run(
        import_str,
        host="0.0.0.0",
        port=int(args.port),
        access_log=True,
        log_level="debug",
        reload=args.reload,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
