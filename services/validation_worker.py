"""
Background Validation Worker for Che168

Proactively validates car availability by checking recent search results
against the detail API. Cars detected as sold are added to the sold registry.
"""

import asyncio
import logging
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.che168_service import Che168Service

logger = logging.getLogger(__name__)


class ValidationWorker:
    """
    Background worker that validates car availability from recent search cache.

    Runs periodically, checking car IDs from diskcache search results against
    the detail API to proactively detect sold cars.
    """

    def __init__(self, che168_service: "Che168Service"):
        self.che168_service = che168_service
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._validated_count = 0
        self._sold_found = 0
        self._last_run_time = 0.0
        self._errors = 0
        self._cycle_count = 0

    async def start(self) -> None:
        """Start the background validation worker."""
        if self._running:
            logger.warning("Validation worker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Background validation worker started")

    async def stop(self) -> None:
        """Stop the background validation worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Background validation worker stopped")

    async def _run_loop(self) -> None:
        """Main loop that runs validation cycles."""
        # Wait 30 seconds before first run to let the service warm up
        await asyncio.sleep(30)

        while self._running:
            try:
                await self._run_validation_cycle()
                self._cycle_count += 1

                # Purge entries older than 7 days every 100 cycles (~100 min)
                if self._cycle_count % 100 == 0:
                    try:
                        purged = self.che168_service.sold_registry.purge_old_entries(604800)
                        if purged > 0:
                            logger.info(f"Auto-purged {purged} old sold car entries")
                    except Exception as purge_err:
                        logger.debug(f"Auto-purge error: {purge_err}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Validation cycle error: {e}")
                self._errors += 1

            # Wait 60 seconds between cycles
            await asyncio.sleep(60)

    async def _run_validation_cycle(self) -> None:
        """Run a single validation cycle."""
        self._last_run_time = time.time()

        # Get car IDs from recent search cache
        car_ids = self._get_cached_car_ids()
        if not car_ids:
            logger.debug("No car IDs to validate from cache")
            return

        # Filter out already-known sold cars
        registry = self.che168_service.sold_registry
        unvalidated = [cid for cid in car_ids if not registry.is_sold(cid)]

        if not unvalidated:
            logger.debug("All cached car IDs already validated")
            return

        # Limit to reasonable batch size per cycle
        batch = unvalidated[:25]
        logger.info(f"Validating {len(batch)} cars (from {len(unvalidated)} unvalidated)")

        # Process in sub-batches of 5 with delays
        BATCH_SIZE = 5
        for i in range(0, len(batch), BATCH_SIZE):
            if not self._running:
                break

            sub_batch = batch[i:i + BATCH_SIZE]
            for car_id in sub_batch:
                if not self._running:
                    break

                try:
                    result = await self.che168_service.get_car_info(car_id)
                    self._validated_count += 1

                    if result.get("sold"):
                        self._sold_found += 1
                        logger.info(f"Background validation: car {car_id} is sold")
                except Exception as e:
                    logger.debug(f"Validation error for car {car_id}: {e}")
                    self._errors += 1

                # 0.5s between individual requests
                await asyncio.sleep(0.5)

            # 2s between sub-batches
            if i + BATCH_SIZE < len(batch):
                await asyncio.sleep(2)

    def _get_cached_car_ids(self) -> list[int]:
        """Extract car IDs from the diskcache search results."""
        car_ids = set()
        try:
            cache = self.che168_service.cache
            for key in cache:
                try:
                    data = cache.get(key)
                    if isinstance(data, dict) and "result" in data:
                        carlist = data.get("result", {}).get("carlist", [])
                        for car in carlist:
                            infoid = car.get("infoid")
                            if infoid:
                                car_ids.add(int(infoid))
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Error reading cache for validation: {e}")

        return list(car_ids)

    def get_status(self) -> dict:
        """Get worker status for monitoring."""
        return {
            "running": self._running,
            "validated_count": self._validated_count,
            "sold_found": self._sold_found,
            "errors": self._errors,
            "cycle_count": self._cycle_count,
            "last_run_time": self._last_run_time,
            "seconds_since_last_run": int(time.time() - self._last_run_time) if self._last_run_time else None,
        }
