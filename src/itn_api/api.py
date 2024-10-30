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
from fastapi.responses import RedirectResponse

try:
    import reports
except ImportError:
    try:
        from src.itn_api import reports
    except ImportError:
        from itn_api import reports


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
    version="1.0.0",
    contact={
        "Github": "https://github.com/orcfax/ITN-Phase-1/",
    },
    openapi_tags=tags_metadata,
    lifespan=lifespan,
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
    return RedirectResponse(url="/docs")


@app.get("/get_active_participants", tags=[TAG_STATISTICS])
async def get_active_participants():
    """Return participants in the ITN database."""
    participants = app.state.connection.execute(
        "select distinct address from data_points;"
    )
    data = [participant[0] for participant in participants]
    return data


@app.get("/get_participants_counts_total", tags=[TAG_STATISTICS])
async def get_participants_counts_total():
    """Return participants total counts."""
    participants_count_total = app.state.connection.execute(
        "select count(*) as count, address from data_points group by address order by count desc;"
    )
    return participants_count_total


@app.get("/get_participants_counts_day", tags=[TAG_STATISTICS])
async def get_participants_counts_day(
    date_start: str = "1970-01-01", date_end: str = "1970-01-03"
):
    """Return participants in ITN."""

    report = reports.get_participants_counts_date_range(app, date_start, date_end)
    return report


@app.get("/date_range", tags=[TAG_INFO])
async def get_date_range():
    """Return the date range of all statistics."""
    return await reports.get_date_ranges(app)


@app.get("/itn_aliases_and_staking", tags=[TAG_INFO])
async def get_itn_aliases_and_staking(min_stake: int = 500000):
    """Return the date range of all statistics."""
    return reports.get_all_license_holders(app, min_stake)


def main():
    """Primary entry point for this script."""

    parser = argparse.ArgumentParser(
        prog="itn-api",
        description="ITN API",
        epilog="for more information visit https://ffdev.info/",
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
        access_log=False,
        log_level="info",
        reload=args.reload,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
