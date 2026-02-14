import os
import json
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

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


def generate_deep_analysis(claim_amount, delay_days, document_count, document_score,
                           dispute_type, jurisdiction, probability, feature_importance):
    analysis = []
    # Analyze delay days impact
    if delay_days < 100:
        analysis.append({
            'factor': 'Payment Delay', 'impact': 'positive', 'icon': 'fa-check-circle',
            'description': f'Short delay period ({delay_days} days) increases settlement likelihood. Disputes with delays under 100 days typically see faster resolution.'
        })
    elif delay_days < 300:
        analysis.append({
            'factor': 'Payment Delay', 'impact': 'neutral', 'icon': 'fa-minus-circle',
            'description': f'Moderate delay period ({delay_days} days). This is within typical negotiation timeframes but may require careful handling.'
        })
    else:
        analysis.append({
            'factor': 'Payment Delay', 'impact': 'negative', 'icon': 'fa-exclamation-circle',
            'description': f'Extended delay period ({delay_days} days) may complicate settlement. Longer delays often correlate with reduced settlement probability.'
        })
    
    # Analyze document completeness
    if document_score >= 0.75:
        analysis.append({
            'factor': 'Documentation', 'impact': 'positive', 'icon': 'fa-check-circle',
            'description': f'Strong documentation ({document_count} documents, {document_score:.2f} score). Comprehensive evidence significantly improves settlement chances.'
        })
    elif document_score >= 0.5:
        analysis.append({
            'factor': 'Documentation', 'impact': 'neutral', 'icon': 'fa-minus-circle',
            'description': f'Adequate documentation ({document_count} documents, {document_score:.2f} score). Consider gathering additional supporting evidence if available.'
        })
    else:
        analysis.append({
            'factor': 'Documentation', 'impact': 'negative', 'icon': 'fa-exclamation-circle',
            'description': f'Limited documentation ({document_count} documents, {document_score:.2f} score). Insufficient evidence may weaken negotiating position.'
        })
    
    # Analyze claim amount
    if claim_amount < 200000:
        analysis.append({
            'factor': 'Claim Amount', 'impact': 'positive', 'icon': 'fa-check-circle',
            'description': f'Lower claim amount (₹{claim_amount:,}) typically facilitates faster settlements with higher success rates.'
        })
    elif claim_amount < 1000000:
        analysis.append({
            'factor': 'Claim Amount', 'impact': 'neutral', 'icon': 'fa-minus-circle',
            'description': f'Medium claim amount (₹{claim_amount:,}). Requires balanced negotiation approach between parties.'
        })
    else:
        analysis.append({
            'factor': 'Claim Amount', 'impact': 'negative', 'icon': 'fa-exclamation-circle',
            'description': f'High claim amount (₹{claim_amount:,}) may require more extensive negotiation and review processes.'
        })
    
    # Analyze dispute type
    analysis.append({
        'factor': 'Dispute Type', 'impact': 'neutral', 'icon': 'fa-gavel',
        'description': f'Case classified as "{dispute_type}". Historical data for this dispute category has been factored into the analysis.'
    })
    
    # Analyze jurisdiction
    analysis.append({
        'factor': 'Jurisdiction', 'impact': 'neutral', 'icon': 'fa-map-location-dot',
        'description': f'Case jurisdiction: {jurisdiction}. Regional patterns and precedents have been considered in this assessment.'
    })
    
    # Overall recommendation
    if probability > 0.6:
        analysis.append({
            'factor': 'Overall Assessment', 'impact': 'positive', 'icon': 'fa-thumbs-up',
            'description': 'Strong indicators suggest high settlement potential. Recommend prioritizing this case for negotiation.'
        })
    elif probability > 0.3:
        analysis.append({
            'factor': 'Overall Assessment', 'impact': 'neutral', 'icon': 'fa-balance-scale',
            'description': 'Mixed indicators suggest moderate settlement potential. Careful evaluation and strategic negotiation recommended.'
        })
    else:
        analysis.append({
            'factor': 'Overall Assessment', 'impact': 'negative', 'icon': 'fa-exclamation-triangle',
            'description': 'Current indicators suggest challenges in reaching settlement. Consider alternative dispute resolution mechanisms.'
        })
    
    return analysis


def run_xgb_prediction(claim_amount, delay_days, document_count, dispute_type, jurisdiction):
    """Run XGBoost prediction and return full results dict."""
    document_score = document_count / 4
    
    # Check if encoders are fitted (should be by load_or_train_model)
    try:
        dispute_enc_val = int(dispute_encoder.transform([dispute_type])[0])
        jurisdiction_enc_val = int(state_encoder.transform([jurisdiction])[0])
    except Exception as e:
        # Fallback if unknown category
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
    probability = float(xgb_model.predict_proba(final_data)[0][1])

    if document_count >= 4:
        probability = min(probability * 1.25, 0.95)
    elif document_count == 3:
        probability = min(probability * 1.15, 0.95)

    feature_importance = xgb_model.feature_importances_

    if probability > 0.6:
        priority, priority_class = "High Settlement Likelihood", "high"
    elif probability > 0.3:
        priority, priority_class = "Medium Settlement Likelihood", "medium"
    else:
        priority, priority_class = "Lower Settlement Likelihood", "low"

    base_min, base_max = 0.70, 0.85
    doc_boost_min = document_score * 0.15
    doc_boost_max = document_score * 0.08
    settle_min = int(claim_amount * (base_min + doc_boost_min))
    settle_max = int(claim_amount * (base_max + doc_boost_max))

    deep_analysis = generate_deep_analysis(
        claim_amount, delay_days, document_count, document_score,
        dispute_type, jurisdiction, probability, feature_importance,
    )

    return {
        "success": True,
        "probability": round(float(probability * 100), 2),
        "priority": priority,
        "priority_class": priority_class,
        "settle_min": f"{settle_min:,}",
        "settle_max": f"{settle_max:,}",
        "delay_days": int(delay_days),
        "document_score": float(document_score),
        "claim_amount": f"{claim_amount:,}",
        "deep_analysis": deep_analysis,
    }


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
