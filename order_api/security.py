import os
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Caller:
    sub: str
    role: str


def gateway_caller(request: Request) -> Caller:
    expected = os.environ.get("GATEWAY_SECRET", "")
    provided = request.headers.get("x-gateway-secret", "")
    if not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Gateway authentication required")
    sub = request.headers.get("x-consumer-id", "").strip()
    role = request.headers.get("x-consumer-role", "").strip()
    if not sub or len(sub) > 255 or role not in {"customer", "staff"}:
        raise HTTPException(status_code=403, detail="Invalid gateway identity")
    return Caller(sub=sub, role=role)


def customer_caller(request: Request) -> Caller:
    caller = gateway_caller(request)
    if caller.role != "customer":
        raise HTTPException(status_code=403, detail="Customer key required")
    return caller


def staff_caller(request: Request) -> Caller:
    caller = gateway_caller(request)
    if caller.role != "staff":
        raise HTTPException(status_code=403, detail="Staff key required")
    return caller

