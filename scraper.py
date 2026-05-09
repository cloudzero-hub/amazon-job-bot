import json
import os
import requests
from typing import Optional
from config import Config

SEEN_IDS_FILE = "seen_jobs.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-CA,en;q=0.9",
    "Referer": "https://hiring.amazon.ca/",
    "Origin": "https://hiring.amazon.ca",
}

API_URL = "https://hiring.amazon.ca/api/v1/jobs"

class AmazonJobScraper:

    def load_seen_ids(self) -> set:
        if os.path.exists(SEEN_IDS_FILE):
            with open(SEEN_IDS_FILE, "r") as f:
                return set(json.load(f))
        return set()

    def save_seen_ids(self, ids: set):
        with open(SEEN_IDS_FILE, "w") as f:
            json.dump(list(ids), f)

    def fetch_jobs(self, keyword: Optional[str] = None) -> list:
        jobs = []
        location = keyword or Config.LOCATION_FILTER or ""

        params = {
            "locale": "en-CA",
            "country": "Canada",
            "offset": 0,
            "result_limit": 50,
            "sort": "RELEVANCE",
        }

        if location:
            params["city"] = location

        try:
            print(f"  → Calling Amazon Jobs API...")
            response = requests.get(API_URL, headers=HEADERS, params=params, timeout=30)
            print(f"  → Status code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                job_list = data.get("jobs", data.get("data", data.get("results", [])))

                if isinstance(data, list):
                    job_list = data

                print(f"  → Found {len(job_list)} jobs from API")

                for item in job_list:
                    job = self._parse_job(item)
                    if job:
                        jobs.append(job)
            else:
                print(f"  ⚠️ API returned status {response.status_code}")
                # Try alternative API
                jobs = self._try_alternative_api(location)

        except Exception as e:
            print(f"  ⚠️ API error: {e}")
            jobs = self._try_alternative_api(location)

        print(f"  → Total jobs parsed: {len(jobs)}")
        return jobs

    def _try_alternative_api(self, location: str = "") -> list:
        jobs = []
        alt_urls = [
            "https://hiring.amazon.ca/api/jobs",
            "https://hiring.amazon.ca/api/v2/jobs",
            f"https://hiring.amazon.ca/api/v1/jobs?locale=en-CA&country=Canada&result_limit=50",
        ]
        for url in alt_urls:
            try:
                print(f"  → Trying: {url}")
                r = requests.get(url, headers=HEADERS, timeout=30)
                print(f"  → Status: {r.status_code}")
                if r.status_code == 200:
                    data = r.json()
                    job_list = data.get("jobs", data.get("data", data.get("results", [])))
                    if isinstance(data, list):
                        job_list = data
                    for item in job_list:
                        job = self._parse_job(item)
                        if job:
                            jobs.append(job)
                    if jobs:
                        print(f"  → Found {len(jobs)} jobs!")
                        break
            except Exception as e:
                print(f"  ⚠️ Error: {e}")
                continue
        return jobs

    def _parse_job(self, item: dict) -> Optional[dict]:
        if not isinstance(item, dict):
            return None

        title = (
            item.get("title") or item.get("job_title") or
            item.get("jobTitle") or item.get("name") or ""
        )
        if not title:
            return None

        job_id = str(item.get("id") or item.get("jobId") or item.get("job_id") or title[:20])
        location = (
            item.get("location") or item.get("city") or
            item.get("jobLocation") or item.get("address", {}).get("city", "") or ""
        )
        if isinstance(location, dict):
            location = location.get("city", "") or location.get("name", "")

        pay = item.get("pay") or item.get("salary") or item.get("wage") or item.get("basePay") or ""
        job_type = item.get("jobType") or item.get("job_type") or item.get("employmentType") or ""
        shift = item.get("shift") or item.get("shiftType") or item.get("schedule") or ""
        posted = item.get("postedDate") or item.get("posted_date") or item.get("createdAt") or ""
        desc = item.get("description") or item.get("jobDescription") or item.get("summary") or ""

        job_url = item.get("url") or item.get("applyUrl") or item.get("apply_url") or ""
        if not job_url:
            job_url = f"https://hiring.amazon.ca/app#/jobSearch"

        return {
            "id": job_id,
            "title": title,
            "url": job_url,
            "location": str(location),
            "job_type": str(job_type),
            "pay": str(pay),
            "shift": str(shift),
            "posted_date": str(posted),
            "description": str(desc)[:300],
        }

    def get_new_jobs(self) -> list:
        seen = self.load_seen_ids()
        all_jobs = self.fetch_jobs()
        new_jobs = [j for j in all_jobs if j["id"] not in seen]
        if new_jobs:
            seen.update(j["id"] for j in new_jobs)
            self.save_seen_ids(seen)
        return new_jobs
