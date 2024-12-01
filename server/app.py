import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional
from uuid import UUID, uuid4
from flask import Flask, jsonify

class JobStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class Job:
    id: UUID
    status: JobStatus
    start_time: float
    process_time: float

class JobManager:
    def __init__(self):
        self.jobs: Dict[UUID, Job] = {}

    def create_job(self, process_time: float = 10.0) -> UUID:
        job_id = uuid4()
        self.jobs[job_id] = Job(
            id=job_id,
            status=JobStatus.PENDING,
            start_time=time.time(),
            process_time=process_time
        )
        return job_id

    def get_job_status(self, job_id: UUID) -> Optional[JobStatus]:
        job = self.jobs.get(job_id)
        if not job:
            return None

        # Check if job should be completed based on elapsed time
        elapsed_time = time.time() - job.start_time
        if elapsed_time >= job.process_time and job.status == JobStatus.PENDING:
            job.status = JobStatus.COMPLETED

        return job.status

app = Flask(__name__)
job_manager = JobManager()

@app.route('/job', methods=['POST'])
def create_job():
    job_id = job_manager.create_job()
    return jsonify({
        "job_id": str(job_id),
        "status": JobStatus.PENDING.value
    }), 201

@app.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    try:
        job_id_uuid = UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job ID"}), 400

    status = job_manager.get_job_status(job_id_uuid)
    if status is None:
        return jsonify({"error": "Job not found"}), 404

    return jsonify({"result": status.value})

if __name__ == '__main__':
    app.run(debug=True)