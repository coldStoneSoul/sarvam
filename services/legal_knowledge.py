import math
from typing import Dict, List, Any


class LegalArgumentationEngine:
    """
    Improved MSME Legal Argumentation Engine
    - Section 15 trigger logic added
    - Section 16 monthly compound interest (3x RBI rate)
    - Evidence-weighted escalation model
    - No fake penalties
    """

    # You may later fetch RBI rate dynamically
    RBI_BANK_RATE = 0.085  # Example: 8.5% (update as required)

    STATUTES = {
        "section_15": {
            "title": "Time limit for payment",
            "text": "Buyer must pay within agreed period (max 45 days) or 15 days if no agreement."
        },
        "section_16": {
            "title": "Interest on delayed payment",
            "text": "Compound interest monthly at 3 times RBI bank rate."
        },
        "section_18": {
            "title": "Reference to MSEFC",
            "text": "Either party may refer dispute to MSEFC for conciliation/arbitration."
        }
    }

    COUNTER_ARGUMENTS = {
        "goods_rejection": [
            {"defense": "Goods quality below specification", "rebuttal": "section_9"},
            {"defense": "Delivery delayed causing losses", "rebuttal": "force_majeure_check"},
            {"defense": "Payment terms not agreed", "rebuttal": "po_terms_binding"}
        ],
        "service_non_payment": [
            {"defense": "Service incomplete/defective", "rebuttal": "acceptance_criteria"},
            {"defense": "SLA breaches", "rebuttal": "penalty_clause_limitation"},
            {"defense": "Work not authorized", "rebuttal": "implied_authority_doctrine"}
        ],
        "invoice_non_payment": [
            {"defense": "Invoice discrepancies", "rebuttal": "interest_independent"},
            {"defense": "Cash flow issues", "rebuttal": "not_statutory_defense"},
            {"defense": "Set-off for other claims", "rebuttal": "independent_obligation"}
        ]
    }

    # Evidence scoring weights
    EVIDENCE_WEIGHTS = {
        "signed_po": 0.30,
        "delivery_proof": 0.25,
        "acknowledgement_email": 0.20,
        "invoice_copy": 0.15,
        "ledger_statement": 0.10
    }

    # ---------------- MAIN ENTRY ---------------- #

    def generate_argumentation(self, case_data: Dict, prediction: Dict) -> Dict[str, Any]:

        claim_amount = case_data.get("claim_amount", 0)
        delay_days = case_data.get("delay_days", 0)
        dispute_type = case_data.get("dispute_type", "invoice_non_payment")
        agreed_days = case_data.get("agreed_payment_days", None)

        statutory = self._calculate_statutory_claim(
            claim_amount,
            delay_days,
            agreed_days
        )

        statutes = self._identify_statutes(delay_days)

        opponent_args = self._predict_opponent_defenses(dispute_type)

        rebuttals = self._generate_rebuttals(opponent_args)

        script = self._generate_negotiation_script(
            claim_amount,
            statutory["total"],
            prediction.get("probability", 0.5),
            statutes
        )

        risk = self._assess_escalation_risk(case_data, statutory)

        return {
            "legal_argument": self._format_legal_argument(statutory),
            "statutory_breakdown": statutory,
            "applicable_statutes": statutes,
            "opponent_counter_arguments": [a["defense"] for a in opponent_args],
            "rebuttal_strategy": rebuttals,
            "negotiation_script": script,
            "escalation_risk_assessment": risk
        }

    # ---------------- STATUTORY CALCULATION ---------------- #

    def _calculate_statutory_claim(self, amount: float, delay_days: int,
                                   agreed_days: int = None) -> Dict:

        # Section 15 trigger
        if agreed_days:
            trigger_days = min(agreed_days, 45)
        else:
            trigger_days = 15

        if delay_days <= trigger_days:
            return {
                "principal": amount,
                "interest": 0,
                "total": amount,
                "section_15_trigger": False,
                "section_16_applied": False
            }

        # Section 16 compound interest
        annual_rate = 3 * self.RBI_BANK_RATE
        monthly_rate = annual_rate / 12

        months = delay_days / 30
        compound_factor = (1 + monthly_rate) ** months

        interest = amount * (compound_factor - 1)

        total = amount + interest

        return {
            "principal": amount,
            "annual_interest_rate": round(annual_rate * 100, 2),
            "interest": round(interest, 2),
            "total": round(total, 2),
            "section_15_trigger": True,
            "section_16_applied": True
        }

    # ---------------- STATUTES ---------------- #

    def _identify_statutes(self, delay_days: int) -> List[Dict]:

        statutes = []

        if delay_days > 0:
            statutes.append({
                "section": "15",
                "title": self.STATUTES["section_15"]["title"]
            })

        if delay_days > 15:
            statutes.append({
                "section": "16",
                "title": self.STATUTES["section_16"]["title"]
            })

        statutes.append({
            "section": "18",
            "title": self.STATUTES["section_18"]["title"],
            "strategic_value": "Escalation leverage via statutory conciliation/arbitration"
        })

        return statutes

    # ---------------- DEFENSE & REBUTTALS ---------------- #

    def _predict_opponent_defenses(self, dispute_type: str) -> List[Dict]:
        return self.COUNTER_ARGUMENTS.get(
            dispute_type,
            self.COUNTER_ARGUMENTS["invoice_non_payment"]
        )[:3]

    def _generate_rebuttals(self, opponent_args: List[Dict]) -> str:

        rebuttal_texts = []

        for arg in opponent_args:

            if arg["rebuttal"] == "interest_independent":
                rebuttal_texts.append(
                    f"Against '{arg['defense']}': Interest liability under Section 16 is independent of invoice disputes."
                )
            elif arg["rebuttal"] == "section_9":
                rebuttal_texts.append(
                    f"Against '{arg['defense']}': Written objection required within statutory period. Silence implies acceptance."
                )
            else:
                rebuttal_texts.append(
                    f"Against '{arg['defense']}': Demand documentary proof and challenge factual basis."
                )

        return " | ".join(rebuttal_texts)

    # ---------------- NEGOTIATION SCRIPT ---------------- #

    def _generate_negotiation_script(self, principal: float,
                                     statutory_total: float,
                                     probability: float,
                                     statutes: List[Dict]) -> str:

        if probability >= 0.75:
            offer = statutory_total * 0.95
        elif probability >= 0.60:
            offer = statutory_total * 0.90
        else:
            offer = statutory_total * 0.85

        applicable_sections = ", ".join(
            [f"Section {s['section']}" for s in statutes]
        )

        return (
            f"Our statutory position under MSME Act 2006 is clear. "
            f"Principal: ₹{principal:,.0f}. "
            f"Applicable provisions: {applicable_sections}. "
            f"Total statutory liability: ₹{statutory_total:,.0f}. "
            f"We propose settlement at ₹{offer:,.0f} "
            f"to avoid escalation before MSEFC."
        )

    # ---------------- ESCALATION RISK ---------------- #

    def _assess_escalation_risk(self, case_data: Dict,
                                statutory: Dict) -> Dict:

        evidence_score = 0

        for key, weight in self.EVIDENCE_WEIGHTS.items():
            if case_data.get(key, False):
                evidence_score += weight

        evidence_score = min(evidence_score, 1.0)

        base_prob = 0.65
        win_probability = base_prob + (evidence_score * 0.30)

        return {
            "evidence_strength": f"{round(evidence_score*100)}%",
            "estimated_award_probability": round(win_probability, 2),
            "estimated_recovery": f"₹{int(statutory['total'] * win_probability):,}",
            "escalation_path": "MSEFC → Arbitration → Civil Court",
            "timeline_if_escalated": "6–18 months",
            "recommendation":
                "Settle immediately" if win_probability > 0.80
                else "Negotiate firmly"
        }

    # ---------------- FORMAT ---------------- #

    def _format_legal_argument(self, statutory: Dict) -> str:

        if not statutory["section_16_applied"]:
            return (
                "Payment within statutory period. No interest liability triggered."
            )

        return (
            f"Under Section 16 MSME Act 2006, claimant entitled to "
            f"compound interest at {statutory['annual_interest_rate']}% per annum. "
            f"Total statutory claim: ₹{statutory['total']:,.0f} "
            f"(Principal: ₹{statutory['principal']:,.0f}, "
            f"Interest: ₹{statutory['interest']:,.0f})."
        )
