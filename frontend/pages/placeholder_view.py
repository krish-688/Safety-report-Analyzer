"""Placeholder views for future stages (Stage 7, 8, 10)."""
import streamlit as st

from api_client import APIClient


def render_investigations_page(client: APIClient, user: dict) -> None:
    st.title("🔍 Investigations & CAPA Workflow")
    st.caption("Root Cause Confirmation, 5-Why Investigation, and Corrective Action Plan (CAPA) tracking.")
    st.info("🚧 **Stage 7 Scope:** This module is planned for Stage 7. It will provide the full 6-step investigation stepper, action owner assignments, Plant Manager approval flow, and overdue deadline notifications.")


def render_alerts_page(client: APIClient, user: dict) -> None:
    st.title("🔔 Alerts & Notifications Engine")
    st.caption("Active safety warnings, threshold breaches, and recurrent cause notifications.")
    st.info("🚧 **Stage 8 Scope:** This module is planned for Stage 8. It monitors recurring equipment failures, high/critical severity triggers, and investigation overdue alerts.")


def render_reports_page(client: APIClient, user: dict) -> None:
    st.title("📑 Safety Reports & Compliance Exports")
    st.caption("Automated PDF incident summaries, regulatory compliance packages, and audit exports.")
    st.info("🚧 **Stage 10 Scope:** This module is planned for Stage 10. It will generate ReportLab PDF reports and regulatory HSE summaries.")
