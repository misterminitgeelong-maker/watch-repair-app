"""Links sent to customers when a job is booked in or changes status.

They open the customer portal (My Repairs) rather than the bare status page.
The portal page swaps the job's own status token for a customer-scoped portal
session, so there is no sign-in step.
"""
from .config import settings

PORTAL_JOB_TYPES = ("watch", "shoe", "auto_key")


def customer_portal_job_url(job_type: str, status_token: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/customer-portal/j/{job_type}/{status_token}"
