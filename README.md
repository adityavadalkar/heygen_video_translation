# HeyGen Translation Client Library Documentation

## Project Overview

This project implements a client library for HeyGen's video translation service as part of a technical assessment. The goal was to create a robust, production-ready client library that simulates interaction with a video translation service, focusing on efficient status polling and excellent developer experience.

## Assessment Requirements and Implementation

### Core Requirements Implementation

The project successfully implements all core requirements specified in the assessment:

1. **Server Implementation**
   We created a Flask-based server that simulates the video translation backend with configurable processing times. The server provides two key endpoints:
   * POST /job: Creates a new translation job
   * GET /status: Returns the current status of a job (pending/completed/error)
2. **Client Library**
   The core client library improves upon the trivial approach of simple HTTP calls by implementing:
   * Intelligent polling with exponential backoff
   * Proper error handling and status management
   * Clean, well-documented API for third-party developers
3. **Integration Testing**
   A comprehensive test suite demonstrates the library's functionality by:
   * Spinning up a test server
   * Creating and monitoring translation jobs
   * Verifying proper error handling
   * Testing various configuration scenarios

### Additional Features and Improvements

Beyond the basic requirements, we implemented several advanced features to make the library more robust and production-ready:

1. **Advanced Polling Strategy**
   * Exponential backoff with configurable parameters
   * Jitter implementation to prevent thundering herd problems
   * Configurable timeout settings
   * Smart interval adjustment based on server response patterns
2. **Circuit Breaker Pattern**
   * Automatic failure detection
   * Configurable failure thresholds
   * Self-healing mechanism with reset timeouts
   * Protection against cascade failures
3. **Comprehensive Event System**
   * Real-time job status monitoring
   * Custom event handlers for different job states
   * Detailed event data for debugging and logging
   * Support for multiple event subscribers
4. **Batch Operations Support**
   * Efficient handling of multiple translation jobs
   * Parallel status monitoring
   * Aggregate status reporting
   * Batch-specific error handling
5. **Enhanced Error Handling**
   * Hierarchical error classification
   * Retryable vs. non-retryable error distinction
   * Detailed error reporting
   * Custom exception classes for different scenarios
6. **Developer Experience**
   * Fluent API design
   * Comprehensive type hints
   * Extensive documentation with examples
   * Clear and consistent naming conventions

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from client import TranslationClient, PollingConfig

# Initialize the client with default settings
client = TranslationClient(base_url="http://your-server-url")

# Create a translation job
job_id = client.create_job()

# Wait for completion
final_status = client.wait_for_completion(job_id)
print(f"Job completed with status: {final_status}")
```

## Configuration

### Polling Configuration

The client's polling behavior can be customized using the `PollingConfig` class:

```python
polling_config = PollingConfig(
    initial_interval=0.5,    # Initial polling interval in seconds
    max_interval=5.0,        # Maximum polling interval
    multiplier=2.0,          # How quickly the interval increases
    jitter_factor=0.1,       # Randomization factor
    timeout=300.0           # Maximum total wait time
)

client = TranslationClient(
    base_url="http://your-server-url",
    polling_config=polling_config
)
```

## Event System

The client includes a powerful event system for monitoring job progress and handling errors.

### Available Events

- `JOB_CREATED`: Fired when a new job is created
- `STATUS_CHANGED`: Fired when a job's status changes
- `RETRY_ATTEMPTED`: Fired when a retry is attempted
- `ERROR_OCCURRED`: Fired when an error occurs
- `JOB_COMPLETED`: Fired when a job completes successfully
- `JOB_FAILED`: Fired when a job fails
- `TIMEOUT`: Fired when a timeout occurs
- `CIRCUIT_BREAKER_OPENED`: Fired when the circuit breaker trips
- `CIRCUIT_BREAKER_CLOSED`: Fired when the circuit breaker resets
- `BATCH_OPERATION`: Fired for batch operation events

### Event Handling Example

```python
from client import TranslationClient, EventType

def log_status_change(event):
    print(f"Job {event.job_id} changed status from {event.previous_state} to {event.current_state}")

client = TranslationClient()
client.on(EventType.STATUS_CHANGED, log_status_change)
```

## Batch Operations

The client supports efficient handling of multiple jobs:

```python
# Create multiple jobs
job_ids = client.create_batch_jobs(count=3)

# Wait for all jobs to complete
final_statuses = client.wait_for_batch_completion(job_ids)
```

## Error Handling

The client provides several error classes for different scenarios:

- `TranslationError`: Base exception class
- `RetryableError`: For temporary failures that can be retried
- `CircuitBreakerError`: For circuit breaker related errors
- `TimeoutError`: For timeout related errors

Example with error handling:

```python
from client import TranslationError, TimeoutError

try:
    status = client.wait_for_completion(job_id)
except TimeoutError:
    print("Job took too long to complete")
except TranslationError as e:
    print(f"Translation error occurred: {str(e)}")
```

## Best Practices

1. **Configure Timeouts Appropriately**
   - Set timeouts based on your expected job duration
   - Consider network latency in your timeout calculations

```python
config = PollingConfig(
    timeout=600.0  # 10 minutes for longer jobs
)
```

2. **Use Event Handlers for Monitoring**
   - Subscribe to relevant events for monitoring
   - Implement logging for important state changes

```python
def monitor_job(event):
    print(f"Event: {event.type} - Job: {event.job_id}")
    print(f"Data: {event.data}")

client.on(EventType.STATUS_CHANGED, monitor_job)
client.on(EventType.ERROR_OCCURRED, monitor_job)
```

3. **Implement Proper Error Handling**

   - Always wrap client calls in try-except blocks
   - Handle different error types appropriately
4. **Use Batch Operations for Multiple Jobs**

   - Prefer batch operations over multiple single operations
   - Implement proper error handling for batch operations

## Advanced Usage

### Custom Circuit Breaker Configuration

```python
from client import CircuitBreaker

client = TranslationClient()
client.circuit_breaker = CircuitBreaker(
    failure_threshold=5,    # Number of failures before opening
    reset_timeout=60.0      # Seconds until circuit resets
)
```

### Custom Event Handling

```python
class JobMonitor:
    def __init__(self):
        self.completed_jobs = 0
        self.failed_jobs = 0

    def on_completion(self, event):
        self.completed_jobs += 1
        print(f"Job {event.job_id} completed successfully")

    def on_failure(self, event):
        self.failed_jobs += 1
        print(f"Job {event.job_id} failed: {event.error}")

monitor = JobMonitor()
client.on(EventType.JOB_COMPLETED, monitor.on_completion)
client.on(EventType.JOB_FAILED, monitor.on_failure)
```

## Troubleshooting

### Common Issues and Solutions

1. **Circuit Breaker Trips Frequently**

   - Check network connectivity
   - Verify server health
   - Consider adjusting failure threshold
2. **Timeouts During Job Processing**

   - Increase timeout in PollingConfig
   - Check server processing capacity
   - Consider batch size adjustments
3. **High Error Rates**

   - Check error types in event logs
   - Verify API endpoint configuration
   - Review network stability

## API Reference

### TranslationClient

#### Methods

- `create_job() -> str`: Creates a new translation job
- `get_status(job_id: str) -> str`: Gets the current status of a job
- `wait_for_completion(job_id: str) -> str`: Waits for job completion
- `create_batch_jobs(count: int) -> List[str]`: Creates multiple jobs
- `wait_for_batch_completion(job_ids: List[str]) -> Dict[str, str]`: Waits for multiple jobs
- `on(event_type: EventType, callback: Callable)`: Subscribes to events
- `off(event_type: EventType, callback: Callable)`: Unsubscribes from events

#### Configuration Classes

- `PollingConfig`: Controls polling behavior
- `CircuitBreaker`: Manages failure handling
- `EventHandler`: Manages event subscriptions

## Support

For issues, bugs, or feature requests, please create an issue in the GitHub repository. For urgent support, contact the HeyGen support team.
