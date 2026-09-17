import ipaddress
from functools import lru_cache
from bisect import bisect_right
import pandas as pd
import maxminddb
from config import CITY_DB_PATH, ASN_DB_PATH, ALT_CITY_DB_PATH, ALT_ASN_DB_PATH, LOCATION_CSV_PATH, ASN_CSV_PATH

# Open MaxMind DB readers if available
city_reader = None
asn_reader = None

for path in [CITY_DB_PATH, ALT_CITY_DB_PATH]:
    if path.exists():
        try:
            city_reader = maxminddb.open_database(str(path))
            break
        except Exception:
            pass

for path in [ASN_DB_PATH, ALT_ASN_DB_PATH]:
    if path.exists():
        try:
            asn_reader = maxminddb.open_database(str(path))
            break
        except Exception:
            pass


@lru_cache(maxsize=1)
def load_location_ranges():
    if not LOCATION_CSV_PATH.exists():
        return [], []

    try:
        reference = pd.read_csv(LOCATION_CSV_PATH, encoding="utf-8-sig")
        reference.columns = [column.strip().lstrip("\ufeff").lower() for column in reference.columns]
        ranges = []
        for row in reference.to_dict("records"):
            try:
                start = int(ipaddress.ip_address(str(row["start"]).strip()))
                end = int(ipaddress.ip_address(str(row["end"]).strip()))
                if start <= end:
                    ranges.append((
                        start,
                        end,
                        str(row.get("state", "Unknown")).strip(),
                        str(row.get("city", "Unknown")).strip(),
                        float(row["lat"]),
                        float(row["long"]),
                    ))
            except (KeyError, TypeError, ValueError):
                continue
        ranges = sorted(ranges, key=lambda item: item[0])
        return [item[0] for item in ranges], ranges
    except Exception:
        return [], []


@lru_cache(maxsize=1)
def load_asn_ranges():
    if not ASN_CSV_PATH.exists():
        return [], []

    try:
        reference = pd.read_csv(
            ASN_CSV_PATH,
            header=None,
            names=["start", "end", "asn", "org"],
            encoding="utf-8",
            on_bad_lines="skip",
        )
        ranges = []
        for row in reference.to_dict("records"):
            try:
                start = int(ipaddress.ip_address(str(row["start"]).strip()))
                end = int(ipaddress.ip_address(str(row["end"]).strip()))
                if start <= end:
                    ranges.append((start, end, str(row["asn"]).strip(), str(row["org"]).strip()))
            except (TypeError, ValueError):
                continue
        ranges = sorted(ranges, key=lambda item: item[0])
        return [item[0] for item in ranges], ranges
    except Exception:
        return [], []


def find_range(value, indexed_ranges):
    if not indexed_ranges:
        return None
    starts, ranges = indexed_ranges
    if not ranges:
        return None
    index = bisect_right(starts, value) - 1
    if index >= 0 and value <= ranges[index][1]:
        return ranges[index]
    return None


def lookup_ip(ip: str) -> dict:
    result = {
        "state": "Unknown", "city": "Unknown", "asn": "N/A", "org": "N/A",
        "latitude": None, "longitude": None
    }
    if not ip or ip == "Unknown":
        return result

    try:
        address = ipaddress.ip_address(ip)
        if not address.is_global:
            return result

        if city_reader:
            data = city_reader.get(ip)
            if data:
                subdivisions = data.get("subdivisions", [])
                location = data.get("location", {})
                city = data.get("city", {}).get("names", {}).get("en")
                if subdivisions:
                    result["state"] = subdivisions[0].get("names", {}).get("en", "Unknown")
                if city:
                    result["city"] = city
                result["latitude"] = location.get("latitude")
                result["longitude"] = location.get("longitude")

        if asn_reader:
            data = asn_reader.get(ip)
            if data:
                result["asn"] = f"AS{data.get('autonomous_system_number', '')}"
                result["org"] = data.get("autonomous_system_organization", "N/A")

        # CSV range fallback if MaxMind is incomplete
        if result["state"] == "Unknown":
            location_match = find_range(int(address), load_location_ranges())
            if location_match:
                _, _, state, city, latitude, longitude = location_match
                result["state"] = state
                result["city"] = city
                if result["latitude"] is None:
                    result["latitude"] = latitude
                if result["longitude"] is None:
                    result["longitude"] = longitude

        if result["asn"] == "N/A":
            asn_match = find_range(int(address), load_asn_ranges())
            if asn_match:
                _, _, asn, org = asn_match
                result["asn"] = f"AS{asn}"
                result["org"] = org

    except Exception:
        pass
    return result
