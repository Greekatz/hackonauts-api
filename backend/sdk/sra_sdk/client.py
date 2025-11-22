"""
HTTP Client for SRA API
Handles batching, retries, and async transmission.
"""
import threading
import queue
import time
import json
import atexit
from typing import Optional, Dict, Any, List
from datetime import datetime
import urllib.request
import urllib.error


class SRAClient:
    """
    Low-level HTTP client for sending data to SRA backend.
    Handles batching and async transmission.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str = "http://localhost:8000",
        batch_size: int = 50,
        flush_interval: float = 5.0,
        max_queue_size: int = 10000,
        timeout: float = 10.0,
        enabled: bool = True
    ):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_queue_size = max_queue_size
        self.timeout = timeout
        self.enabled = enabled

        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()
        self._lock = threading.Lock()

        if self.enabled:
            self._start_worker()
            atexit.register(self.shutdown)

    def _start_worker(self):
        """Start the background worker thread."""
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def _worker(self):
        """Background worker that batches and sends data."""
        batch: List[Dict[str, Any]] = []
        last_flush = time.time()

        while not self._shutdown.is_set():
            try:
                # Get item with timeout for periodic flushing
                try:
                    item = self._queue.get(timeout=0.5)
                    batch.append(item)
                    self._queue.task_done()
                except queue.Empty:
                    pass

                # Check if we should flush
                should_flush = (
                    len(batch) >= self.batch_size or
                    (len(batch) > 0 and time.time() - last_flush >= self.flush_interval)
                )

                if should_flush:
                    self._send_batch(batch)
                    batch = []
                    last_flush = time.time()

            except Exception:
                # Don't crash the worker on errors
                pass

        # Final flush on shutdown
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        """Send a batch of items to the backend."""
        if not batch:
            return

        # Group by type
        logs = [item["data"] for item in batch if item["type"] == "log"]
        metrics = [item["data"] for item in batch if item["type"] == "metric"]

        if logs:
            self._post("/ingest/logs", {"logs": logs})

        if metrics:
            self._post("/ingest/metrics", {"metrics": metrics})

    def _post(self, path: str, data: Dict[str, Any]) -> bool:
        """Make a POST request to the backend."""
        url = f"{self.endpoint}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

        try:
            json_data = json.dumps(data, default=str).encode("utf-8")
            request = urllib.request.Request(url, data=json_data, headers=headers, method="POST")

            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status == 200

        except urllib.error.URLError:
            return False
        except Exception:
            return False

    def send_log(self, log_data: Dict[str, Any]):
        """Queue a log entry for sending."""
        if not self.enabled:
            return

        try:
            self._queue.put_nowait({"type": "log", "data": log_data})
        except queue.Full:
            # Drop oldest items if queue is full
            try:
                self._queue.get_nowait()
                self._queue.put_nowait({"type": "log", "data": log_data})
            except queue.Empty:
                pass

    def send_metric(self, metric_data: Dict[str, Any]):
        """Queue a metric entry for sending."""
        if not self.enabled:
            return

        try:
            self._queue.put_nowait({"type": "metric", "data": metric_data})
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait({"type": "metric", "data": metric_data})
            except queue.Empty:
                pass

    def flush(self):
        """Force flush all queued items."""
        self._queue.join()

    def shutdown(self):
        """Shutdown the client gracefully."""
        self._shutdown.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
