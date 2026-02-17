import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class NegotiationState:
    round_num: int
    claim_amount: int
    delay_days: int
    document_count: int
    dispute_type: str
    settlement_probability: float
    last_opponent_offer: Optional[int] = None
    last_our_offer: Optional[int] = None
    concession_pattern: List[str] = None
    
    def __post_init__(self):
        if self.concession_pattern is None:
            self.concession_pattern = []

class MultiRoundNegotiationEngine:
    """
    Deterministic negotiation with minimal LLM dependency.
    All logic rule-based. LLM only for tone adjustment.
    """
    
    # Negotiation constants
    MAX_ROUNDS = 5
    CONCESSION_FLOOR = 0.65  # Never go below 65% of claim
    AGGRESSIVE_OPENING = 0.92
    STRONG_OPENING = 0.85
    BALANCED_OPENING = 0.78
    DEFENSIVE_OPENING = 0.68
    
    # Concession schedule by round
    CONCESSION_SCHEDULE = {
        1: 0.00,  # No concession
        2: 0.03,  # 3% reduction
        3: 0.07,  # 7% reduction  
        4: 0.12,  # 12% reduction
        5: 0.15   # 15% reduction (final)
    }
    
    # Psychological tactics by round
    TACTICS = {
        1: {"name": "Anchor High", "desc": "Set aggressive baseline"},
        2: {"name": "Justify Position", "desc": "Cite statutory provisions"},
        3: {"name": "Limited Concession", "desc": "Small move, demand reciprocity"},
        4: {"name": "Final Offer Setup", "desc": "Create urgency"},
        5: {"name": "Walk-Away Threat", "desc": "MSEFC escalation warning"}
    }
    
    def __init__(self, llm_client=None, model="micro"):
        self.llm_client = llm_client
        self.model = model
        self.conversation_history = []
    
    def start_negotiation(self, case_data: Dict, prediction: Dict) -> Dict:
        """Initialize Round 1"""
        state = NegotiationState(
            round_num=1,
            claim_amount=case_data["claim_amount"],
            delay_days=case_data["delay_days"],
            document_count=case_data["document_count"],
            dispute_type=case_data["dispute_type"],
            settlement_probability=prediction["probability"] / 100
        )
        
        return self._generate_round_response(state, is_initial=True)
    
    def process_counter_offer(self, state_dict: Dict, opponent_offer: int, 
                             opponent_message: str = "") -> Dict:
        """Process Round 2-5"""
        state = NegotiationState(**state_dict)
        state.round_num += 1
        state.last_opponent_offer = opponent_offer
        
        if state.round_num > self.MAX_ROUNDS:
            return self._generate_final_ultimatum(state)
        
        # Analyze opponent pattern
        state.concession_pattern.append(
            self._classify_opponent_move(state, opponent_offer, opponent_message)
        )
        
        return self._generate_round_response(state, opponent_message=opponent_message)
    
    def _classify_opponent_move(self, state: NegotiationState, 
                                offer: int, message: str) -> str:
        """Classify opponent's negotiation style"""
        if state.last_our_offer:
            ratio = offer / state.last_our_offer
            if ratio < 0.5:
                return "extreme_lowball"
            elif ratio < 0.75:
                return "aggressive"
            elif ratio < 0.90:
                return "moderate"
            else:
                return "cooperative"
        return "opening"
    
    def _calculate_opening_base(self, state: NegotiationState) -> float:
        """Determine opening offer percentage based on case strength"""
        prob = state.settlement_probability
        
        if prob >= 0.75:
            return self.AGGRESSIVE_OPENING
        elif prob >= 0.60:
            return self.STRONG_OPENING
        elif prob >= 0.40:
            return self.BALANCED_OPENING
        else:
            return self.DEFENSIVE_OPENING
    
    def _generate_round_response(self, state: NegotiationState, 
                                  is_initial: bool = False,
                                  opponent_message: str = "") -> Dict:
        """Core logic: Generate response for current round"""
        
        base_rate = self._calculate_opening_base(state)
        concession = self.CONCESSION_SCHEDULE.get(state.round_num, 0.15)
        
        # Calculate our offer
        our_offer_pct = base_rate - concession
        our_offer = int(state.claim_amount * our_offer_pct)
        state.last_our_offer = our_offer
        
        # Determine tactic
        tactic = self.TACTICS.get(state.round_num, self.TACTICS[5])
        
        # Calculate gap analysis
        gap = None
        if state.last_opponent_offer:
            gap = {
                "absolute": state.last_opponent_offer - our_offer,
                "percentage": round((state.last_opponent_offer - our_offer) / state.last_opponent_offer * 100, 1),
                "assessment": self._assess_gap(state.last_opponent_offer, our_offer, state.claim_amount)
            }
        
        # Build response components
        response = {
            "round": state.round_num,
            "our_offer": our_offer,
            "offer_percentage": round(our_offer_pct * 100, 1),
            "tactic": tactic,
            "rationale": self._build_rationale(state, tactic, gap),
            "gap_analysis": gap,
            "next_moves": self._suggest_next_moves(state, gap),
            "state": {
                "round_num": state.round_num,
                "claim_amount": state.claim_amount,
                "delay_days": state.delay_days,
                "document_count": state.document_count,
                "dispute_type": state.dispute_type,
                "settlement_probability": state.settlement_probability,
                "last_opponent_offer": state.last_opponent_offer,
                "last_our_offer": state.last_our_offer,
                "concession_pattern": state.concession_pattern
            },
            "is_final_round": state.round_num == self.MAX_ROUNDS,
            "escalation_warning": state.round_num >= 4
        }
        
        # Light LLM polish if available
        if self.llm_client and state.round_num == 1:
            response["polished_message"] = self._light_llm_polish(
                response["rationale"], state, tactic
            )
        else:
            response["polished_message"] = response["rationale"]
        
        return response
    
    def _build_rationale(self, state: NegotiationState, tactic: Dict, 
                         gap: Optional[Dict]) -> str:
        """Build negotiation rationale without LLM"""
        
        parts = []
        
        # Opening anchor
        if state.round_num == 1:
            parts.append(
                f"ROUND 1 - ANCHOR HIGH: "
                f"Opening at ₹{state.last_our_offer:,} ({tactic['desc']}). "
                f"Based on {state.delay_days}-day delay and {state.document_count} supporting documents, "
                f"statutory claim is strong. "
                f"Settlement probability: {state.settlement_probability*100:.0f}%."
            )
        
        # Response to counter
        elif gap:
            direction = "above" if gap['absolute'] > 0 else "below"
            parts.append(
                f"ROUND {state.round_num} - {tactic['name'].upper()}: "
                f"Opponent offered ₹{state.last_opponent_offer:,}. "
                f"Our position: ₹{state.last_our_offer:,} ({abs(gap['percentage']):.1f}% {direction} their offer). "
                f"Assessment: {gap['assessment']}. "
            )
            
            # Add pattern analysis
            if len(state.concession_pattern) >= 2:
                if "aggressive" in state.concession_pattern[-2:]:
                    parts.append("Opponent showing resistance. Hold firm.")
                elif "cooperative" in state.concession_pattern[-2:]:
                    parts.append("Opponent cooperative. Small concession justified.")
        
        # Add statutory reminder
        if state.round_num >= 3:
            parts.append(
                f" Reminder: MSME Act Section 16 mandates "
                f"{0.18 if state.delay_days > 90 else 0.12*100}% interest. "
                f"MSEFC escalation remains option."
            )
        
        return " | ".join(parts)
    
    def _assess_gap(self, opponent: int, ours: int, claim: int) -> str:
        """Assess the negotiation gap"""
        ratio = opponent / claim
        if ratio < 0.50:
            return "Extreme lowball - reject and cite statutory minimums"
        elif ratio < 0.70:
            return "Below reasonable range - demand justification"
        elif ratio < 0.85:
            return "Entering negotiation zone - conditional acceptance possible"
        else:
            return "Within acceptable range - push for final close"
    
    def _suggest_next_moves(self, state: NegotiationState, 
                           gap: Optional[Dict]) -> List[Dict]:
        """Suggest 2-3 possible next actions"""
        moves = []
        
        if state.round_num < 3:
            moves.append({
                "action": "hold_firm",
                "description": "Reject counter, restate statutory position",
                "risk": "May stall negotiation",
                "reward": "Maintains anchor point"
            })
        
        if gap and gap['percentage'] < 15:
            moves.append({
                "action": "conditional_accept",
                "description": f"Accept ₹{state.last_opponent_offer:,} with immediate payment clause",
                "risk": "May leave money on table",
                "reward": "Certain closure"
            })
        
        if state.round_num >= 3:
            moves.append({
                "action": "escalate_threat",
                "description": "Warn of MSEFC reference",
                "risk": "May harden opponent position",
                "reward": "Creates deadline pressure"
            })
        
        return moves[:3]  # Max 3 options
    
    def _generate_final_ultimatum(self, state: NegotiationState) -> Dict:
        """Generate final take-it-or-leave-it"""
        
        final_offer = int(state.claim_amount * 0.70)  # Floor at 70%
        
        return {
            "round": "FINAL",
            "our_offer": final_offer,
            "offer_percentage": 70.0,
            "tactic": {"name": "Final Offer", "desc": "Take it or MSEFC"},
            "rationale": (
                f"FINAL ROUND: Last offer ₹{final_offer:,} (70% of claim). "
                f"If rejected, proceeding to MSEFC under Section 18. "
                f"Statutory interest continues accruing at "
                f"{0.18 if state.delay_days > 90 else 0.12*100}%."
            ),
            "ultimatum": True,
            "escalation_path": "MSEFC → Arbitration → Civil Court",
            "timeline": "90 days conciliation + 90 days arbitration",
            "state": {
                "round_num": "FINAL",
                "claim_amount": state.claim_amount,
                "last_our_offer": final_offer
            }
        }
    
    def _light_llm_polish(self, rationale: str, state: NegotiationState, 
                          tactic: Dict) -> str:
        """Minimal LLM call - only for Round 1 opening"""
        
        if not self.llm_client:
            return rationale
        
        # Ultra-short prompt to save tokens
        prompt = f"""Rewrite as professional negotiation opener (2 sentences):
Case: ₹{state.claim_amount} claim, {state.delay_days} days delay.
Strategy: {tactic['name']}, offer ₹{state.last_our_offer}.
Tone: Firm but professional. Cite MSME Act if relevant."""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=80,  # Very short
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except:
            return rationale  # Fallback to rule-based


class NegotiationSessionManager:
    """Manage multiple active negotiation sessions"""
    
    def __init__(self):
        self.sessions = {}
        self.engine = MultiRoundNegotiationEngine()
    
    def create_session(self, session_id: str, case_data: Dict, prediction: Dict):
        """Start new negotiation"""
        response = self.engine.start_negotiation(case_data, prediction)
        self.sessions[session_id] = response["state"]
        return response
    
    def continue_session(self, session_id: str, opponent_offer: int, 
                         message: str = "") -> Dict:
        """Continue existing negotiation"""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        state = self.sessions[session_id]
        response = self.engine.process_counter_offer(
            state, opponent_offer, message
        )
        self.sessions[session_id] = response["state"]
        return response
    
    def get_session_state(self, session_id: str) -> Dict:
        """Get current state"""
        return self.sessions.get(session_id, {})