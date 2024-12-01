from enum import Enum
from typing import Optional, Callable, Dict, List, Union
from dataclasses import dataclass
from datetime import datetime
import time
import random
import requests
from urllib.parse import urljoin

class JobStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"

class TranslationError(Exception):
    """Base exception class for translation client"""
    pass

class RetryableError(TranslationError):
    """Exception class for errors that should trigger a retry"""
    pass

class CircuitBreakerError(TranslationError):
    """Exception class for circuit breaker related errors"""
    pass

class TimeoutError(TranslationError):
    """Exception class for timeout related errors"""
    pass

# ... rest of the client implementation remains the same ...

class JobStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"

class EventType(Enum):
    JOB_CREATED = "job_created"
    STATUS_CHANGED = "status_changed"
    RETRY_ATTEMPTED = "retry_attempted"
    ERROR_OCCURRED = "error_occurred"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    BATCH_OPERATION = "batch_operation"

@dataclass
class Event:
    type: EventType
    job_id: Union[str, List[str]]  # Can be single job_id or list for batch operations
    timestamp: datetime
    data: dict
    previous_state: Optional[str] = None
    current_state: Optional[str] = None
    error: Optional[Exception] = None
    retry_count: Optional[int] = None

class PollingConfig:
    def __init__(
        self,
        initial_interval: float = 0.5,
        max_interval: float = 5.0,
        multiplier: float = 2.0,
        jitter_factor: float = 0.1,
        timeout: float = 300.0
    ):
        self.initial_interval = initial_interval
        self.max_interval = max_interval
        self.multiplier = multiplier
        self.jitter_factor = jitter_factor
        self.timeout = timeout

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = None
        self.is_open = False

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.is_open = True

    def record_success(self):
        self.failures = 0
        self.is_open = False

    def can_execute(self) -> bool:
        if not self.is_open:
            return True
        
        if time.time() - self.last_failure_time >= self.reset_timeout:
            self.is_open = False
            self.failures = 0
            return True
            
        return False

class EventHandler:
    def __init__(self):
        self.listeners: Dict[EventType, List[Callable[[Event], None]]] = {
            event_type: [] for event_type in EventType
        }
        self.history: List[Event] = []
    
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        self.listeners[event_type].append(callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        if callback in self.listeners[event_type]:
            self.listeners[event_type].remove(callback)
    
    def dispatch(self, event: Event):
        self.history.append(event)
        for callback in self.listeners[event.type]:
            try:
                callback(event)
            except Exception as e:
                print(f"Error in event callback: {str(e)}")

class TranslationClient:
    def __init__(
        self,
        base_url: str = "http://localhost:5000",
        polling_config: Optional[PollingConfig] = None
    ):
        self.base_url = base_url
        self.session = requests.Session()
        self.polling_config = polling_config or PollingConfig()
        self.event_handler = EventHandler()
        self.circuit_breaker = CircuitBreaker()
        self.MAX_RETRIES = 3

    def _add_jitter(self, interval: float) -> float:
        jitter = interval * self.polling_config.jitter_factor
        return interval + random.uniform(-jitter, jitter)

    def _get_next_interval(self, current_interval: float) -> float:
        next_interval = min(
            current_interval * self.polling_config.multiplier,
            self.polling_config.max_interval
        )
        return self._add_jitter(next_interval)

    def _should_retry(self, exception: Exception) -> bool:
        if isinstance(exception, requests.exceptions.RequestException):
            if isinstance(exception, requests.exceptions.HTTPError):
                return 500 <= exception.response.status_code < 600
            return isinstance(exception, (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout
            ))
        return False

    def on(self, event_type: EventType, callback: Callable[[Event], None]):
        """Subscribe to an event"""
        self.event_handler.subscribe(event_type, callback)
        return self

    def off(self, event_type: EventType, callback: Callable[[Event], None]):
        """Unsubscribe from an event"""
        self.event_handler.unsubscribe(event_type, callback)
        return self

    def create_job(self) -> str:
        """Create a new translation job with circuit breaker and event handling"""
        if not self.circuit_breaker.can_execute():
            self.event_handler.dispatch(Event(
                type=EventType.CIRCUIT_BREAKER_OPENED,
                job_id="",
                timestamp=datetime.now(),
                data={"message": "Circuit breaker is open"}
            ))
            raise RuntimeError("Circuit breaker is open")

        try:
            response = self.session.post(urljoin(self.base_url, "job"))
            response.raise_for_status()
            job_id = response.json()["job_id"]
            
            self.circuit_breaker.record_success()
            self.event_handler.dispatch(Event(
                type=EventType.JOB_CREATED,
                job_id=job_id,
                timestamp=datetime.now(),
                data={"response": response.json()}
            ))
            
            return job_id
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            self.event_handler.dispatch(Event(
                type=EventType.ERROR_OCCURRED,
                job_id="",
                timestamp=datetime.now(),
                error=e,
                data={"action": "create_job"}
            ))
            raise

    def create_batch_jobs(self, count: int) -> List[str]:
        """Create multiple jobs at once"""
        job_ids = []
        errors = []

        for _ in range(count):
            try:
                job_id = self.create_job()
                job_ids.append(job_id)
            except Exception as e:
                errors.append(str(e))

        self.event_handler.dispatch(Event(
            type=EventType.BATCH_OPERATION,
            job_id=job_ids,
            timestamp=datetime.now(),
            data={
                "operation": "create",
                "success_count": len(job_ids),
                "error_count": len(errors),
                "errors": errors
            }
        ))

        return job_ids

    def get_status(self, job_id: str) -> str:
        """Get status with improved error handling and circuit breaker"""
        if not self.circuit_breaker.can_execute():
            self.event_handler.dispatch(Event(
                type=EventType.CIRCUIT_BREAKER_OPENED,
                job_id=job_id,
                timestamp=datetime.now(),
                data={"message": "Circuit breaker is open"}
            ))
            raise RuntimeError("Circuit breaker is open")

        try:
            response = self.session.get(urljoin(self.base_url, f"status/{job_id}"))
            
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                self.event_handler.dispatch(Event(
                    type=EventType.ERROR_OCCURRED,
                    job_id=job_id,
                    timestamp=datetime.now(),
                    error=http_err,
                    data={
                        "status_code": response.status_code,
                        "response_text": response.text
                    }
                ))
                self.circuit_breaker.record_failure()
                raise

            self.circuit_breaker.record_success()
            return response.json()["result"]
            
        except requests.exceptions.RequestException as e:
            self.event_handler.dispatch(Event(
                type=EventType.ERROR_OCCURRED,
                job_id=job_id,
                timestamp=datetime.now(),
                error=e,
                data={"error_type": type(e).__name__}
            ))
            self.circuit_breaker.record_failure()
            
            if self._should_retry(e):
                raise RetryableError("Retryable error occurred") from e
            raise

    def get_batch_status(self, job_ids: List[str]) -> Dict[str, str]:
        """Get status for multiple jobs"""
        statuses = {}
        errors = []

        for job_id in job_ids:
            try:
                status = self.get_status(job_id)
                statuses[job_id] = status
            except Exception as e:
                errors.append((job_id, str(e)))
                statuses[job_id] = "error"

        self.event_handler.dispatch(Event(
            type=EventType.BATCH_OPERATION,
            job_id=job_ids,
            timestamp=datetime.now(),
            data={
                "operation": "status_check",
                "statuses": statuses,
                "error_count": len(errors),
                "errors": errors
            }
        ))

        return statuses

    def wait_for_completion(
        self,
        job_id: str,
    ) -> str:
        """Wait for job completion with enhanced error handling and events"""
        start_time = time.time()
        current_interval = self.polling_config.initial_interval
        last_status = None
        retry_count = 0

        while True:
            if time.time() - start_time > self.polling_config.timeout:
                self.event_handler.dispatch(Event(
                    type=EventType.TIMEOUT,
                    job_id=job_id,
                    timestamp=datetime.now(),
                    data={"elapsed_time": time.time() - start_time}
                ))
                raise TimeoutError(f"Job {job_id} did not complete within {self.polling_config.timeout} seconds")

            try:
                status = self.get_status(job_id)
                
                if status != last_status:
                    self.event_handler.dispatch(Event(
                        type=EventType.STATUS_CHANGED,
                        job_id=job_id,
                        timestamp=datetime.now(),
                        previous_state=last_status,
                        current_state=status,
                        data={"attempt": retry_count + 1}
                    ))
                    last_status = status

                if status == JobStatus.ERROR.value:
                    self.event_handler.dispatch(Event(
                        type=EventType.JOB_FAILED,
                        job_id=job_id,
                        timestamp=datetime.now(),
                        data={"final_status": status}
                    ))
                    raise RuntimeError(f"Job {job_id} failed with error status")
                
                if status == JobStatus.COMPLETED.value:
                    self.event_handler.dispatch(Event(
                        type=EventType.JOB_COMPLETED,
                        job_id=job_id,
                        timestamp=datetime.now(),
                        data={"final_status": status}
                    ))
                    return status

                current_interval = self._get_next_interval(current_interval)
                time.sleep(current_interval)

            except RetryableError as e:
                retry_count += 1
                if retry_count > self.MAX_RETRIES:
                    raise RuntimeError(f"Max retries ({self.MAX_RETRIES}) exceeded") from e
                
                self.event_handler.dispatch(Event(
                    type=EventType.RETRY_ATTEMPTED,
                    job_id=job_id,
                    timestamp=datetime.now(),
                    error=e,
                    retry_count=retry_count,
                    data={"next_interval": current_interval}
                ))
                current_interval = self._get_next_interval(current_interval)
                time.sleep(current_interval)
                continue
            
            except Exception as e:
                self.event_handler.dispatch(Event(
                    type=EventType.ERROR_OCCURRED,
                    job_id=job_id,
                    timestamp=datetime.now(),
                    error=e,
                    data={"action": "wait_for_completion"}
                ))
                raise

    def wait_for_batch_completion(
        self,
        job_ids: List[str],
    ) -> Dict[str, str]:
        """Wait for multiple jobs to complete"""
        final_statuses = {}
        start_time = time.time()

        while job_ids:
            if time.time() - start_time > self.polling_config.timeout:
                remaining_jobs = [jid for jid in job_ids if jid not in final_statuses]
                self.event_handler.dispatch(Event(
                    type=EventType.TIMEOUT,
                    job_id=remaining_jobs,
                    timestamp=datetime.now(),
                    data={
                        "elapsed_time": time.time() - start_time,
                        "completed_jobs": len(final_statuses),
                        "remaining_jobs": len(remaining_jobs)
                    }
                ))
                raise TimeoutError(f"Batch operation did not complete within {self.polling_config.timeout} seconds")

            statuses = self.get_batch_status(job_ids)
            
            # Update completed/failed jobs
            for job_id in list(job_ids):  # Create copy for safe modification
                status = statuses.get(job_id)
                if status in [JobStatus.COMPLETED.value, JobStatus.ERROR.value]:
                    final_statuses[job_id] = status
                    job_ids.remove(job_id)

            if job_ids:
                time.sleep(self._get_next_interval(self.polling_config.initial_interval))

        return final_statuses