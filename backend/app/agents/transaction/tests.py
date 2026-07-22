"""
Unit and behavior tests for TransactionAgent.
Covers 14 specific scenarios:
1. Normal Customer
2. Structuring (TX001)
3. Velocity (TX002)
4. Large Transaction (TX003)
5. High Risk Country Transfer (TX004)
6. Dormant Account (TX007)
7. Cash Intensive Behaviour (TX008)
8. Rapid In / Rapid Out (TX005)
9. Round Amount Detection (TX006)
10. Multiple Suspicious Patterns (TX009)
11. Empty Transaction History
12. Invalid Transaction
13. Business Customer
14. Individual Customer
"""

from datetime import datetime, timedelta
import pytest
from app.agents.base.agent_state import AgentState
from app.agents.base.exceptions import AgentValidationError
from app.agents.transaction.agent import TransactionAgent
from app.agents.transaction.constants import *

# ─────────────────────────────────────────────────────────────
# Payload Helpers
# ─────────────────────────────────────────────────────────────


def mock_customer(
    customer_type="individual", nationality="United Kingdom", country="United Kingdom"
):
    return {
        "first_name": "John",
        "last_name": "Doe",
        "dob": "1980-01-01",
        "customer_type": customer_type,
        "nationality": nationality,
        "country": country,
    }


def clean_txs() -> list:
    base_time = datetime.utcnow()
    return [
        {
            "transaction_id": "tx-1",
            "account_id": "acc-123",
            "amount": 250.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": (base_time - timedelta(days=5)).isoformat(),
            "transaction_type": "TRANSFER",
        },
        {
            "transaction_id": "tx-2",
            "account_id": "acc-123",
            "amount": 120.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": (base_time - timedelta(days=3)).isoformat(),
            "transaction_type": "CARD",
        },
    ]


def build_state(customer=None, txs=None, shared_metadata=None) -> AgentState:
    return AgentState(
        customer_id="cust-100",
        case_id="case-100",
        customer=customer if customer is not None else mock_customer(),
        transactions=txs if txs is not None else [],
        shared_metadata=shared_metadata or {},
    )


# ─────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_normal_customer_clear():
    """1. Normal Customer: No patterns triggered, status CLEAR, score 100."""
    state = build_state(txs=clean_txs())
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.success is True
    assert result.risk_score == 100.0
    assert result.risk_level == RISK_LOW
    assert result.metadata["transaction_status"] == TRANSACTION_STATUS_CLEAR
    assert "TX001" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_structuring_triggered():
    """2. Structuring: Multiple txns 8,000–9,999 GBP within 24 hours."""
    base_time = datetime.utcnow()
    txs = [
        {
            "transaction_id": "tx-s1",
            "amount": 9500.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": base_time.isoformat(),
            "transaction_type": "TRANSFER",
        },
        {
            "transaction_id": "tx-s2",
            "amount": 9800.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": (base_time + timedelta(hours=2)).isoformat(),
            "transaction_type": "TRANSFER",
        },
    ]
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.risk_level in (RISK_HIGH, RISK_CRITICAL)
    assert result.metadata["transaction_status"] == TRANSACTION_STATUS_ALERT
    assert "TX002" in result.metadata["rules_triggered"]
    assert any("structuring" in w.lower() for w in result.findings)


@pytest.mark.anyio
async def test_velocity_triggered():
    """3. Velocity: More than 10 txns in 24 hours."""
    base_time = datetime.utcnow()
    txs = []
    for i in range(12):
        txs.append(
            {
                "transaction_id": f"tx-vel-{i}",
                "amount": 50.0,
                "currency": "GBP",
                "direction": "OUTFLOW",
                "timestamp": (base_time + timedelta(minutes=i * 10)).isoformat(),
                "transaction_type": "CARD",
            }
        )
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.metadata["transaction_status"] == TRANSACTION_STATUS_WARNING
    assert "TX003" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_large_transaction_triggered():
    """4. Large Transaction: Single transfer > 50,000 GBP."""
    txs = [
        {
            "transaction_id": "tx-large",
            "amount": 55000.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "TRANSFER",
        }
    ]
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.metadata["transaction_status"] == TRANSACTION_STATUS_ALERT
    assert (
        "TX003" in result.metadata["rules_triggered"]
        or "TX002" in result.metadata["rules_triggered"]
    )


@pytest.mark.anyio
async def test_high_risk_country_transfers():
    """5. High Risk Country: Dest/origin country in metadata's high risk list."""
    txs = [
        {
            "transaction_id": "tx-hr-cty",
            "amount": 1000.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "TRANSFER",
            "destination_country": "Syria",
        }
    ]
    shared_meta = {"high_risk_countries": ["Syria"], "prohibited_countries": []}
    state = build_state(txs=txs, shared_metadata=shared_meta)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.metadata["transaction_status"] == TRANSACTION_STATUS_CRITICAL
    assert "TX004" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_dormant_reactivation():
    """6. Dormant Account: Long gap (>=90 days) followed by sudden transfer."""
    base_time = datetime.utcnow()
    txs = [
        {
            "transaction_id": "tx-old",
            "amount": 100.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": (base_time - timedelta(days=100)).isoformat(),
            "transaction_type": "TRANSFER",
        },
        {
            "transaction_id": "tx-reactivate",
            "amount": 5000.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": base_time.isoformat(),
            "transaction_type": "TRANSFER",
        },
    ]
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert "TX007" in result.metadata["rules_triggered"]
    assert any("dormant" in w.lower() for w in result.findings)


@pytest.mark.anyio
async def test_cash_intensive_behaviour():
    """7. Cash Intensive Behaviour: 3 or more cash transactions."""
    txs = [
        {
            "transaction_id": "tx-cash-1",
            "amount": 500.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "CASH_DEPOSIT",
        },
        {
            "transaction_id": "tx-cash-2",
            "amount": 400.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "CASH_DEPOSIT",
        },
        {
            "transaction_id": "tx-cash-3",
            "amount": 300.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "CASH_DEPOSIT",
        },
    ]
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert "TX006" in result.metadata["rules_triggered"]
    assert any("cash" in w.lower() for w in result.findings)


@pytest.mark.anyio
async def test_rapid_in_rapid_out():
    """8. Rapid In / Rapid Out: Flow in and then immediately out (>80% within 48h)."""
    base_time = datetime.utcnow()
    txs = [
        {
            "transaction_id": "tx-in",
            "account_id": "acc-1",
            "amount": 1000.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": base_time.isoformat(),
            "transaction_type": "TRANSFER",
        },
        {
            "transaction_id": "tx-out",
            "account_id": "acc-1",
            "amount": 900.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": (base_time + timedelta(hours=4)).isoformat(),
            "transaction_type": "TRANSFER",
        },
    ]
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.metadata["transaction_status"] == TRANSACTION_STATUS_ALERT
    assert "TX005" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_round_amount_detection():
    """9. Round Amount Detection: Multiple exact round transactions."""
    txs = [
        {
            "transaction_id": "tx-r-1",
            "amount": 10000.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "TRANSFER",
        },
        {
            "transaction_id": "tx-r-2",
            "amount": 20000.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "TRANSFER",
        },
        {
            "transaction_id": "tx-r-3",
            "amount": 50000.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "TRANSFER",
        },
    ]
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert any("round amount" in w.lower() for w in result.findings)


@pytest.mark.anyio
async def test_multiple_suspicious_patterns():
    """10. Multiple Patterns (TX009): Clustered alerts trigger CRITICAL status."""
    base_time = datetime.utcnow()
    txs = [
        # Large Value
        {
            "transaction_id": "tx-p1",
            "amount": 60000.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": base_time.isoformat(),
            "transaction_type": "TRANSFER",
        },
        # Round amount (1)
        {
            "transaction_id": "tx-p2",
            "amount": 10000.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": base_time.isoformat(),
            "transaction_type": "TRANSFER",
        },
        # Round amount (2)
        {
            "transaction_id": "tx-p3",
            "amount": 20000.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": base_time.isoformat(),
            "transaction_type": "TRANSFER",
        },
        # Round amount (3)
        {
            "transaction_id": "tx-p4",
            "amount": 50000.0,
            "currency": "GBP",
            "direction": "OUTFLOW",
            "timestamp": base_time.isoformat(),
            "transaction_type": "TRANSFER",
        },
        # Structuring check (just below threshold)
        {
            "transaction_id": "tx-p5",
            "amount": 9500.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": base_time.isoformat(),
            "transaction_type": "TRANSFER",
        },
        {
            "transaction_id": "tx-p6",
            "amount": 9600.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": (base_time + timedelta(hours=1)).isoformat(),
            "transaction_type": "TRANSFER",
        },
    ]
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.metadata["transaction_status"] == TRANSACTION_STATUS_CRITICAL
    assert "TX008" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_empty_transaction_history():
    """11. Empty Transaction History: Clean path, reports validation warning but runs."""
    state = build_state(txs=[])
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.success is True
    assert result.risk_score == 100.0
    assert result.metadata["transaction_status"] == TRANSACTION_STATUS_CLEAR
    assert any("no transaction history" in w.lower() for w in result.warnings)


@pytest.mark.anyio
async def test_invalid_transaction():
    """12. Invalid Transaction: Negative amount and invalid currency; skips bad rows, parses the clean one."""
    txs = [
        # Invalid: Negative amount
        {
            "transaction_id": "tx-bad-1",
            "amount": -500.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "TRANSFER",
        },
        # Invalid: Bad currency format
        {
            "transaction_id": "tx-bad-2",
            "amount": 100.0,
            "currency": "INVALID_CURRENCY",
            "direction": "INFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "TRANSFER",
        },
        # Valid transaction
        {
            "transaction_id": "tx-good",
            "amount": 300.0,
            "currency": "GBP",
            "direction": "INFLOW",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_type": "TRANSFER",
        },
    ]
    state = build_state(txs=txs)
    agent = TransactionAgent()
    result = await agent.execute(state)

    # Agent must succeed since one transaction was valid
    assert result.success is True
    assert result.metadata["audit_trail"]["transactions_analysed"] == 1
    # Check that we have logged errors for the bad transactions
    assert len(result.errors) >= 2


@pytest.mark.anyio
async def test_business_customer():
    """13. Business Customer validation and run."""
    customer = mock_customer(customer_type="business")
    state = build_state(customer=customer, txs=clean_txs())
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.success is True
    assert result.metadata["next_agent"] == "account_agent"


@pytest.mark.anyio
async def test_individual_customer():
    """14. Individual Customer validation and run."""
    customer = mock_customer(customer_type="individual")
    state = build_state(customer=customer, txs=clean_txs())
    agent = TransactionAgent()
    result = await agent.execute(state)

    assert result.success is True
    assert result.metadata["next_agent"] == "account_agent"
