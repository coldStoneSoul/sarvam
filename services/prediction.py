import os
import json
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from services.audit import AuditLogger
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
sentiment_analyzer = SentimentIntensityAnalyzer()
# Initialize Audit Logger
audit_logger = AuditLogger()
import xgboost as xgb
# Get absolute path to the data file
# ../prediction/msme_synthetic_cases.json relative to this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "prediction", "msme_synthetic_cases.json")

# Load and prepare data
# Load model and encoders if they exist, otherwise train
MODEL_PATH = os.path.join(BASE_DIR, "model", "xgb_model.pkl")
DISPUTE_ENC_PATH = os.path.join(BASE_DIR, "model", "dispute_encoder.pkl")
STATE_ENC_PATH = os.path.join(BASE_DIR, "model", "state_encoder.pkl")
FEATURES = [
    "claim_amount",
    "delay_days",
    "document_count",
    "document_completeness_score",
    "dispute_type_enc",
    "jurisdiction_enc"
]
# Define global variables for model and encoders
xgb_model = None
dispute_encoder = None
state_encoder = None
dispute_types = []
jurisdictions = []

def load_or_train_model():
    global xgb_model, dispute_encoder, state_encoder, dispute_types, jurisdictions
    
    if os.path.exists(MODEL_PATH) and os.path.exists(DISPUTE_ENC_PATH) and os.path.exists(STATE_ENC_PATH):
        try:
            import joblib
            xgb_model = joblib.load(MODEL_PATH)
            dispute_encoder = joblib.load(DISPUTE_ENC_PATH)
            state_encoder = joblib.load(STATE_ENC_PATH)
            
            # Load data just to get lists for dropdowns
            with open(JSON_PATH) as _f:
                _case_data = json.load(_f)
            _df = pd.DataFrame(_case_data)
            dispute_types = sorted(_df["dispute_type"].unique().tolist())
            jurisdictions = sorted(_df["jurisdiction"].unique().tolist())
            
            print("Model and encoders loaded from disk.")
            return
        except Exception as e:
            print(f"Failed to load model: {e}. Retraining...")

    # Load and prepare data
    with open(JSON_PATH) as _f:
        _case_data = json.load(_f)

    _df = pd.DataFrame(_case_data)

    dispute_encoder = LabelEncoder()
    state_encoder = LabelEncoder()

    _df["dispute_type_enc"] = dispute_encoder.fit_transform(_df["dispute_type"])
    _df["jurisdiction_enc"] = state_encoder.fit_transform(_df["jurisdiction"])

    # Train model
    xgb_model = XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9, eval_metric="logloss", random_state=42,
    )
    xgb_model.fit(_df[FEATURES], _df["is_settlement"])

    # Export for use in UI dropdowns
    dispute_types = sorted(_df["dispute_type"].unique().tolist())
    jurisdictions = sorted(_df["jurisdiction"].unique().tolist())
    
    # Save model and encoders
    try:
        import joblib
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(xgb_model, MODEL_PATH)
        joblib.dump(dispute_encoder, DISPUTE_ENC_PATH)
        joblib.dump(state_encoder, STATE_ENC_PATH)
        print("Model and encoders saved to disk.")
    except Exception as e:
        print(f"Failed to save model: {e}")

    # Debug print
    print(f"XGBoost model trained (Services). Dispute types: {len(dispute_types)}, Jurisdictions: {len(jurisdictions)}")

# Initialize model
load_or_train_model()


def generate_deep_analysis(
    claim_amount,
    delay_days,
    document_count,
    document_score,
    dispute_type,
    jurisdiction,
    probability,
    feature_contribution,
    optimal_threshold=0.607
):
    analysis = []

    def interpret_feature(name, display_name, icon):
        contrib = feature_contribution.get(name, 0)

        if contrib > 0:
            impact = "positive"
            description = (
                f"{display_name} positively influenced settlement likelihood "
                f"(model contribution: +{contrib:.3f})."
            )
        elif contrib < 0:
            impact = "negative"
            description = (
                f"{display_name} reduced settlement likelihood "
                f"(model contribution: {contrib:.3f})."
            )
        else:
            impact = "neutral"
            description = (
                f"{display_name} had minimal influence on the model prediction."
            )

        return {
            "factor": display_name,
            "impact": impact,
            "icon": icon,
            "description": description
        }

    # Model-aligned explanations
    analysis.append(
        interpret_feature("delay_days", "Payment Delay", "fa-clock")
    )

    analysis.append(
        interpret_feature("document_count", "Documentation Strength", "fa-file-lines")
    )

    analysis.append(
        interpret_feature("claim_amount", "Claim Amount", "fa-indian-rupee-sign")
    )

    analysis.append(
        interpret_feature("dispute_type_enc", "Dispute Category", "fa-gavel")
    )

    analysis.append(
        interpret_feature("jurisdiction_enc", "Jurisdiction Influence", "fa-map-location-dot")
    )

    # Add contextual narrative (UX layer)
    analysis.append({
        "factor": "Case Context",
        "impact": "neutral",
        "icon": "fa-circle-info",
        "description": (
            f"The case involves a claim of ₹{claim_amount:,} "
            f"with a delay of {delay_days} days and "
            f"{document_count} supporting documents "
            f"(completeness score: {document_score:.2f})."
        )
    })

    # Overall Assessment based on optimized threshold
    if probability >= optimal_threshold:
        analysis.append({
            "factor": "Overall Assessment",
            "impact": "positive",
            "icon": "fa-thumbs-up",
            "description": (
                f"Predicted settlement probability is {probability:.2%}, "
                f"which exceeds the decision threshold ({optimal_threshold:.2f}). "
                f"The model indicates strong settlement potential."
            )
        })
    else:
        analysis.append({
            "factor": "Overall Assessment",
            "impact": "negative",
            "icon": "fa-exclamation-triangle",
            "description": (
                f"Predicted settlement probability is {probability:.2%}, "
                f"below the decision threshold ({optimal_threshold:.2f}). "
                f"The model indicates lower likelihood of settlement."
            )
        })

    return analysis


OPTIMAL_THRESHOLD = 0.607

def run_xgb_prediction(claim_amount, delay_days, document_count, dispute_type, jurisdiction):
    """Run XGBoost prediction and return full results dict."""

    document_score = document_count / 4

    try:
        dispute_enc_val = int(dispute_encoder.transform([dispute_type])[0])
        jurisdiction_enc_val = int(state_encoder.transform([jurisdiction])[0])
    except Exception as e:
        print(f"Encoder error: {e}. Using defaults.")
        dispute_enc_val = 0
        jurisdiction_enc_val = 0

    input_dict = {
        "claim_amount": [claim_amount],
        "delay_days": [delay_days],
        "document_count": [document_count],
        "document_completeness_score": [document_score],
        "dispute_type_enc": [dispute_enc_val],
        "jurisdiction_enc": [jurisdiction_enc_val],
    }

    final_data = pd.DataFrame(input_dict, columns=FEATURES)

    # ---- MODEL PREDICTION ----
    probability = float(xgb_model.predict_proba(final_data)[0][1])

    # ---- CLASS DECISION USING OPTIMAL THRESHOLD ----
    prediction = 1 if probability >= OPTIMAL_THRESHOLD else 0

    if prediction == 1:
        priority, priority_class = "High Settlement Likelihood", "high"
    else:
        priority, priority_class = "Lower Settlement Likelihood", "low"

    # ---- SETTLEMENT RANGE (independent of classification) ----
    base_min, base_max = 0.70, 0.85
    doc_boost_min = document_score * 0.15
    doc_boost_max = document_score * 0.08
    settle_min = int(claim_amount * (base_min + doc_boost_min))
    settle_max = int(claim_amount * (base_max + doc_boost_max))


    dmat = xgb.DMatrix(final_data)
    contrib = xgb_model.get_booster().predict(dmat, pred_contribs=True)[0]

    feature_contribution = {
        feature: float(value)
        for feature, value in zip(FEATURES + ["bias"], contrib)
    }

    # ---- GENERATE EXPLAINABLE ANALYSIS ----
    deep_analysis = generate_deep_analysis(
        claim_amount,
        delay_days,
        document_count,
        document_score,
        dispute_type,
        jurisdiction,
        probability,
        feature_contribution,
        optimal_threshold=OPTIMAL_THRESHOLD
    )
    negotiation_strategy = generate_negotiation_strategy(
    probability,
    claim_amount,
    document_score,
    delay_days,
    feature_contribution
)


    # ---- AUDIT LOGGING ----
    try:
        audit_inputs = {
            "claim_amount": claim_amount,
            "delay_days": delay_days,
            "document_count": document_count,
            "dispute_type": dispute_type,
            "jurisdiction": jurisdiction
        }
        
        audit_result = {
            "probability": probability,
            "prediction": prediction,
            "threshold": OPTIMAL_THRESHOLD
        }
        
        # Log the prediction
        case_id = audit_logger.log_prediction(audit_inputs, audit_result)
        print(f"Prediction logged with Case ID: {case_id}")
        
    except Exception as e:
        print(f"Error logging prediction: {e}")
        case_id = None

    return {
        "success": True,
        "probability": round(probability * 100, 2),
        "prediction": prediction,
        "threshold": OPTIMAL_THRESHOLD,
        "priority": priority,
        "priority_class": priority_class,
        "settle_min": f"{settle_min:,}",
        "settle_max": f"{settle_max:,}",
        "delay_days": int(delay_days),
        "document_score": float(document_score),
        "claim_amount": f"{claim_amount:,}",
        "feature_contribution": feature_contribution,
        "deep_analysis": deep_analysis,
        "case_id": case_id,
        "negotiation_strategy": negotiation_strategy

    }
def generate_negotiation_strategy(
    probability,
    claim_amount,
    document_score,
    delay_days,
    feature_contribution,
    counterparty_text=None
):
    strategy = {}

    # ---- Determine Zone ----
    if probability >= 0.75:
        zone = "Aggressive"
        opening_ratio = 0.92
    elif probability >= 0.60:
        zone = "Strong"
        opening_ratio = 0.85
    elif probability >= 0.40:
        zone = "Balanced"
        opening_ratio = 0.78
    else:
        zone = "Defensive"
        opening_ratio = 0.68

    # ---- Sentiment Adjustment ----
    sentiment_label = "neutral"
    sentiment_score = 0

    if counterparty_text:
        sentiment_label, sentiment_score = analyze_sentiment(counterparty_text)

        if sentiment_label == "positive":
            opening_ratio += 0.03
        elif sentiment_label == "negative":
            opening_ratio -= 0.05

    opening_ratio = min(max(opening_ratio, 0.60), 0.95)
    opening_offer = int(claim_amount * opening_ratio)

    # ---- Installment Logic ----
    installment_plan = None
    if claim_amount > 1_500_000 or sentiment_label == "negative":
        installment_plan = {
            "recommended_installments": 3,
            "per_installment": int(opening_offer / 3)
        }

    # ---- Tactical Note ----
    dominant_feature = max(
        feature_contribution,
        key=lambda k: abs(feature_contribution[k])
    )

    tactical_note = f"Primary leverage factor: {dominant_feature}. "

    if sentiment_label == "negative":
        tactical_note += "Adopt de-escalation tone and propose structured repayment."
    elif sentiment_label == "positive":
        tactical_note += "Maintain assertive negotiation posture."
    else:
        tactical_note += "Proceed with balanced negotiation."

    strategy = {
        "negotiation_zone": zone,
        "opening_offer": f"{opening_offer:,}",
        "installment_plan": installment_plan,
        "sentiment_detected": sentiment_label,
        "sentiment_score": sentiment_score,
        "tactical_note": tactical_note
    }

    return strategy

def analyze_sentiment(text):
    scores = sentiment_analyzer.polarity_scores(text)
    compound = scores["compound"]

    if compound >= 0.3:
        sentiment = "positive"
    elif compound <= -0.3:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return sentiment, compound

def _clean_int(val, default=0):
    """Safely convert a value to int, stripping commas and currency symbols."""
    if isinstance(val, (int, float)):
        return int(val)
    if not val:
        return default
    clean = ''.join(c for c in str(val) if c.isdigit() or c == '.')
    try:
        return int(float(clean))
    except (ValueError, TypeError):
        return default


def generate_settlement_draft_text(case_data):
    """Generate rule-based settlement draft text."""
    case_id = case_data.get("case_id", "N/A")
    dispute_type = case_data.get("dispute_type", "")
    jurisdiction = case_data.get("jurisdiction", "")
    claim_amount = _clean_int(case_data.get("claim_amount", 0))
    delay_days = _clean_int(case_data.get("delay_days", 0))
    document_count = _clean_int(case_data.get("document_count", 0))

    try:
        probability = float(str(case_data.get("probability", 0)).replace(",", ""))
    except (ValueError, TypeError):
        probability = 0.0
        
    # Calculate document score if not present
    document_score = float(case_data.get("document_score", document_count / 4))

    settle_min = case_data.get("settle_min", "0")
    settle_max = case_data.get("settle_max", "0")
    if isinstance(settle_min, str):
        settle_min = int(settle_min.replace(",", ""))
    if isinstance(settle_max, str):
        settle_max = int(settle_max.replace(",", ""))

    confidence_level = "High" if probability >= 60 else "Medium" if probability >= 30 else "Low"

    d = []
    d.append("ASSISTED SETTLEMENT DRAFT")
    d.append("(Generated by MSME Negotiation AI – Decision Support System)")
    d.append("")
    d.append("This draft is generated to assist parties in exploring a mutually agreeable settlement.")
    d.append("Final terms are subject to mutual consent and approval by the adjudicating authority.")
    d.append("")
    d.append("=" * 80)
    d.append("")
    d.append("CASE SUMMARY")
    d.append("-" * 80)
    if case_id != "N/A":
        d.append(f"Case Reference ID: {case_id}")
    d.append(f"Dispute Type: {dispute_type}")
    d.append(f"Jurisdiction: {jurisdiction}")
    d.append(f"Claimed Amount: ₹{claim_amount:,}")
    d.append(f"Payment Delay: {delay_days} days")
    d.append(f"Supporting Documents Submitted: {document_count}")
    d.append("")
    d.append("=" * 80)
    d.append("")
    d.append("AI ASSESSMENT SUMMARY")
    d.append("-" * 80)
    d.append(f"Settlement likelihood estimate: {probability:.2f}%")
    d.append(f"Assessment Confidence Level: {confidence_level}")
    d.append("")
    d.append("=" * 80)
    d.append("")
    d.append("SUGGESTED SETTLEMENT RANGE")
    d.append("-" * 80)
    d.append(f"₹{settle_min:,} – ₹{settle_max:,}")
    d.append("This range is indicative and derived from settlement ratios observed in comparable cases.")
    d.append("")
    d.append("=" * 80)
    d.append("")
    
    # SECTION 5: Negotiation Guidance (Dynamic, rule-based text)
    d.append("NEGOTIATION GUIDANCE")
    d.append("-" * 80)
    d.append("")
    
    guidance_points = []
    
    # Rule 1: Document strength
    if document_score >= 0.75:
        guidance_points.append("• The availability of supporting documentation strengthens the factual basis of the claim\n  and may facilitate constructive negotiation.")
    elif document_score < 0.5:
        guidance_points.append("• Limited documentation may require additional evidence gathering to strengthen the\n  negotiating position.")
    
    # Rule 2: Delay duration
    if delay_days > 200:
        guidance_points.append("• The extended duration of payment delay may be a relevant factor for consideration\n  during discussions.")
    elif delay_days < 100:
        guidance_points.append("• The relatively short delay period may enable expedited resolution through prompt\n  negotiation.")
    
    # Rule 3: Settlement probability
    if probability < 30:
        guidance_points.append("• Given the current indicators, parties may consider alternative dispute resolution\n  mechanisms in parallel with settlement discussions.")
    elif probability > 60:
        guidance_points.append("• Strong settlement indicators suggest prioritizing direct negotiation may yield\n  favorable outcomes.")
    
    # Rule 4: Claim amount considerations
    if claim_amount > 1000000:
        guidance_points.append("• The substantial claim amount warrants careful consideration of payment terms\n  and structured settlement options.")
    
    # Add guidance points to draft (max 3)
    for point in guidance_points[:3]:
        d.append(point)
        d.append("")
    
    d.append("=" * 80)
    d.append("")

    d.append("DISCLAIMER")
    d.append("-" * 80)
    d.append("This draft is generated as an AI-assisted decision support output.")
    d.append("It does not constitute legal advice, adjudication, or a binding settlement.")
    d.append("All final decisions are subject to review and approval by the designated authority.")
    return "\n".join(d)
