#!/usr/bin/env python3
"""
Multi-Market Investment Accounting & Portfolio Management Engine
----------------------------------------------------------------
Supports VFEX, ZSE, and C-TRADE independently with a consolidated reporting view.
Zero external dependencies (Python stdlib only).

Cost-Basis Method:
    FIFO (First-In, First-Out) per unique (account_id, exchange, security_id).
    Acquisition fees/taxes are capitalized into lot cost basis; disposal
    fees/taxes reduce net proceeds and realized gain/loss.

Multi-Currency Policy:
    Every transaction and cash balance is tracked in its native currency
    (e.g., USD, ZWG). Currencies are NEVER silently summed. Consolidated
    reporting converts each currency explicitly using dated FX rates and
    separates price return, FX return, income return, and fee drag.

Reconciliation Immutability:
    Transactions marked status='RECONCILED' cannot be silently modified or
    deleted; corrections must be recorded as explicit ADJUSTMENT transactions.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Any

VALID_EXCHANGES = {"VFEX", "ZSE", "CTRADE", "FINSEC", "OTHER"}
VALID_TX_TYPES = {
    "BUY",
    "SELL",
    "DEPOSIT",
    "WITHDRAWAL",
    "DIVIDEND",
    "FEE",
    "TAX",
    "CORPORATE_ACTION",
    "SPLIT",
    "RIGHTS_ISSUE",
    "ADJUSTMENT",
    "TRANSFER_IN",
    "TRANSFER_OUT",
}
VALID_RECON_STATUS = {"UNRECONCILED", "RECONCILED", "DISCREPANCY"}
VALID_DIV_STATUS = {"DECLARED", "EXPECTED", "RECEIVED"}


def make_security_id(exchange: str, symbol: str, isin: str = "") -> str:
    """Create a globally unique security identifier scoped to exchange (never conflating symbols across markets)."""
    ex = str(exchange or "VFEX").strip().upper()
    sym = str(symbol or "").strip().upper()
    if isin and str(isin).strip():
        return f"{ex}:{sym}:{str(isin).strip().upper()}"
    return f"{ex}:{sym}"


def _parse_date(raw: str | date | datetime | None) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw or "").strip()[:10]
    return date.fromisoformat(s)


@dataclass
class Account:
    account_id: str
    name: str
    exchange: str  # VFEX, ZSE, CTRADE
    broker: str = ""
    base_currency: str = "USD"
    cds_number: str = ""


@dataclass
class Security:
    security_id: str  # e.g. VFEX:INFR or ZSE:DLTA
    exchange: str
    symbol: str
    name: str = ""
    currency: str = "USD"
    isin: str = ""
    sector: str = "Unclassified"


@dataclass
class Transaction:
    transaction_date: str  # YYYY-MM-DD
    tx_type: str  # VALID_TX_TYPES
    exchange: str
    account_id: str
    currency: str
    quantity: float = 0.0
    unit_price: float = 0.0
    fees: float = 0.0
    taxes: float = 0.0
    total_amount: float | None = None
    security_id: str = ""
    symbol: str = ""
    settlement_date: str = ""
    reference: str = ""
    data_source: str = "manual"  # manual | portal_sync | contract_note | statement
    reconciliation_status: str = "UNRECONCILED"
    fx_rate_to_reporting: float | None = None  # 1 unit of `currency` in reporting currency
    notes: str = ""
    transaction_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def __post_init__(self) -> None:
        self.tx_type = self.tx_type.strip().upper()
        self.exchange = self.exchange.strip().upper()
        self.currency = self.currency.strip().upper()
        if self.tx_type not in VALID_TX_TYPES:
            raise ValueError(f"Unsupported transaction type: {self.tx_type}")
        if self.reconciliation_status not in VALID_RECON_STATUS:
            raise ValueError(f"Invalid reconciliation_status: {self.reconciliation_status}")
        if self.symbol and not self.security_id:
            self.security_id = make_security_id(self.exchange, self.symbol)
        if not self.settlement_date:
            self.settlement_date = self.transaction_date
        if self.total_amount is None:
            gross = abs(float(self.quantity)) * float(self.unit_price)
            if self.tx_type in ("BUY", "RIGHTS_ISSUE"):
                self.total_amount = round(gross + float(self.fees) + float(self.taxes), 6)
            elif self.tx_type == "SELL":
                self.total_amount = round(max(0.0, gross - float(self.fees) - float(self.taxes)), 6)
            else:
                self.total_amount = round(gross, 6)


@dataclass
class DividendRecord:
    security_id: str
    exchange: str
    symbol: str
    currency: str
    declaration_date: str
    ex_dividend_date: str
    record_date: str
    payment_date: str
    gross_amount: float
    withholding_tax: float = 0.0
    status: str = "DECLARED"  # DECLARED | EXPECTED | RECEIVED
    account_id: str = "default"
    reference: str = ""
    dividend_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    @property
    def net_amount(self) -> float:
        return round(max(0.0, float(self.gross_amount) - float(self.withholding_tax)), 6)


@dataclass
class FxRate:
    """Dated FX rate: 1 unit of `from_currency` = `rate` units of `to_currency`."""
    rate_date: str
    from_currency: str
    to_currency: str
    rate: float
    source: str = "manual"


@dataclass
class Lot:
    acquired_date: str
    quantity: float
    unit_cost_native: float  # includes capitalized buy fees/taxes per share
    fx_rate_at_acquisition: float  # native -> reporting currency
    reference: str = ""


class PortfolioAccountingEngine:
    """
    Independent, deterministic FIFO multi-market, multi-currency accounting engine.
    """

    def __init__(self, reporting_currency: str = "USD") -> None:
        self.reporting_currency = reporting_currency.strip().upper()
        self.accounts: dict[str, Account] = {}
        self.securities: dict[str, Security] = {}
        self.transactions: list[Transaction] = []
        self.dividends: list[DividendRecord] = []
        self.fx_rates: list[FxRate] = []

    # ── Registration & Immutability Guards ───────────────────────────────────

    def add_account(self, account: Account) -> None:
        self.accounts[account.account_id] = account

    def add_security(self, sec: Security) -> None:
        self.securities[sec.security_id] = sec

    def add_fx_rate(self, rate_date: str, from_currency: str, to_currency: str, rate: float, source: str = "manual") -> None:
        if rate <= 0:
            raise ValueError("FX rate must be positive.")
        self.fx_rates.append(FxRate(
            rate_date=str(rate_date)[:10],
            from_currency=from_currency.strip().upper(),
            to_currency=to_currency.strip().upper(),
            rate=float(rate),
            source=source,
        ))
        self.fx_rates.sort(key=lambda r: r.rate_date)

    def get_fx_rate(self, from_currency: str, to_currency: str, as_of_date: str | None = None) -> float:
        fc = from_currency.strip().upper()
        tc = to_currency.strip().upper()
        if fc == tc:
            return 1.0
        target_d = _parse_date(as_of_date) if as_of_date else date.today()
        # Direct or inverse lookup on or before as_of_date
        best_direct: FxRate | None = None
        best_inverse: FxRate | None = None
        for r in self.fx_rates:
            rd = _parse_date(r.rate_date)
            if rd > target_d:
                continue
            if r.from_currency == fc and r.to_currency == tc:
                best_direct = r
            elif r.from_currency == tc and r.to_currency == fc:
                best_inverse = r
        if best_direct is not None:
            return best_direct.rate
        if best_inverse is not None and best_inverse.rate > 0:
            return 1.0 / best_inverse.rate
        raise ValueError(f"No FX rate available for {fc}->{tc} on or before {target_d.isoformat()}")

    def add_transaction(self, tx: Transaction) -> Transaction:
        self.transactions.append(tx)
        self.transactions.sort(key=lambda t: (t.transaction_date, t.transaction_id))
        return tx

    def update_transaction(self, transaction_id: str, **updates: Any) -> Transaction:
        for tx in self.transactions:
            if tx.transaction_id == transaction_id:
                if tx.reconciliation_status == "RECONCILED":
                    raise ValueError(
                        f"Cannot modify RECONCILED transaction {transaction_id}. "
                        "Record an explicit ADJUSTMENT transaction instead."
                    )
                for k, v in updates.items():
                    if hasattr(tx, k):
                        setattr(tx, k, v)
                return tx
        raise KeyError(f"Transaction {transaction_id} not found.")

    def mark_reconciled(self, transaction_id: str) -> None:
        for tx in self.transactions:
            if tx.transaction_id == transaction_id:
                tx.reconciliation_status = "RECONCILED"
                return
        raise KeyError(f"Transaction {transaction_id} not found.")

    def add_dividend(self, div: DividendRecord) -> DividendRecord:
        if div.status not in VALID_DIV_STATUS:
            raise ValueError(f"Invalid dividend status: {div.status}")
        self.dividends.append(div)
        return div

    # ── Core FIFO Valuation & Multi-Currency Accounting ──────────────────────

    def compute_portfolio(
        self,
        market_prices: dict[str, float],
        as_of_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Replay all transactions chronologically up to `as_of_date` using FIFO.
        Returns per-position, per-currency, per-exchange, and consolidated reporting metrics.
        `market_prices` is keyed by `security_id` (e.g. 'VFEX:INFR': 0.25, 'ZSE:DLTA': 12.50).
        """
        cutoff = _parse_date(as_of_date) if as_of_date else date.max
        eval_date_str = as_of_date or date.today().isoformat()

        # State keyed by (account_id, security_id)
        lots_map: dict[tuple[str, str], list[Lot]] = {}
        sec_meta: dict[str, dict[str, str]] = {}
        # Cash keyed by (account_id, currency)
        cash_map: dict[tuple[str, str], float] = {}

        # Per-currency accumulators (never silently mixed)
        by_currency: dict[str, dict[str, float]] = {}

        def _cur_bucket(cur: str) -> dict[str, float]:
            return by_currency.setdefault(cur, {
                "cash": 0.0,
                "market_value": 0.0,
                "cost_basis": 0.0,
                "unrealised_pnl": 0.0,
                "realised_pnl": 0.0,
                "dividend_income": 0.0,
                "fees_paid": 0.0,
                "taxes_paid": 0.0,
                "deposits": 0.0,
                "withdrawals": 0.0,
                "net_deposits": 0.0,
            })

        realised_price_rep = 0.0
        realised_fx_rep = 0.0
        fees_rep = 0.0
        taxes_rep = 0.0
        dividends_rep = 0.0
        deposits_rep = 0.0
        withdrawals_rep = 0.0
        div_by_sec: dict[str, float] = {}

        for tx in self.transactions:
            if _parse_date(tx.transaction_date) > cutoff:
                continue
            cur = tx.currency
            cb = _cur_bucket(cur)
            ckey = (tx.account_id, cur)
            cash_map.setdefault(ckey, 0.0)
            fx_tx = tx.fx_rate_to_reporting if tx.fx_rate_to_reporting is not None else self.get_fx_rate(cur, self.reporting_currency, tx.transaction_date)

            cb["fees_paid"] += tx.fees
            cb["taxes_paid"] += tx.taxes
            fees_rep += tx.fees * fx_tx
            taxes_rep += tx.taxes * fx_tx

            if tx.security_id:
                sec_meta.setdefault(tx.security_id, {
                    "exchange": tx.exchange,
                    "symbol": tx.symbol or tx.security_id.split(":")[-1],
                    "currency": cur,
                })

            if tx.tx_type == "DEPOSIT":
                amt = float(tx.total_amount or 0.0)
                cash_map[ckey] += amt - tx.fees - tx.taxes
                cb["deposits"] += amt
                deposits_rep += amt * fx_tx

            elif tx.tx_type == "WITHDRAWAL":
                amt = float(tx.total_amount or 0.0)
                cash_map[ckey] -= (amt + tx.fees + tx.taxes)
                cb["withdrawals"] += amt
                withdrawals_rep += amt * fx_tx

            elif tx.tx_type in ("BUY", "RIGHTS_ISSUE"):
                qty = float(tx.quantity)
                total_cost = qty * float(tx.unit_price) + float(tx.fees) + float(tx.taxes)
                unit_cost = total_cost / qty if qty > 0 else 0.0
                lots_map.setdefault((tx.account_id, tx.security_id), []).append(
                    Lot(tx.transaction_date, qty, unit_cost, fx_tx, tx.reference)
                )
                cash_map[ckey] -= total_cost

            elif tx.tx_type == "TRANSFER_IN":
                qty = float(tx.quantity)
                unit_cost = float(tx.unit_price)
                lots_map.setdefault((tx.account_id, tx.security_id), []).append(
                    Lot(tx.transaction_date, qty, unit_cost, fx_tx, tx.reference)
                )

            elif tx.tx_type == "TRANSFER_OUT":
                qty_rem = float(tx.quantity)
                lots = lots_map.get((tx.account_id, tx.security_id), [])
                new_lots: list[Lot] = []
                for lot in lots:
                    if qty_rem <= 1e-9:
                        new_lots.append(lot)
                    elif lot.quantity <= qty_rem + 1e-9:
                        qty_rem -= lot.quantity
                    else:
                        new_lots.append(Lot(lot.acquired_date, lot.quantity - qty_rem, lot.unit_cost_native, lot.fx_rate_at_acquisition, lot.reference))
                        qty_rem = 0.0
                lots_map[(tx.account_id, tx.security_id)] = new_lots

            elif tx.tx_type == "SELL":
                qty_to_sell = float(tx.quantity)
                lots = lots_map.get((tx.account_id, tx.security_id), [])
                avail = sum(l.quantity for l in lots)
                if avail + 1e-9 < qty_to_sell:
                    raise ValueError(f"Insufficient shares of {tx.security_id} in {tx.account_id} to sell {qty_to_sell} (have {avail})")
                gross_proceeds = qty_to_sell * float(tx.unit_price)
                net_proceeds = gross_proceeds - float(tx.fees) - float(tx.taxes)
                cash_map[ckey] += net_proceeds

                cost_native = 0.0
                cost_rep_at_acq = 0.0
                new_lots = []
                rem = qty_to_sell
                for lot in lots:
                    if rem <= 1e-9:
                        new_lots.append(lot)
                    elif lot.quantity <= rem + 1e-9:
                        cost_native += lot.quantity * lot.unit_cost_native
                        cost_rep_at_acq += lot.quantity * lot.unit_cost_native * lot.fx_rate_at_acquisition
                        rem -= lot.quantity
                    else:
                        cost_native += rem * lot.unit_cost_native
                        cost_rep_at_acq += rem * lot.unit_cost_native * lot.fx_rate_at_acquisition
                        new_lots.append(Lot(lot.acquired_date, lot.quantity - rem, lot.unit_cost_native, lot.fx_rate_at_acquisition, lot.reference))
                        rem = 0.0
                lots_map[(tx.account_id, tx.security_id)] = new_lots

                realised_native = net_proceeds - cost_native
                cb["realised_pnl"] += realised_native
                # Decompose reporting-currency realized gain into Price Return vs FX Return
                realised_price_rep += realised_native * fx_tx
                realised_fx_rep += cost_native * (fx_tx - (cost_rep_at_acq / cost_native if cost_native > 0 else fx_tx))

            elif tx.tx_type == "SPLIT":
                # quantity holds split ratio (e.g. 2.0 for 2-for-1 split, 0.5 for 1-for-2 reverse split)
                ratio = float(tx.quantity)
                if ratio <= 0:
                    raise ValueError("Split ratio must be positive.")
                for lot in lots_map.get((tx.account_id, tx.security_id), []):
                    lot.quantity *= ratio
                    lot.unit_cost_native /= ratio

            elif tx.tx_type == "DIVIDEND":
                net_div = float(tx.total_amount or 0.0) - float(tx.fees) - float(tx.taxes)
                cash_map[ckey] += net_div
                cb["dividend_income"] += net_div
                dividends_rep += net_div * fx_tx
                if tx.security_id:
                    div_by_sec[tx.security_id] = div_by_sec.get(tx.security_id, 0.0) + net_div * fx_tx

            elif tx.tx_type in ("FEE", "TAX"):
                amt = float(tx.total_amount or 0.0) + float(tx.fees) + float(tx.taxes)
                cash_map[ckey] -= amt

            elif tx.tx_type == "ADJUSTMENT":
                cash_map[ckey] += float(tx.total_amount or 0.0)

        # Roll up open positions
        positions: list[dict[str, Any]] = []
        total_mv_rep = 0.0
        total_cost_rep = 0.0
        unrealised_price_rep = 0.0
        unrealised_fx_rep = 0.0

        for (acct_id, sec_id), lots in lots_map.items():
            qty = sum(l.quantity for l in lots)
            if qty <= 1e-9:
                continue
            meta = sec_meta.get(sec_id, {"exchange": "VFEX", "symbol": sec_id, "currency": "USD"})
            sec_obj = self.securities.get(sec_id)
            cur = sec_obj.currency if sec_obj else meta["currency"]
            exch = sec_obj.exchange if sec_obj else meta["exchange"]
            sym = sec_obj.symbol if sec_obj else meta["symbol"]
            sector = sec_obj.sector if sec_obj else "Unclassified"

            cost_native = sum(l.quantity * l.unit_cost_native for l in lots)
            avg_cost_native = cost_native / qty
            cost_rep_hist = sum(l.quantity * l.unit_cost_native * l.fx_rate_at_acquisition for l in lots)

            px_native = float(market_prices.get(sec_id, avg_cost_native))
            mv_native = qty * px_native
            unr_native = mv_native - cost_native

            fx_now = self.get_fx_rate(cur, self.reporting_currency, eval_date_str)
            mv_rep = mv_native * fx_now
            unr_price_rep = unr_native * fx_now
            unr_fx_rep = (mv_rep - cost_rep_hist) - unr_price_rep

            cb = _cur_bucket(cur)
            cb["market_value"] += mv_native
            cb["cost_basis"] += cost_native
            cb["unrealised_pnl"] += unr_native

            total_mv_rep += mv_rep
            total_cost_rep += cost_rep_hist
            unrealised_price_rep += unr_price_rep
            unrealised_fx_rep += unr_fx_rep

            positions.append({
                "account_id": acct_id,
                "security_id": sec_id,
                "exchange": exch,
                "symbol": sym,
                "sector": sector,
                "currency": cur,
                "quantity": round(qty, 6),
                "avg_cost_native": round(avg_cost_native, 6),
                "cost_basis_native": round(cost_native, 4),
                "market_price_native": round(px_native, 6),
                "market_value_native": round(mv_native, 4),
                "unrealised_pnl_native": round(unr_native, 4),
                "unrealised_pnl_pct": round((unr_native / cost_native) * 100.0, 2) if cost_native > 0 else 0.0,
                "market_value_reporting": round(mv_rep, 4),
                "cost_basis_reporting": round(cost_rep_hist, 4),
                "unrealised_price_reporting": round(unr_price_rep, 4),
                "unrealised_fx_reporting": round(unr_fx_rep, 4),
                "dividend_income_reporting": round(div_by_sec.get(sec_id, 0.0), 4),
            })

        # Roll up cash balances
        total_cash_rep = 0.0
        cash_balances: list[dict[str, Any]] = []
        for (acct_id, cur), bal in cash_map.items():
            fx_now = self.get_fx_rate(cur, self.reporting_currency, eval_date_str)
            bal_rep = bal * fx_now
            total_cash_rep += bal_rep
            _cur_bucket(cur)["cash"] += bal
            cash_balances.append({
                "account_id": acct_id,
                "currency": cur,
                "balance_native": round(bal, 4),
                "balance_reporting": round(bal_rep, 4),
            })

        for cur, b in by_currency.items():
            b["net_deposits"] = round(b["deposits"] - b["withdrawals"], 4)
            for k in list(b.keys()):
                b[k] = round(b[k], 4)

        total_equity_rep = total_mv_rep + total_cash_rep
        for p in positions:
            p["allocation_pct"] = round((p["market_value_reporting"] / total_equity_rep) * 100.0, 2) if total_equity_rep > 0 else 0.0

        total_price_return = realised_price_rep + unrealised_price_rep
        total_fx_return = realised_fx_rep + unrealised_fx_rep
        total_return_rep = total_price_return + total_fx_return + dividends_rep

        return {
            "as_of_date": eval_date_str,
            "reporting_currency": self.reporting_currency,
            "cost_basis_method": "FIFO",
            "positions": positions,
            "cash_balances": cash_balances,
            "by_currency": by_currency,
            "consolidated": {
                "total_equity": round(total_equity_rep, 4),
                "market_value": round(total_mv_rep, 4),
                "total_cash": round(total_cash_rep, 4),
                "cost_basis": round(total_cost_rep, 4),
                "unrealised_price_pnl": round(unrealised_price_rep, 4),
                "unrealised_fx_pnl": round(unrealised_fx_rep, 4),
                "realised_price_pnl": round(realised_price_rep, 4),
                "realised_fx_pnl": round(realised_fx_rep, 4),
                "dividend_income": round(dividends_rep, 4),
                "fees_paid": round(fees_rep, 4),
                "taxes_paid": round(taxes_rep, 4),
                "net_deposits": round(deposits_rep - withdrawals_rep, 4),
                "price_return": round(total_price_return, 4),
                "fx_return": round(total_fx_return, 4),
                "total_return": round(total_return_rep, 4),
            },
        }

    # ── Performance Analytics (TWR & XIRR & Period Returns) ──────────────────

    @staticmethod
    def compute_twr(valuation_series: list[dict[str, float]]) -> float | None:
        """
        Compute Time-Weighted Return (TWR %) from ordered sub-period observations:
        [{"start_value": V0, "end_value": V1, "net_cashflow": CF}, ...]
        Sub-period return r_i = (V1 - CF - V0) / V0 (assuming CF at period end)
        """
        if not valuation_series:
            return None
        acc = 1.0
        valid = 0
        for row in valuation_series:
            v0 = float(row.get("start_value") or 0.0)
            v1 = float(row.get("end_value") or 0.0)
            cf = float(row.get("net_cashflow") or 0.0)
            if v0 <= 0:
                continue
            r = (v1 - cf - v0) / v0
            acc *= (1.0 + r)
            valid += 1
        return round((acc - 1.0) * 100.0, 2) if valid > 0 else None

    @staticmethod
    def compute_xirr(cashflows: list[tuple[date, float]]) -> float | None:
        """Money-weighted annualized return (XIRR %) via Newton-Raphson."""
        if len(cashflows) < 2:
            return None
        has_neg = any(cf < 0 for _, cf in cashflows)
        has_pos = any(cf > 0 for _, cf in cashflows)
        if not (has_neg and has_pos):
            return None
        t0 = min(d for d, _ in cashflows)

        def npv(r: float) -> float:
            return sum(cf / ((1.0 + r) ** ((d - t0).days / 365.0)) for d, cf in cashflows)

        rate = 0.10
        for _ in range(80):
            f = npv(rate)
            if abs(f) < 1e-7:
                return round(rate * 100.0, 2)
            df = (npv(rate + 1e-5) - f) / 1e-5
            if abs(df) < 1e-12:
                break
            nxt = max(-0.95, min(10.0, rate - f / df))
            if abs(nxt - rate) < 1e-7:
                return round(nxt * 100.0, 2)
            rate = nxt
        return None

    # ── Dividend Summary (Declared vs Expected vs Received) ──────────────────

    def dividend_summary(self, market_prices: dict[str, float] | None = None) -> dict[str, Any]:
        buckets = {"DECLARED": 0.0, "EXPECTED": 0.0, "RECEIVED": 0.0}
        by_cur: dict[str, dict[str, float]] = {}
        for d in self.dividends:
            fx = self.get_fx_rate(d.currency, self.reporting_currency, d.payment_date or d.declaration_date)
            net_rep = d.net_amount * fx
            buckets[d.status] = round(buckets.get(d.status, 0.0) + net_rep, 4)
            c_map = by_cur.setdefault(d.currency, {"DECLARED": 0.0, "EXPECTED": 0.0, "RECEIVED": 0.0})
            c_map[d.status] = round(c_map[d.status] + d.net_amount, 4)
        return {
            "reporting_currency": self.reporting_currency,
            "declared_reporting": buckets["DECLARED"],
            "expected_reporting": buckets["EXPECTED"],
            "received_reporting": buckets["RECEIVED"],
            "by_currency": by_cur,
            "records": [asdict(d) for d in self.dividends],
        }

    # ── Portfolio Reconciliation ─────────────────────────────────────────────

    def reconcile_against_statement(
        self,
        external_holdings: dict[tuple[str, str], float],
        external_cash: dict[tuple[str, str], float],
        market_prices: dict[str, float],
        qty_tolerance: float = 1e-4,
        cash_tolerance: float = 0.02,
    ) -> dict[str, Any]:
        """
        Compare internal FIFO holdings & cash against external brokerage/portal statement.
        Never mutates reconciled records; returns structured discrepancy report.
        """
        snap = self.compute_portfolio(market_prices)
        internal_pos = {(p["account_id"], p["security_id"]): p["quantity"] for p in snap["positions"]}
        internal_cash = {(c["account_id"], c["currency"]): c["balance_native"] for c in snap["cash_balances"]}

        discrepancies: list[dict[str, Any]] = []
        for key in sorted(set(internal_pos.keys()) | set(external_holdings.keys())):
            iq = internal_pos.get(key, 0.0)
            eq = external_holdings.get(key, 0.0)
            if abs(iq - eq) > qty_tolerance:
                discrepancies.append({
                    "kind": "QUANTITY_MISMATCH",
                    "account_id": key[0],
                    "security_id": key[1],
                    "internal_qty": round(iq, 6),
                    "external_qty": round(eq, 6),
                    "delta": round(eq - iq, 6),
                })

        for key in sorted(set(internal_cash.keys()) | set(external_cash.keys())):
            ic = internal_cash.get(key, 0.0)
            ec = external_cash.get(key, 0.0)
            if abs(ic - ec) > cash_tolerance:
                discrepancies.append({
                    "kind": "CASH_MISMATCH",
                    "account_id": key[0],
                    "currency": key[1],
                    "internal_cash": round(ic, 4),
                    "external_cash": round(ec, 4),
                    "delta": round(ec - ic, 4),
                })

        return {
            "reconciled": len(discrepancies) == 0,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
        }

    # ── Portfolio Insights & Attribution ─────────────────────────────────────

    def generate_insights(self, market_prices: dict[str, float], concentration_limit_pct: float = 25.0) -> dict[str, Any]:
        snap = self.compute_portfolio(market_prices)
        pos = snap["positions"]
        sorted_perf = sorted(pos, key=lambda p: p["unrealised_pnl_pct"], reverse=True)

        exchange_alloc: dict[str, float] = {}
        sector_alloc: dict[str, float] = {}
        currency_alloc: dict[str, float] = {}
        concentration_risks: list[dict[str, Any]] = []

        eq = snap["consolidated"]["total_equity"]
        for p in pos:
            exchange_alloc[p["exchange"]] = round(exchange_alloc.get(p["exchange"], 0.0) + p["allocation_pct"], 2)
            sector_alloc[p["sector"]] = round(sector_alloc.get(p["sector"], 0.0) + p["allocation_pct"], 2)
            currency_alloc[p["currency"]] = round(currency_alloc.get(p["currency"], 0.0) + p["allocation_pct"], 2)
            if p["allocation_pct"] > concentration_limit_pct:
                concentration_risks.append({
                    "security_id": p["security_id"],
                    "allocation_pct": p["allocation_pct"],
                    "limit_pct": concentration_limit_pct,
                })

        cash_alloc_pct = round((snap["consolidated"]["total_cash"] / eq) * 100.0, 2) if eq > 0 else 0.0
        return {
            "strongest_holdings": sorted_perf[:3],
            "weakest_holdings": list(reversed(sorted_perf[-3:])) if sorted_perf else [],
            "concentration_risks": concentration_risks,
            "exchange_allocation_pct": exchange_alloc,
            "sector_allocation_pct": sector_alloc,
            "currency_exposure_pct": currency_alloc,
            "cash_allocation_pct": cash_alloc_pct,
            "attribution": {
                "price_return": snap["consolidated"]["price_return"],
                "fx_return": snap["consolidated"]["fx_return"],
                "dividend_income": snap["consolidated"]["dividend_income"],
                "fees_and_taxes": round(snap["consolidated"]["fees_paid"] + snap["consolidated"]["taxes_paid"], 4),
            },
        }
