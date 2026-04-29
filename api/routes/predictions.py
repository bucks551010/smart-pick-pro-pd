"""api/routes/predictions.py – Prediction endpoints."""
import os
import json
import datetime
from utils.logger import get_logger

_logger = get_logger(__name__)

try:
    from fastapi import APIRouter, Depends, HTTPException
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from utils.jwt_utils import verify_access_token
    router = APIRouter(prefix="/predictions", tags=["predictions"])
    _FASTAPI_AVAILABLE = True
    _bearer = HTTPBearer(auto_error=False)

    async def _optional_jwt(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
        """Verify Bearer JWT if provided; raises 401 on invalid token."""
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        payload = verify_access_token(credentials.credentials)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return payload

except ImportError:
    _FASTAPI_AVAILABLE = False
    router = None

_EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "processed"
)


def _load_predictions_for_date(date_str: str) -> list:
    """Load predictions JSON for a given date.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        List of prediction dicts, or empty list.
    """
    path = os.path.join(_EXPORT_DIR, f"predictions_{date_str}.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            _logger.error("Could not load predictions file %s: %s", path, exc)
    return []


if _FASTAPI_AVAILABLE:
    @router.get("/today")
    async def get_today_predictions(_user=Depends(_optional_jwt)):
        """Return today's predictions from the latest pipeline run.

        Returns:
            JSON list of predictions or a message if none available.
        """
        date_str = datetime.date.today().isoformat()
        predictions = _load_predictions_for_date(date_str)
        return {"date": date_str, "predictions": predictions, "count": len(predictions)}

    @router.get("/{date}")
    async def get_predictions_by_date(date: str, _user=Depends(_optional_jwt)):
        """Return predictions for a specific date.

        Args:
            date: Date string in YYYY-MM-DD format.

        Returns:
            JSON list of predictions.

        Raises:
            HTTPException: 400 if date format is invalid.
        """
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format; use YYYY-MM-DD")

        predictions = _load_predictions_for_date(date)
        return {"date": date, "predictions": predictions, "count": len(predictions)}
