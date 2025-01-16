"""ITN Validator API.

Output stats from the Orcfax Validator Database in order to report on
the ITN output.

    `uvicorn src.itn_api.api:app --reload`

The database for this app is configured by the DATABASE_PATH environment
variable.
"""

# pylint: disable=W0621

import argparse
import importlib
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

import apsw
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the database connection for the life of the app.s"""
    db_path = Path(os.environ["DATABASE_PATH"])
    logger.info("validator database: %s", db_path)
    app.state.connection = apsw.Connection(
        str(db_path), flags=apsw.SQLITE_OPEN_READONLY
    )
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
    try:
        participants = app.state.connection.execute(
            "select distinct address from data_points;"
        )
    except apsw.SQLError as err:
        return {"error": f"{err}"}
    data = [participant[0] for participant in participants]
    return data


@app.get("/get_participants_counts_total", tags=[TAG_STATISTICS])
async def get_participants_counts_total():
    """Return participants total counts."""
    try:
        participants_count_total = app.state.connection.execute(
            "select count(*) as count, address from data_points group by address order by count desc;"
        )
    except apsw.SQLError as err:
        return {"error": f"{err}"}
    return participants_count_total


@app.get("/get_participants_counts_day", tags=[TAG_STATISTICS])
async def get_participants_counts_day(
    date_start: str = "1970-01-01", date_end: str = "1970-01-03"
):
    """Return participants in ITN."""

    report = reports.get_participants_counts_date_range(app, date_start, date_end)
    return report


@app.get(
    "/get_participants_counts_csv", tags=[TAG_STATISTICS], response_class=HTMLResponse
)
async def get_participants_counts_day_csv(
    date_start: str = "1970-01-01", date_end: str = "1970-01-03"
) -> str:
    """Return participants in ITN."""
    report = reports.get_participants_counts_date_range(app, date_start, date_end)
    csv_report = reports.generate_participant_count_csv(report)
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


# HTMX #################################################################
# HTMX #################################################################
# HTMX #################################################################


@app.get("/participants", tags=[TAG_HTMX], response_class=HTMLResponse)
async def get_itn_participants() -> str:
    """Return ITN aliases and licenses."""
    all_holders = reports.get_all_license_holders(app, 0, None)
    htmx = htm_helpers.aliases_to_html(all_holders)
    return htmx.strip()


@app.get("/online_collectors", tags=[TAG_HTMX], response_class=HTMLResponse)
async def get_online_collectors() -> str:
    """Return ITN aliases and collector counts."""
    try:
        participants_count = app.state.connection.execute(
            """SELECT address, COUNT(*) AS total_count,
            SUM(CASE WHEN datetime(date_time) >= datetime('now', '-24 hours')
            THEN 1 ELSE 0 END) AS count_24hr
            FROM data_points
            GROUP BY address ORDER BY total_count DESC;
            """
        )
    except apsw.SQLError:
        return "zero collectors online"

    try:
        feed_count = app.state.connection.execute(
            """SELECT distinct feed_id
            from data_points
            where datetime(date_time) >= datetime('now', '-48 hours');
            """
        )
    except apsw.SQLError:
        return "zero collectors online"

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

    htmx = htm_helpers.participants_count_table(
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
    return htm_helpers.locations_table(locations)


@app.get("/locations_map", tags=[TAG_HTMX], response_class=HTMLResponse)
async def get_locations_map_hx():
    """Return countries participating in the ITN."""
    locations = await reports.get_locations(app)
    return htm_helpers.locations_map(locations)


@app.get("/count_active_participants", tags=[TAG_HTMX], response_class=HTMLResponse)
async def count_active_participants():
    """Count active participants."""
    try:
        participants = app.state.connection.execute(
            "select count(distinct address) as count from data_points;"
        )
    except apsw.SQLError as err:
        return {"error": f"{err}"}
    data = list(participants)
    return f"{data[0][0]}"


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
