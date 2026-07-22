import csv
import json
import os
import urllib.request
from datetime import datetime, timedelta
from typing import Dict

from src.common.config import get_settings
from src.common.logger import get_logger

logger = get_logger(__name__)


def fetch_holidays(country_code: str, year: int) -> Dict[str, str]:
    """
    Fetch public holidays from Nager.Date API for a specific country and year.

    Returns:
        Dictionary in format:
        {
            "2026-01-01": "New Year's Day",
            "2026-07-04": "Independence Day"
        }

    Raises:
        RuntimeError: If the API request fails.
    """
    if not country_code or not isinstance(country_code, str):
        raise ValueError("country_code must be a non-empty string")

    if not isinstance(year, int):
        raise ValueError("year must be an integer")

    normalized_country_code = country_code.strip().upper()

    url = (
        f"https://date.nager.at/api/v4/Holidays/"
        f"{normalized_country_code}/{year}"
    )

    logger.info(
        f"Fetching public holidays. "
        f"country={normalized_country_code}, year={year}"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Bike-Sharing-Operation-Intelligence/1.0"
                )
            },
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = getattr(response, "status", None)

            if status_code is not None and status_code >= 400:
                raise RuntimeError(
                    f"Nager.Date API returned status={status_code}"
                )

            data = json.loads(response.read().decode("utf-8"))

        if not isinstance(data, list):
            raise ValueError(
                "Invalid Nager.Date response: expected a list of holidays"
            )

        holidays: Dict[str, str] = {}

        for item in data:
            if not isinstance(item, dict):
                continue

            date_str = item.get("date")
            name = item.get("localName") or item.get("name")

            if not date_str or not name:
                continue

            # If multiple holidays exist on the same date, keep all names.
            if date_str in holidays:
                holidays[date_str] += f"; {name}"
            else:
                holidays[date_str] = name

        logger.info(
            f"Fetched {len(holidays)} public holiday date(s) "
            f"for country={normalized_country_code}, year={year}"
        )

        return holidays

    except Exception as e:
        logger.error(
            f"Failed to fetch holidays from Nager.Date. "
            f"country={normalized_country_code}, year={year}, error={e}"
        )
        raise RuntimeError(
            f"Failed to fetch holidays for "
            f"{normalized_country_code} in {year}: {e}"
        ) from e


def generate_calendar_csv() -> None:
    """
    Generate local calendar CSV file.

    The generated CSV contains one row per date with:
    - date
    - day_of_week
    - is_weekend
    - is_holiday
    - holiday_name

    This CSV will be used later by the weather_calendar_sync_dag.
    """
    settings = get_settings()

    csv_path = settings.CALENDAR_CSV_PATH
    country_code = settings.CALENDAR_COUNTRY_CODE
    start_date_str = settings.CALENDAR_START_DATE
    end_date_str = settings.CALENDAR_END_DATE

    logger.info(
        f"Generating calendar CSV. "
        f"path={csv_path}, country={country_code}, "
        f"range=[{start_date_str} to {end_date_str}]"
    )

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError as e:
        logger.error(f"Invalid calendar date format in configuration: {e}")
        raise

    if start_date > end_date:
        raise ValueError(
            f"CALENDAR_START_DATE must be <= CALENDAR_END_DATE. "
            f"start={start_date}, end={end_date}"
        )

    holiday_dict: Dict[str, str] = {}

    for year in range(start_date.year, end_date.year + 1):
        year_holidays = fetch_holidays(country_code, year)
        holiday_dict.update(year_holidays)

    parent_dir = os.path.dirname(csv_path)

    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    rows = []
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.isoformat()
        day_of_week = current_date.strftime("%A")
        is_weekend = current_date.weekday() >= 5

        holiday_name = holiday_dict.get(date_str, "")
        is_holiday = bool(holiday_name)

        rows.append(
            {
                "date": date_str,
                "day_of_week": day_of_week,
                "is_weekend": str(is_weekend).lower(),
                "is_holiday": str(is_holiday).lower(),
                "holiday_name": holiday_name,
            }
        )

        current_date += timedelta(days=1)

    try:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "date",
                    "day_of_week",
                    "is_weekend",
                    "is_holiday",
                    "holiday_name",
                ],
            )

            writer.writeheader()
            writer.writerows(rows)

        logger.info(
            f"Successfully generated calendar CSV. "
            f"path={csv_path}, rows={len(rows)}, "
            f"holiday_dates={len(holiday_dict)}"
        )

    except Exception as e:
        logger.error(f"Failed to write calendar CSV. path={csv_path}, error={e}")
        raise


if __name__ == "__main__":
    generate_calendar_csv()