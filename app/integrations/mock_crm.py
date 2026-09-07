"""Mock CRM connector with realistic Kuwaiti corporate client data.

Used when INTEGRATION_MODE=mock. Provides deterministic, realistic
data for development and testing without connecting to a real CRM.
"""

from __future__ import annotations

from datetime import date
from typing import List

from app.integrations.base import CRMConnector, ClientProfile

# Realistic Kuwaiti corporate client profiles
_CLIENTS = {
    "CORP-001": ClientProfile(
        client_id="CORP-001",
        legal_name="Al-Babtain Real Estate & Development Co. KSC",
        trade_name="Al-Babtain RED",
        client_type="corporate",
        sector="Real Estate",
        sub_sector="Property Development",
        country="KW",
        risk_rating="BBB+",
        relationship_start_date=date(2018, 3, 15),
        rm_name="Ahmad Al-Sabah",
        rm_email="a.sabah@warbabank.com.kw",
        group_name="Al-Babtain Group",
    ),
    "CORP-002": ClientProfile(
        client_id="CORP-002",
        legal_name="Kuwait Industrial Holding Co. KSCC",
        trade_name="KIH",
        client_type="corporate",
        sector="Industrial",
        sub_sector="Manufacturing",
        country="KW",
        risk_rating="A-",
        relationship_start_date=date(2016, 7, 1),
        rm_name="Fatima Al-Kandari",
        rm_email="f.kandari@warbabank.com.kw",
        group_name="KIH Group",
    ),
    "CORP-003": ClientProfile(
        client_id="CORP-003",
        legal_name="Gulf Trading & Contracting Co. WLL",
        trade_name="GTC",
        client_type="corporate",
        sector="Construction",
        sub_sector="General Contracting",
        country="KW",
        risk_rating="BB+",
        relationship_start_date=date(2020, 1, 10),
        rm_name="Mohammed Al-Otaibi",
        rm_email="m.otaibi@warbabank.com.kw",
        group_name="",
    ),
    "SME-001": ClientProfile(
        client_id="SME-001",
        legal_name="Al-Noor Retail & Trading Co. WLL",
        trade_name="Al-Noor Retail",
        client_type="sme",
        sector="Retail",
        sub_sector="General Trading",
        country="KW",
        risk_rating="BB",
        relationship_start_date=date(2021, 6, 1),
        rm_name="Sara Al-Mutairi",
        rm_email="s.mutairi@warbabank.com.kw",
        group_name="",
    ),
}


class MockCRMConnector(CRMConnector):
    """Mock CRM connector returning deterministic sample data."""

    def get_client_profile(self, client_id: str) -> ClientProfile:
        if client_id in _CLIENTS:
            return _CLIENTS[client_id]
        # Return a synthetic profile for unknown IDs
        return ClientProfile(
            client_id=client_id,
            legal_name=f"Client {client_id}",
            trade_name=f"Client {client_id}",
            client_type="corporate",
            sector="Diversified",
            sub_sector="General",
            country="KW",
            risk_rating="BBB",
            relationship_start_date=date(2019, 1, 1),
            rm_name="Unknown RM",
            rm_email="rm@warbabank.com.kw",
        )

    def search_clients(self, query: str, limit: int = 20) -> List[ClientProfile]:
        query_lower = query.lower()
        results = []
        for profile in _CLIENTS.values():
            if (
                query_lower in profile.legal_name.lower()
                or query_lower in profile.client_id.lower()
                or query_lower in profile.sector.lower()
            ):
                results.append(profile)
                if len(results) >= limit:
                    break
        return results
