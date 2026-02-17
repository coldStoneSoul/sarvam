import math
from typing import Dict, Optional, Any
from datetime import datetime
import os
from openai import OpenAI


class MSMESettlementEngine:
    """
    Compliance-Grade MSME Settlement Draft Generator
    - Section 15 trigger logic
    - Section 16 monthly compound interest (3x RBI bank rate)
    - Deterministic settlement modeling
    - Probability normalized (0–1)
    - Optional LLM polish (isolated)
    """

    def __init__(self, rbi_bank_rate: float = 0.085,
                 api_key: Optional[str] = None,
                 model: str = "ai/granite-4.0-micro",
                 base_url: Optional[str] = None):

        # RBI bank rate (e.g., 8.5% = 0.085)
        self.rbi_bank_rate = rbi_bank_rate
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or "not-needed"
        self.model = model
        self.base_url = base_url or os.getenv("MODEL_RUNNER_URL", "http://localhost:12434/v1")

        try:
            self.llm_client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except Exception:
            self.llm_client = None

    # =====================================================
    # MAIN ENTRY
    # =====================================================

    def generate(self,
                 case_data: Dict[str, Any],
                 prediction_data: Dict[str, Any],
                 final_offer: Optional[int] = None) -> Dict:

        claim = self._clean_amount(case_data.get("claim_amount"))
        delay_days = self._clean_amount(case_data.get("delay_days"))
        agreed_days = case_data.get("agreed_payment_days")
        probability = self._normalize_probability(
            prediction_data.get("probability", 0)
        )

        statutory = self._calculate_statutory_entitlement(
            claim, delay_days, agreed_days
        )

        settlement_amount = final_offer or self._compute_settlement_amount(
            statutory["total"],
            probability
        )

        draft = self._build_structured_draft(
            case_data,
            statutory,
            settlement_amount,
            probability
        )

        return {
            "success": True,
            "settlement_amount": settlement_amount,
            "statutory_entitlement": statutory["total"],
            "interest_component": statutory["interest"],
            "annual_interest_rate": statutory["annual_rate_percent"],
            "concession_value": statutory["total"] - settlement_amount,
            "structured_draft": draft,
            "full_text": self._compile_text(draft)
        }

    # =====================================================
    # CLEANERS
    # =====================================================

    def _clean_amount(self, value) -> int:
        if value is None:
            return 0
        if isinstance(value, str):
            val = value.replace(",", "").replace("₹", "").strip()
            if not val:
                return 0
            try:
                return int(float(val))
            except ValueError:
                return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def _normalize_probability(self, prob) -> float:
        """
        Accepts:
        - 0–1
        - 0–100
        - string
        Returns normalized 0–1 float
        """
        try:
            prob = float(str(prob).replace(",", ""))
        except:
            return 0.0

        if prob > 1:
            prob = prob / 100

        return max(0.0, min(prob, 1.0))

    # =====================================================
    # STATUTORY CALCULATION (Section 15 & 16)
    # =====================================================

    def _calculate_statutory_entitlement(self,
                                         principal: int,
                                         delay_days: int,
                                         agreed_days: Optional[int]) -> Dict:

        # Section 15 trigger
        if agreed_days:
            trigger_days = min(int(agreed_days), 45)
        else:
            trigger_days = 15

        if delay_days <= trigger_days:
            return {
                "principal": principal,
                "interest": 0.0,
                "total": principal,
                "annual_rate_percent": 0.0,
                "section_15_triggered": False,
                "section_16_applied": False
            }

        # Section 16 → 3 × RBI rate
        annual_rate = 3 * self.rbi_bank_rate
        monthly_rate = annual_rate / 12

        months = delay_days / 30
        compound_factor = (1 + monthly_rate) ** months

        interest = principal * (compound_factor - 1)
        total = principal + interest

        return {
            "principal": principal,
            "interest": round(interest, 2),
            "total": round(total, 2),
            "annual_rate_percent": round(annual_rate * 100, 2),
            "section_15_triggered": True,
            "section_16_applied": True
        }

    # =====================================================
    # SETTLEMENT LOGIC
    # =====================================================

    def _compute_settlement_amount(self,
                                   statutory_total: float,
                                   probability: float) -> int:

        if probability >= 0.75:
            ratio = 0.95
        elif probability >= 0.60:
            ratio = 0.90
        elif probability >= 0.40:
            ratio = 0.85
        else:
            ratio = 0.75

        return int(statutory_total * ratio)

    # =====================================================
    # STRUCTURED DRAFT BUILDER
    # =====================================================

    def _build_structured_draft(self,
                                case_data: Dict,
                                statutory: Dict,
                                settlement: int,
                                probability: float) -> Dict:

        return {
            "metadata": {
                "document_type": "SETTLEMENT PROPOSAL",
                "generated_on": datetime.now().isoformat(),
                "case_reference": case_data.get("case_id", "N/A"),
                "governing_law": "MSME Act, 2006 & Arbitration and Conciliation Act, 1996"
            },
            "statutory_basis": self._legal_basis_text(statutory),
            "settlement_terms": {
                "settlement_amount": settlement,
                "statutory_entitlement": statutory["total"],
                "concession": statutory["total"] - settlement
            },
            "payment_terms": self._payment_structure(settlement),
            "recital": self._optional_llm_recital(
                statutory["principal"],
                settlement,
                probability
            ),
            "disclaimer": (
                "This draft is AI-assisted decision support. "
                "Final execution subject to legal review."
            )
        }

    # =====================================================
    # LEGAL TEXT
    # =====================================================

    def _legal_basis_text(self, statutory: Dict) -> str:

        if not statutory["section_16_applied"]:
            return (
                "Payment within statutory period under Section 15. "
                "No interest liability triggered."
            )

        return (
            f"Under Section 15 read with Section 16 of MSME Act 2006, "
            f"buyer liable to pay compound interest at "
            f"{statutory['annual_rate_percent']}% per annum "
            f"(3× RBI bank rate). "
            f"Total statutory entitlement: ₹{statutory['total']:,.2f} "
            f"(Principal ₹{statutory['principal']:,.2f} "
            f"+ Interest ₹{statutary_interest(statutory):,.2f})."
        )

    # helper to avoid key typo crash
    def _safe_interest(self, statutory: Dict):
        return statutory.get("interest", 0.0)

    # Fix formatting bug
    def _payment_structure(self, amount: int) -> Dict:

        if amount <= 100000:
            return {
                "mode": "Single Payment",
                "timeline": "Within 7 days",
                "amount": amount
            }

        elif amount <= 500000:
            return {
                "mode": "Two Installments",
                "installments": [
                    {"due": "15 days", "amount": int(amount * 0.6)},
                    {"due": "45 days", "amount": int(amount * 0.4)}
                ],
                "default_clause":
                    "Default revives full statutory claim including interest."
            }

        else:
            return {
                "mode": "Three Installments",
                "installments": [
                    {"due": "Immediate", "amount": int(amount * 0.4)},
                    {"due": "30 days", "amount": int(amount * 0.35)},
                    {"due": "60 days", "amount": int(amount * 0.25)}
                ],
                "default_clause":
                    "Default revokes concession; full statutory entitlement becomes payable."
            }

    # =====================================================
    # OPTIONAL LLM POLISH
    # =====================================================

    def _optional_llm_recital(self,
                              principal: int,
                              settlement: int,
                              probability: float) -> str:

        if not self.llm_client:
            return ""

        prompt = (
            f"Draft 3 formal legal sentences: Settlement of ₹{settlement:,} "
            f"against principal claim ₹{principal:,}. "
            f"Emphasize amicable resolution and preservation of business relationship."
        )

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=80
            )
            return response.choices[0].message.content.strip()
        except:
            return ""

    # =====================================================
    # TEXT COMPILER
    # =====================================================

    def _compile_text(self, draft: Dict) -> str:

        lines = []
        meta = draft["metadata"]

        lines.append("=" * 80)
        lines.append(meta["document_type"].center(80))
        lines.append("=" * 80)
        lines.append(f"Generated On: {meta['generated_on']}")
        lines.append(f"Case Ref: {meta['case_reference']}")
        lines.append("")
        lines.append(draft["statutory_basis"])
        lines.append("")
        lines.append(f"Proposed Settlement Amount: ₹{draft['settlement_terms']['settlement_amount']:,}")
        lines.append(f"Concession Granted: ₹{draft['settlement_terms']['concession']:,}")
        lines.append("")
        lines.append("PAYMENT TERMS")
        lines.append("-" * 80)

        payment = draft["payment_terms"]

        if "installments" in payment:
            for inst in payment["installments"]:
                lines.append(f"• ₹{inst['amount']:,} due {inst['due']}")
        else:
            lines.append(f"• ₹{payment['amount']:,} within {payment['timeline']}")

        lines.append("")
        lines.append(draft["recital"])
        lines.append("")
        lines.append(draft["disclaimer"])

        return "\n".join(lines)


# Utility to avoid format typo
def statutary_interest(statutory: Dict):
    return statutory.get("interest", 0.0)
