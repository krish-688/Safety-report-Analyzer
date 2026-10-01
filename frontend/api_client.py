"""REST API Client for the Streamlit thin frontend.

Connects to the FastAPI backend at settings.API_BASE_URL.
Maintains authentication bearer tokens and maps HTTP responses to typed dictionaries.
"""
from typing import Any
import httpx


class APIError(Exception):
    """Raised when an API call returns a non-2xx status code."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error {status_code}: {detail}")


class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1", token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def set_token(self, token: str | None) -> None:
        self.token = token

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        try:
            data = response.json()
        except Exception:
            data = None

        if response.is_success:
            return data

        detail = "An unknown error occurred."
        if isinstance(data, dict):
            detail = data.get("detail", str(data))
        elif response.text:
            detail = response.text

        raise APIError(response.status_code, detail)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        with httpx.Client(base_url=self.base_url, timeout=20.0) as client:
            try:
                res = client.get(path, headers=self._headers(), params=params)
                return self._handle_response(res)
            except httpx.ConnectError:
                raise APIError(503, "Cannot connect to backend server. Ensure FastAPI is running on http://localhost:8000.")

    def _post(self, path: str, json: dict[str, Any] | None = None, files: Any = None) -> Any:
        with httpx.Client(base_url=self.base_url, timeout=20.0) as client:
            try:
                res = client.post(path, headers=self._headers(), json=json, files=files)
                return self._handle_response(res)
            except httpx.ConnectError:
                raise APIError(503, "Cannot connect to backend server. Ensure FastAPI is running on http://localhost:8000.")

    def _patch(self, path: str, json: dict[str, Any] | None = None) -> Any:
        with httpx.Client(base_url=self.base_url, timeout=20.0) as client:
            try:
                res = client.patch(path, headers=self._headers(), json=json)
                return self._handle_response(res)
            except httpx.ConnectError:
                raise APIError(503, "Cannot connect to backend server. Ensure FastAPI is running on http://localhost:8000.")

    def _delete(self, path: str) -> Any:
        with httpx.Client(base_url=self.base_url, timeout=20.0) as client:
            try:
                res = client.delete(path, headers=self._headers())
                return self._handle_response(res)
            except httpx.ConnectError:
                raise APIError(503, "Cannot connect to backend server. Ensure FastAPI is running on http://localhost:8000.")

    def _get_raw(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            try:
                res = client.get(path, headers=self._headers(), params=params)
                if res.is_success:
                    return res.content
                self._handle_response(res)
                return b""
            except httpx.ConnectError:
                raise APIError(503, "Cannot connect to backend server. Ensure FastAPI is running on http://localhost:8000.")

    # --- System & Auth Endpoints -----------------------------------------------------------------

    def get_health(self) -> dict:
        return self._get("/health")

    def get_register_options(self) -> dict:
        return self._get("/auth/register-options")

    def register(
        self,
        name: str,
        email: str,
        password: str,
        requested_role: str,
        preferred_plant_id: int | None = None,
    ) -> dict:
        payload = {
            "name": name,
            "email": email,
            "password": password,
            "requested_role": requested_role,
            "preferred_plant_id": preferred_plant_id,
        }
        return self._post("/auth/register", json=payload)

    def login(self, email: str, password: str) -> dict:
        payload = {"email": email, "password": password}
        data = self._post("/auth/login", json=payload)
        self.set_token(data.get("access_token"))
        return data

    def get_me(self) -> dict:
        return self._get("/auth/me")

    def logout(self) -> dict:
        try:
            res = self._post("/auth/logout")
        finally:
            self.set_token(None)
        return res

    # --- Plants ----------------------------------------------------------------------------------

    def get_plants(self) -> list[dict]:
        return self._get("/plants")

    def get_plant_equipment(self, plant_id: int) -> list[dict]:
        return self._get(f"/plants/{plant_id}/equipment")


    # --- Incidents -------------------------------------------------------------------------------

    def get_incidents(self, params: dict[str, Any] | None = None) -> dict:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get("/incidents", params=clean_params)

    def get_incident(self, incident_id: int) -> dict:
        return self._get(f"/incidents/{incident_id}")

    def create_incident(self, payload: dict[str, Any]) -> dict:
        return self._post("/incidents", json=payload)

    def update_incident(self, incident_id: int, payload: dict[str, Any]) -> dict:
        return self._patch(f"/incidents/{incident_id}", json=payload)

    def delete_incident(self, incident_id: int) -> dict:
        return self._delete(f"/incidents/{incident_id}")

    def export_csv(self, params: dict[str, Any] | None = None) -> bytes:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            res = client.get("/incidents/export-csv", headers=self._headers(), params=clean_params)
            if not res.is_success:
                self._handle_response(res)
            return res.content

    # --- Attachments -----------------------------------------------------------------------------

    def upload_attachment(
        self, incident_id: int, file_bytes: bytes, filename: str, content_type: str | None = None
    ) -> dict:
        files = {"file": (filename, file_bytes, content_type or "application/octet-stream")}
        return self._post(f"/incidents/{incident_id}/attachments", files=files)

    def get_attachments(self, incident_id: int) -> list[dict]:
        return self._get(f"/incidents/{incident_id}/attachments")

    def download_attachment(self, incident_id: int, attachment_id: int) -> bytes:
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            res = client.get(
                f"/incidents/{incident_id}/attachments/{attachment_id}/download",
                headers=self._headers(),
            )
            if not res.is_success:
                self._handle_response(res)
            return res.content

    def delete_attachment(self, incident_id: int, attachment_id: int) -> dict:
        return self._delete(f"/incidents/{incident_id}/attachments/{attachment_id}")

    # --- NLP & Root Causes ------------------------------------------------------------------------

    def analyze_incident(self, incident_id: int, override_text: str | None = None) -> dict:
        payload = {"override_text": override_text} if override_text else {}
        return self._post(f"/incidents/{incident_id}/analyze", json=payload)

    def analyze_text(self, payload: dict[str, Any]) -> dict:
        return self._post("/incidents/analyze-text", json=payload)

    def get_root_causes(self, incident_id: int) -> list[dict]:
        return self._get(f"/incidents/{incident_id}/root-causes")


    def review_root_cause(
        self,
        incident_id: int,
        action: str,
        incident_root_cause_id: int | None = None,
        root_cause_id: int | None = None,
        evidence: str | None = None,
    ) -> list[dict]:
        payload: dict[str, Any] = {"action": action}
        if incident_root_cause_id is not None:
            payload["incident_root_cause_id"] = incident_root_cause_id
        if root_cause_id is not None:
            payload["root_cause_id"] = root_cause_id
        if evidence is not None:
            payload["evidence"] = evidence
        return self._post(f"/incidents/{incident_id}/root-causes", json=payload)

    # --- Admin / User Management ------------------------------------------------------------------

    def list_users(self, params: dict[str, Any] | None = None) -> dict:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get("/users", params=clean_params)

    def get_user(self, user_id: int) -> dict:
        return self._get(f"/users/{user_id}")

    def approve_user(self, user_id: int, role: str, plant_id: int | None = None) -> dict:
        payload = {"role": role, "plant_id": plant_id}
        return self._post(f"/users/{user_id}/approve", json=payload)

    def reject_user(self, user_id: int) -> dict:
        return self._post(f"/users/{user_id}/reject")

    def deactivate_user(self, user_id: int) -> dict:
        return self._post(f"/users/{user_id}/deactivate")

    def activate_user(self, user_id: int) -> dict:
        return self._post(f"/users/{user_id}/activate")

    def reset_password(self, user_id: int, new_password: str) -> dict:
        return self._post(f"/users/{user_id}/reset-password", json={"new_password": new_password})

    def update_user(self, user_id: int, role: str | None = None, plant_id: int | None = None, name: str | None = None) -> dict:
        payload: dict[str, Any] = {}
        if role:
            payload["role"] = role
        if plant_id is not None:
            payload["plant_id"] = plant_id
        if name:
            payload["name"] = name
        return self._patch(f"/users/{user_id}", json=payload)

    # --- Plants & Equipment Admin -----------------------------------------------------------------

    def list_all_plants(self) -> list[dict]:
        return self._get("/plants/all")

    def create_plant(self, name: str, code: str, location: str | None = None, is_active: bool = True) -> dict:
        payload = {"name": name, "code": code, "location": location, "is_active": is_active}
        return self._post("/plants", json=payload)

    def update_plant(self, plant_id: int, payload: dict[str, Any]) -> dict:
        return self._patch(f"/plants/{plant_id}", json=payload)

    def list_equipment(
        self,
        plant_id: int | None = None,
        equipment_type: str | None = None,
        search: str | None = None,
        is_active: bool | None = None,
        limit: int = 200,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if plant_id is not None:
            params["plant_id"] = plant_id
        if equipment_type:
            params["equipment_type"] = equipment_type
        if search:
            params["search"] = search
        if is_active is not None:
            params["is_active"] = is_active
        return self._get("/equipment", params=params)

    def create_equipment(
        self, plant_id: int, tag: str, name: str, equipment_type: str, is_active: bool = True
    ) -> dict:
        payload = {
            "plant_id": plant_id,
            "tag": tag,
            "name": name,
            "equipment_type": equipment_type,
            "is_active": is_active,
        }
        return self._post(f"/plants/{plant_id}/equipment", json=payload)

    def update_equipment(self, equipment_id: int, payload: dict[str, Any]) -> dict:
        return self._patch(f"/equipment/{equipment_id}", json=payload)

    # --- Audit Compliance -------------------------------------------------------------------------

    def list_audit_logs(
        self,
        action: str | None = None,
        entity_type: str | None = None,
        user_id: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if action:
            params["action"] = action
        if entity_type:
            params["entity_type"] = entity_type
        if user_id is not None:
            params["user_id"] = user_id
        return self._get("/audit-logs", params=params)

    # --- Dashboard & Analytics --------------------------------------------------------------------

    def get_dashboard_summary(self, params: dict[str, Any] | None = None) -> dict:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get("/dashboard/summary", params=clean_params)

    def get_monthly_trends(self, params: dict[str, Any] | None = None) -> list[dict]:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get("/dashboard/trends", params=clean_params)

    def get_root_cause_pareto(self, params: dict[str, Any] | None = None) -> list[dict]:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get("/dashboard/pareto-causes", params=clean_params)

    def get_equipment_watchlist(self, params: dict[str, Any] | None = None) -> list[dict]:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get("/dashboard/equipment-watch", params=clean_params)

    def get_plant_distribution(self) -> list[dict]:
        return self._get("/dashboard/plant-distribution")

    # --- Investigations & Corrective Actions (CAPA) -----------------------------------------------

    def get_investigation(self, incident_id: int) -> dict | None:
        return self._get(f"/incidents/{incident_id}/investigation")

    def create_investigation(self, incident_id: int, payload: dict[str, Any]) -> dict:
        return self._post(f"/incidents/{incident_id}/investigation", json=payload)

    def update_investigation(self, incident_id: int, payload: dict[str, Any]) -> dict:
        return self._patch(f"/incidents/{incident_id}/investigation", json=payload)

    def close_investigation(self, incident_id: int) -> dict:
        return self._post(f"/incidents/{incident_id}/investigation/close")

    def get_incident_actions(self, incident_id: int) -> list[dict]:
        return self._get(f"/incidents/{incident_id}/actions")

    def create_action(self, incident_id: int, payload: dict[str, Any]) -> dict:
        return self._post(f"/incidents/{incident_id}/actions", json=payload)

    def list_actions(self, params: dict[str, Any] | None = None) -> list[dict]:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get("/actions", params=clean_params)

    def approve_action(self, action_id: int, approved: bool, comments: str | None = None) -> dict:
        payload = {"approved": approved, "comments": comments}
        return self._post(f"/actions/{action_id}/approve", json=payload)

    def update_action(self, action_id: int, payload: dict[str, Any]) -> dict:
        return self._patch(f"/actions/{action_id}", json=payload)

    # --- Alerts & Notifications -------------------------------------------------------------------

    def list_alerts(self, unread_only: bool = False, limit: int = 50) -> list[dict]:
        return self._get("/alerts", params={"unread_only": unread_only, "limit": limit})

    def get_unread_alerts_count(self) -> int:
        data = self._get("/alerts/unread-count")
        return data.get("unread_count", 0) if data else 0

    def mark_alert_read(self, alert_id: int) -> dict:
        return self._post(f"/alerts/{alert_id}/read")

    def mark_all_alerts_read(self) -> dict:
        return self._post("/alerts/mark-all-read")

    def scan_alerts(self) -> dict:
        return self._post("/alerts/scan")

    def list_thresholds(self) -> list[dict]:
        return self._get("/alerts/thresholds")

    def update_threshold(self, key: str, value: int) -> dict:
        return self._patch(f"/alerts/thresholds/{key}", json={"value": value})

    # --- Reports & Data Exports -------------------------------------------------------------------

    def export_incident_pdf(self, incident_id: int) -> bytes:
        return self._get_raw(f"/incidents/{incident_id}/export-pdf")

    def export_incidents_csv(self, params: dict[str, Any] | None = None) -> bytes:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get_raw("/incidents/export-csv", params=clean_params)

    def export_actions_csv(self, params: dict[str, Any] | None = None) -> bytes:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        return self._get_raw("/actions/export-csv", params=clean_params)


