"""
Solution 3: FastAPI application with in-app IP monitoring.

Demonstrates using the @monitor_ip_status decorator to check subnet IP
availability before creating network resources. This is a proactive approach
that prevents resource creation when IPs are exhausted.

Usage:
    uvicorn solution3_app:app --reload
    curl -X POST http://localhost:8000/create-nic \
      -H "Content-Type: application/json" \
      -d '{"nic_name": "test-nic-1"}'
"""

import os
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from solution3_ip_monitor_decorator import (
    monitor_ip_status,
    get_subnet_ip_status,
    IPAvailabilityError
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Solution 3: In-App IP Monitor",
    description="FastAPI with IP monitoring decorator for NIC creation",
    version="1.0.0"
)

# Configuration from environment
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID", "")
RESOURCE_GROUP = os.getenv("RESOURCE_GROUP", "")
VNET_NAME = os.getenv("VNET_NAME", "")
SUBNET_NAME = os.getenv("SUBNET_NAME", "")


class CreateNICRequest(BaseModel):
    nic_name: str
    min_free_ips: Optional[int] = 1


class CreateNICResponse(BaseModel):
    status: str
    nic_name: str
    message: str


class SubnetStatusResponse(BaseModel):
    subnet_name: str
    total_ips: int
    used_ips: int
    free_ips: int
    utilization_percent: float
    address_prefix: str


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/subnet-status", response_model=SubnetStatusResponse)
async def get_status():
    """
    Get current subnet IP status.

    Returns subnet IP metrics without creating any resources.
    Useful for pre-flight checks and monitoring.
    """
    if not all([SUBSCRIPTION_ID, RESOURCE_GROUP, VNET_NAME, SUBNET_NAME]):
        raise HTTPException(
            status_code=400,
            detail="Missing configuration: SUBSCRIPTION_ID, RESOURCE_GROUP, VNET_NAME, SUBNET_NAME"
        )

    ip_status = get_subnet_ip_status(
        SUBSCRIPTION_ID,
        RESOURCE_GROUP,
        VNET_NAME,
        SUBNET_NAME
    )

    if ip_status is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to query subnet IP status"
        )

    return SubnetStatusResponse(
        subnet_name=ip_status.subnet_name,
        total_ips=ip_status.total_ips,
        used_ips=ip_status.used_ips,
        free_ips=ip_status.free_ips,
        utilization_percent=ip_status.utilization_percent,
        address_prefix=ip_status.address_prefix
    )


# The decorator applied here
# In real usage, this would create an actual Azure NIC
# For testing, it just simulates the creation
def create_nic_impl(nic_name: str) -> dict:
    """Simulate NIC creation (in real app, would call Azure SDK)."""
    logger.info(f"Creating NIC: {nic_name}")
    # In production, this would:
    # 1. Call Azure NetworkManagementClient to create the NIC
    # 2. Assign an IP from the subnet
    # 3. Configure network settings
    return {
        "id": f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.Network/networkInterfaces/{nic_name}",
        "name": nic_name,
        "status": "created"
    }


# Apply the decorator - always enforce security gate, fail closed
def _apply_decorator():
    """Ensure decorator is always applied (fail-closed security pattern)."""
    if not all([SUBSCRIPTION_ID, RESOURCE_GROUP, VNET_NAME, SUBNET_NAME]):
        raise ValueError("Missing required config: SUBSCRIPTION_ID, RESOURCE_GROUP, VNET_NAME, SUBNET_NAME")
    return monitor_ip_status(
        subscription_id=SUBSCRIPTION_ID,
        resource_group=RESOURCE_GROUP,
        vnet_name=VNET_NAME,
        subnet_name=SUBNET_NAME,
        min_free_ips=1
    )(create_nic_impl)

try:
    create_nic_impl = _apply_decorator()
except ValueError as e:
    logger.error(f"Security configuration error: {e}")
    # Fail closed: raise on startup if config missing
    raise


@app.post("/create-nic", response_model=CreateNICResponse)
async def create_nic(request: CreateNICRequest):
    """
    Create a NIC with IP availability check.

    The @monitor_ip_status decorator ensures sufficient free IPs exist
    before creation proceeds. If not, returns 409 Conflict.

    Args:
        request: NIC creation request with name

    Returns:
        Success response with NIC details

    Raises:
        HTTPException 400: Missing configuration
        HTTPException 409: Insufficient free IPs
        HTTPException 500: Azure API error
    """
    if not all([SUBSCRIPTION_ID, RESOURCE_GROUP, VNET_NAME, SUBNET_NAME]):
        raise HTTPException(
            status_code=400,
            detail="Missing Azure configuration. Set: SUBSCRIPTION_ID, RESOURCE_GROUP, VNET_NAME, SUBNET_NAME"
        )

    try:
        # The decorator checks IP availability before this runs
        result = create_nic_impl(request.nic_name)

        return CreateNICResponse(
            status="success",
            nic_name=request.nic_name,
            message=f"NIC created successfully: {result['id']}"
        )

    except IPAvailabilityError as e:
        logger.warning(f"NIC creation blocked: {e}")
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient IPs in subnet: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Error creating NIC: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create NIC: {str(e)}"
        )


# Note: Removed unsafe endpoint - always enforce IP validation for security


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
