import pytest
import threading
from server.app import app
from client.client import (
    TranslationClient, 
    PollingConfig,
    EventType,
    Event
)
import time
from datetime import datetime

def format_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')[:-3]

@pytest.fixture(scope="session")
def server():
    """Start the Flask server in a separate thread."""
    app.config['TESTING'] = True
    server_thread = threading.Thread(target=lambda: app.run(
        host='localhost',
        port=5000,
        debug=False,
        use_reloader=False
    ))
    server_thread.daemon = True
    server_thread.start()
    time.sleep(2)
    yield

class TestLogger:
    def __init__(self):
        self.events = []
        self.start_time = time.time()

    def log_event(self, event: Event):
        elapsed = time.time() - self.start_time
        self.events.append(event)
        print(f"\nEvent: {event.type.value}")
        print(f"Time: {format_time(time.time())} (Elapsed: {elapsed:.2f}s)")
        if isinstance(event.job_id, list):
            print(f"Job IDs: {event.job_id}")
        else:
            print(f"Job ID: {event.job_id}")
        if event.error:
            print(f"Error: {event.error}")
        if event.data:
            print(f"Data: {event.data}")
        print("-" * 40)

def test_single_job_flow(server):
    """Test single job creation and monitoring"""
    print("\nTesting single job flow...")
    
    client = TranslationClient(
        base_url="http://localhost:5000",
        polling_config=PollingConfig(
            initial_interval=0.5,
            max_interval=2.0,
            multiplier=1.5,
            jitter_factor=0.1,
            timeout=15.0
        )
    )

    logger = TestLogger()
    
    # Subscribe to all events
    for event_type in EventType:
        client.on(event_type, logger.log_event)

    try:
        print("\nCreating job...")
        job_id = client.create_job()
        print(f"Created job: {job_id}")

        print("\nWaiting for completion...")
        final_status = client.wait_for_completion(job_id)

        assert final_status == "completed"
        assert any(e.type == EventType.JOB_CREATED for e in logger.events)
        assert any(e.type == EventType.STATUS_CHANGED for e in logger.events)
        assert any(e.type == EventType.JOB_COMPLETED for e in logger.events)

    except Exception as e:
        print(f"\nTest error: {str(e)}")
        raise

def test_batch_operations(server):
    """Test batch job creation and monitoring"""
    print("\nTesting batch operations...")
    
    client = TranslationClient(
        base_url="http://localhost:5000",
        polling_config=PollingConfig(
            initial_interval=0.5,
            max_interval=2.0,
            timeout=30.0
        )
    )

    logger = TestLogger()
    
    # Subscribe to batch-related events
    client.on(EventType.BATCH_OPERATION, logger.log_event)
    client.on(EventType.JOB_COMPLETED, logger.log_event)
    client.on(EventType.ERROR_OCCURRED, logger.log_event)

    try:
        print("\nCreating batch jobs...")
        job_ids = client.create_batch_jobs(3)
        print(f"Created {len(job_ids)} jobs")

        print("\nWaiting for batch completion...")
        final_statuses = client.wait_for_batch_completion(job_ids)

        # Verify results
        assert len(final_statuses) == 3
        assert all(status == "completed" for status in final_statuses.values())
        assert any(e.type == EventType.BATCH_OPERATION for e in logger.events)

    except Exception as e:
        print(f"\nTest error: {str(e)}")
        raise

def test_error_handling_and_circuit_breaker(server):
    """Test error handling and circuit breaker functionality"""
    print("\nTesting error handling and circuit breaker...")
    
    client = TranslationClient(
        base_url="http://localhost:5000",
        polling_config=PollingConfig(
            initial_interval=0.5,
            max_interval=2.0,
            timeout=15.0
        )
    )

    logger = TestLogger()
    
    # Subscribe to error-related events
    client.on(EventType.ERROR_OCCURRED, logger.log_event)
    client.on(EventType.CIRCUIT_BREAKER_OPENED, logger.log_event)
    client.on(EventType.RETRY_ATTEMPTED, logger.log_event)

    try:
        # Test invalid job ID
        print("\nTesting invalid job ID...")
        with pytest.raises(Exception) as exc_info:
            client.get_status("invalid-job-id")
        
        print(f"Caught expected error: {str(exc_info.value)}")
        
        # Test circuit breaker
        print("\nTesting circuit breaker...")
        for _ in range(6):  # More than failure_threshold
            try:
                client.get_status("invalid-job-id")
            except Exception as e:
                print(f"Expected error: {str(e)}")
        
        # Verify events
        error_events = [e for e in logger.events if e.type == EventType.ERROR_OCCURRED]
        circuit_breaker_events = [e for e in logger.events if e.type == EventType.CIRCUIT_BREAKER_OPENED]
        
        print(f"\nCaptured {len(error_events)} error events")
        print(f"Captured {len(circuit_breaker_events)} circuit breaker events")
        
        assert len(error_events) > 0, "Should have captured error events"
        assert len(circuit_breaker_events) > 0, "Should have captured circuit breaker events"
        
    except Exception as e:
        print(f"\nUnexpected test error: {str(e)}")
        raise

def test_polling_strategy(server):
    """Test polling interval behavior"""
    print("\nTesting polling strategy...")
    
    client = TranslationClient(
        base_url="http://localhost:5000",
        polling_config=PollingConfig(
            initial_interval=0.5,
            max_interval=2.0,
            multiplier=2.0,
            timeout=15.0
        )
    )

    logger = TestLogger()
    client.on(EventType.STATUS_CHANGED, logger.log_event)

    try:
        job_id = client.create_job()
        final_status = client.wait_for_completion(job_id)

        # Verify increasing intervals between status checks
        status_events = [e for e in logger.events if e.type == EventType.STATUS_CHANGED]
        for i in range(1, len(status_events)):
            current_time = status_events[i].timestamp
            previous_time = status_events[i-1].timestamp
            interval = (current_time - previous_time).total_seconds()
            print(f"Interval between checks: {interval:.2f}s")

    except Exception as e:
        print(f"\nTest error: {str(e)}")
        raise

if __name__ == "__main__":
    pytest.main([__file__, "-vv", "-s"])