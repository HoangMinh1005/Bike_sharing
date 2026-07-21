import csv
import os
from datetime import datetime, timedelta
import urllib.request
import json
from src.common.config import get_settings
from src.common.logger import get_logger

logger = get_logger(__name__)


def fetch_holidays(country_code: str, year: int) -> dict:
    """
    Fetch public holidays from Nager.Date API for a specific country and year.
    Returns a dictionary of {date_string: holiday_name}.
    """
    url = f"https://date.nager.at/api/v4/Holidays/{country_code}/{year}"
    logger.info(f"Fetching public holidays from: {url}")
    
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Bike-Sharing Operation Intelligence Agent)"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            holidays = {}
            for item in data:
                date_str = item.get("date")
                name = item.get("localName") or item.get("name")
                if date_str and name:
                    holidays[date_str] = name
            return holidays
    except Exception as e:
        logger.error(f"Failed to fetch holidays for {country_code} in {year}: {e}")
        # Return empty dict so we still generate the calendar without holidays rather than crashing
        return {}


def generate_calendar_csv():
    """
    Generate the local calendar CSV file by calling Nager.Date API and
    populating daily fields like day_of_week, is_weekend, and is_holiday.
    """
    settings = get_settings()
    csv_path = settings.CALENDAR_CSV_PATH
    country_code = settings.CALENDAR_COUNTRY_CODE
    start_date_str = settings.CALENDAR_START_DATE
    end_date_str = settings.CALENDAR_END_DATE

    logger.info(
        f"Generating calendar CSV: path={csv_path}, country={country_code}, "
        f"range=[{start_date_str} to {end_date_str}]"
    )

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError as e:
        logger.error(f"Invalid date format in configuration: {e}")
        raise

    # Fetch holidays for all years in the range
    start_year = start_date.year
    end_year = end_date.year
    
    holiday_dict = {}
    for year in range(start_year, end_year + 1):
        year_holidays = fetch_holidays(country_code, year)
        holiday_dict.update(year_holidays)

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    rows = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_of_week = current_date.strftime("%A")
        is_weekend = current_date.weekday() >= 5  # Saturday (5) and Sunday (6)
        
        holiday_name = holiday_dict.get(date_str, "")
        is_holiday = date_str in holiday_dict

        rows.append({
            "date": date_str,
            "day_of_week": day_of_week,
            "is_weekend": str(is_weekend).lower(),
            "is_holiday": str(is_holiday).lower(),
            "holiday_name": holiday_name
        })
        current_date += timedelta(days=1)

    # Write to CSV
    try:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, 
                fieldnames=["date", "day_of_week", "is_weekend", "is_holiday", "holiday_name"]
            )
            writer.writeheader()
            writer.writerows(rows)
            
        logger.info(f"Successfully generated calendar CSV with {len(rows)} rows at: {csv_path}")

    except Exception as e:
        logger.error(f"Failed to write calendar CSV: {e}")
        raise


if __name__ == "__main__":
    generate_calendar_csv()
