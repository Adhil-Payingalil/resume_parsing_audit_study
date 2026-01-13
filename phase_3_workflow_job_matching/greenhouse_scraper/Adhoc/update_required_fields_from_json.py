import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Resume_study")
MONGODB_COLLECTION = "Job_postings_greenhouse"


def get_latest_results_file(data_dir: Path) -> Path:
    candidates = sorted(
        data_dir.glob("required_fields_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No matching required_fields_*.json files found.")
    return candidates[0]


def load_results(filepath: Path) -> List[Dict[str, Any]]:
    with open(filepath, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Unexpected JSON structure: expected a list of results.")
    return data


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Unable to parse timestamp %s; using current UTC time.", value)
    return datetime.utcnow()


def update_documents(results: List[Dict[str, Any]]):
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI not found in environment variables.")

    try:
        client = MongoClient(MONGODB_URI)
        client.admin.command("ping")
    except ConnectionFailure as exc:
        raise RuntimeError(f"Failed to connect to MongoDB: {exc}") from exc

    db = client[MONGODB_DATABASE]
    collection = db[MONGODB_COLLECTION]

    updated = 0
    skipped = 0

    for entry in results:
        job_id = entry.get("job_id")
        labels = entry.get("input_field_labels")
        linkedin_required = entry.get("linkedin_required")
        checked_at = parse_timestamp(entry.get("checked_at"))

        if not job_id or labels is None or linkedin_required is None:
            skipped += 1
            logger.warning("Skipping incomplete entry: %s", entry)
            continue

        update_data = {
            "input_field_labels": labels,
            "linkedin_required": bool(linkedin_required),
            "required_fields_checked_at": checked_at,
        }

        result = collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_data},
        )

        if result.matched_count:
            updated += result.modified_count
        else:
            skipped += 1
            logger.warning("No document found for job_id %s", job_id)

    client.close()
    return updated, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply previously scraped required field data to MongoDB."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="Path to required_fields JSON file. Defaults to the most recent file in ./data/",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    data_dir = Path("data")
    if args.file:
        filepath = Path(args.file)
    else:
        filepath = get_latest_results_file(data_dir)

    logger.info("Loading required field results from %s", filepath)
    results = load_results(filepath)

    if not results:
        logger.info("No entries found in %s; nothing to update.", filepath)
        return

    updated, skipped = update_documents(results)

    logger.info("MongoDB update complete.")
    logger.info("Documents updated: %s", updated)
    logger.info("Entries skipped: %s", skipped)


if __name__ == "__main__":
    main()


