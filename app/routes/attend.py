"""attend.py - Attendance endpoints: receive and store table rows."""

from datetime import date as _date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["attendance"])
