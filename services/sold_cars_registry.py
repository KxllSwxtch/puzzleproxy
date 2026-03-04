"""
Sold Cars Registry - SQLite-backed persistence for known sold car IDs

Tracks cars detected as sold/delisted from Che168 so the backend can filter
them from search results before sending to the frontend.
"""

import sqlite3
import time
import threading
import logging
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

logger = logging.getLogger(__name__)

# Default DB path
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "sold_cars.db"


class SoldCarsRegistry:
    """
    SQLite-backed registry of sold car IDs with in-memory cache.

    Uses an in-memory Set for O(1) lookups, refreshed periodically from SQLite.
    SQLite provides persistence across restarts.
    """

    def __init__(self, db_path: Optional[Path] = None, cache_refresh_seconds: int = 300):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.cache_refresh_seconds = cache_refresh_seconds
        self._sold_ids: Set[int] = set()
        self._last_cache_refresh = 0.0
        self._lock = threading.Lock()

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        # Load initial cache
        self._refresh_cache()

    def _init_db(self) -> None:
        """Create the sold_cars table if it doesn't exist."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sold_cars (
                        infoid INTEGER PRIMARY KEY,
                        detected_at REAL NOT NULL,
                        source TEXT NOT NULL DEFAULT 'api',
                        message TEXT
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sold_cars_detected_at
                    ON sold_cars(detected_at)
                """)
                conn.commit()
            logger.info(f"Sold cars registry initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize sold cars DB: {e}")

    def _refresh_cache(self) -> None:
        """Reload the in-memory cache from SQLite."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("SELECT infoid FROM sold_cars")
                with self._lock:
                    self._sold_ids = {row[0] for row in cursor.fetchall()}
                    self._last_cache_refresh = time.time()
            logger.debug(f"Sold cars cache refreshed: {len(self._sold_ids)} entries")
        except Exception as e:
            logger.error(f"Failed to refresh sold cars cache: {e}")

    def _ensure_cache_fresh(self) -> None:
        """Refresh cache if it's stale."""
        with self._lock:
            needs_refresh = time.time() - self._last_cache_refresh > self.cache_refresh_seconds
        if needs_refresh:
            self._refresh_cache()

    def mark_sold(self, infoid: int, source: str = "api", message: str = "") -> None:
        """Mark a car as sold in both SQLite and in-memory cache."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO sold_cars (infoid, detected_at, source, message)
                       VALUES (?, ?, ?, ?)""",
                    (infoid, time.time(), source, message)
                )
                conn.commit()

            with self._lock:
                self._sold_ids.add(infoid)

            logger.debug(f"Marked car {infoid} as sold (source={source})")
        except Exception as e:
            logger.error(f"Failed to mark car {infoid} as sold: {e}")

    def is_sold(self, infoid: int) -> bool:
        """Check if a car is known to be sold (O(1) from in-memory cache)."""
        self._ensure_cache_fresh()
        with self._lock:
            return infoid in self._sold_ids

    def filter_sold(self, car_list: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
        """
        Filter out known sold cars from a car list.

        Returns:
            Tuple of (filtered_list, removed_count)
        """
        self._ensure_cache_fresh()
        with self._lock:
            sold_ids = self._sold_ids.copy()

        filtered = []
        removed = 0
        for car in car_list:
            infoid = car.get("infoid")
            if infoid and int(infoid) in sold_ids:
                removed += 1
            else:
                filtered.append(car)

        if removed > 0:
            logger.info(f"Filtered {removed} sold cars from search results")

        return filtered, removed

    def get_sold_count(self) -> int:
        """Get total number of known sold cars."""
        self._ensure_cache_fresh()
        with self._lock:
            return len(self._sold_ids)

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        self._ensure_cache_fresh()
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM sold_cars")
                db_count = cursor.fetchone()[0]

                cursor = conn.execute(
                    "SELECT COUNT(*) FROM sold_cars WHERE detected_at > ?",
                    (time.time() - 3600,)
                )
                last_hour = cursor.fetchone()[0]

                cursor = conn.execute(
                    "SELECT COUNT(*) FROM sold_cars WHERE detected_at > ?",
                    (time.time() - 86400,)
                )
                last_24h = cursor.fetchone()[0]

            with self._lock:
                cache_count = len(self._sold_ids)

            return {
                "total_sold": db_count,
                "cache_size": cache_count,
                "added_last_hour": last_hour,
                "added_last_24h": last_24h,
                "cache_age_seconds": int(time.time() - self._last_cache_refresh),
                "db_path": str(self.db_path),
            }
        except Exception as e:
            logger.error(f"Failed to get sold cars stats: {e}")
            return {"error": str(e)}

    def get_recent_sold_ids(self, limit: int = 100) -> List[int]:
        """Get the most recently detected sold car IDs."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT infoid FROM sold_cars ORDER BY detected_at DESC LIMIT ?",
                    (limit,)
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get recent sold IDs: {e}")
            return []

    def purge_old_entries(self, max_age_seconds: int = 604800) -> int:
        """Delete entries older than max_age_seconds (default 7 days). Returns count removed."""
        try:
            cutoff = time.time() - max_age_seconds
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "DELETE FROM sold_cars WHERE detected_at < ?", (cutoff,)
                )
                removed = cursor.rowcount
                conn.commit()

            if removed > 0:
                self._refresh_cache()
                logger.info(f"Purged {removed} sold car entries older than {max_age_seconds}s")

            return removed
        except Exception as e:
            logger.error(f"Failed to purge old sold car entries: {e}")
            return 0

    def clear_all(self) -> int:
        """Remove all entries from the registry. Returns count removed."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("DELETE FROM sold_cars")
                removed = cursor.rowcount
                conn.commit()

            with self._lock:
                self._sold_ids.clear()
                self._last_cache_refresh = time.time()

            logger.info(f"Cleared all {removed} sold car entries")
            return removed
        except Exception as e:
            logger.error(f"Failed to clear sold cars registry: {e}")
            return 0
