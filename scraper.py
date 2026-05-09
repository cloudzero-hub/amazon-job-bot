import json
import os
import time
from typing import Optional
from config import Config

# ─── Seen-Jobs Persistence ────────────────────────────────────────────────────

SEEN_IDS_FILE = "seen_jobs.json"

class AmazonJobScraper:

    def load_seen_ids(self) -> set:
        if os.path.exists(SEEN_IDS_FILE):
            with open(SEEN_IDS_FILE, "r") as f:
                return set(json.load(f))
        return set()

    def save_seen_ids(self, ids: set):
        with open(SEEN_IDS_FILE, "w") as f:
            json.dump(list(ids), f)

    # ─── Main Fetch ───────────────────────────────────────────────────────────

    def fetch_jobs(self, keyword: Optional[str] = None) -> list[dict]:
        """
        Launches a headless browser, navigates to the Amazon jobs page,
        waits for listings to load, and returns parsed job data.
        """
        from playwright.sync_api import sync_playwright

        url = Config.JOB_URL
        location = keyword or Config.LOCATION_FILTER or ""

        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="en-CA",
                timezone_id="America/Toronto"
            )
            page = context.new_page()

            # Block images/fonts to speed up scraping
            page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}", lambda route: route.abort())

            print(f"  → Navigating to {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)

            # If a keyword/location was given, type it into the search box
            if location:
                try:
                    # Try city/location search field
                    loc_input = page.locator('input[placeholder*="ity"], input[placeholder*="ocation"], input[id*="location"]').first
                    loc_input.fill(location)
                    page.keyboard.press("Enter")
                    time.sleep(2)
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

            # Wait for job cards to appear
            try:
                page.wait_for_selector(
                    '[data-test="job-card"], .jobTile, [class*="jobCard"], [class*="job-card"], [class*="JobCard"]',
                    timeout=20000
                )
            except Exception:
                print("  ⚠️  Job cards not found — page may have changed structure.")

            time.sleep(2)  # let lazy-loaded items settle

            # Scroll to load more jobs
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

            jobs = self._parse_jobs(page)
            browser.close()

        return jobs

    # ─── Parser ───────────────────────────────────────────────────────────────

    def _parse_jobs(self, page) -> list[dict]:
        """Extract job data from the rendered page."""
        jobs = []

        # Try multiple selectors — Amazon's SPA structure may vary
        card_selectors = [
            '[data-test="job-card"]',
            '.jobTile',
            '[class*="jobCard"]',
            '[class*="job-card"]',
            '[class*="JobCard"]',
            'li[class*="job"]',
        ]

        cards = []
        for sel in card_selectors:
            cards = page.query_selector_all(sel)
            if cards:
                print(f"  → Found {len(cards)} job cards via selector: {sel}")
                break

        if not cards:
            print("  ⚠️  Could not locate job cards. Dumping raw text for debugging...")
            return []

        for card in cards:
            try:
                job = self._extract_job_from_card(card, page)
                if job:
                    jobs.append(job)
            except Exception as e:
                print(f"  ⚠️  Error parsing card: {e}")

        return jobs

    def _extract_job_from_card(self, card, page) -> Optional[dict]:
        """Extract fields from a single job card element."""

        def get_text(*selectors):
            for sel in selectors:
                el = card.query_selector(sel)
                if el:
                    txt = el.inner_text().strip()
                    if txt:
                        return txt
            return ""

        # Title
        title = get_text(
            '[data-test="job-title"]', '[class*="title"]', 'h2', 'h3',
            '[class*="Title"]', 'a[class*="job"]'
        )
        if not title:
            return None

        # Job URL
        link_el = card.query_selector('a[href]')
        href = link_el.get_attribute("href") if link_el else ""
        if href and not href.startswith("http"):
            href = "https://hiring.amazon.ca" + href
        url = href or Config.JOB_URL

        # Generate a stable ID from title + URL
        job_id = f"{title.lower().replace(' ', '_')}_{href[-20:] if href else 'noid'}"

        # Other fields
        location = get_text('[data-test="job-location"]', '[class*="location"]', '[class*="Location"]')
        job_type  = get_text('[data-test="job-type"]',     '[class*="type"]',     '[class*="Type"]')
        pay       = get_text('[data-test="job-pay"]',      '[class*="pay"]',      '[class*="Pay"]', '[class*="wage"]', '[class*="Wage"]')
        shift     = get_text('[data-test="job-shift"]',    '[class*="shift"]',    '[class*="Shift"]')
        posted    = get_text('[data-test="posted-date"]',  '[class*="date"]',     '[class*="Date"]')
        desc      = get_text('[data-test="job-desc"]',     '[class*="desc"]',     'p')

        return {
            "id":          job_id,
            "title":       title,
            "url":         url,
            "location":    location,
            "job_type":    job_type,
            "pay":         pay,
            "shift":       shift,
            "posted_date": posted,
            "description": desc,
        }

    # ─── New-Jobs Check ───────────────────────────────────────────────────────

    def get_new_jobs(self) -> list[dict]:
        """
        Fetch all current jobs and return only ones not seen before.
        Persists seen IDs to disk.
        """
        seen = self.load_seen_ids()
        all_jobs = self.fetch_jobs()

        new_jobs = [j for j in all_jobs if j["id"] not in seen]

        if new_jobs:
            seen.update(j["id"] for j in new_jobs)
            self.save_seen_ids(seen)

        return new_jobs
