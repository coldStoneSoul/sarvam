import json
from flask import Flask , request , jsonify , make_response
import pandas as pd
import joblib

app =  Flask(__name__)
# Load data for dropdowns

FEATURES = [
    "claim_amount",
    "delay_days",
    "document_count",
    "document_completeness_score",
    "dispute_type_enc",
    "jurisdiction_enc"
]
model = joblib.load("model/xgb_model.pkl")
dispute_encoder = joblib.load("model/dispute_encoder.pkl")
state_encoder = joblib.load("model/state_encoder.pkl")

print("Model and encoders loaded successfully.")
@app.route('/' , methods=['GET'])
def index():
    return {"success": True}
@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        # Get form data
        data = request.get_json()
        claim_amount = int(data['claim_amount'])
        delay_days = int(data['delay_days'])
        document_count = int(data['document_count'])
        dispute_type = data['dispute_type']
        jurisdiction = data['jurisdiction']
        
        document_score = document_count / 4
        
        # Prepare input data with exact feature names and order
        input_dict = {
            "claim_amount": [claim_amount],
            "delay_days": [delay_days],
            "document_count": [document_count],
            "document_completeness_score": [document_score],
            "dispute_type_enc": [dispute_type],
            "jurisdiction_enc": [jurisdiction]
        }
        
        # Create DataFrame with exact column order matching FEATURES
        final_data = pd.DataFrame(input_dict, columns=FEATURES)
        
        # Make prediction
        probability = float(model.predict_proba(final_data)[0][1])
        
        # CORRECTION: Boost probability for higher document counts
        # The training data has counterintuitive patterns, so we apply a correction
        if document_count >= 4:
            probability = min(probability * 1.25, 0.95)  # 25% boost, cap at 95%
        elif document_count == 3:
            probability = min(probability * 1.15, 0.95)  # 15% boost
        
        # Get feature importance for this prediction
        feature_importance = model.feature_importances_
        
        # Priority logic
        if probability > 0.6:
            priority = "High Settlement Likelihood"
            priority_class = "high"
        elif probability > 0.3:
            priority = "Medium Settlement Likelihood"
            priority_class = "medium"
        else:
            priority = "Lower Settlement Likelihood"
            priority_class = "low"
        
        # Settlement range logic - Better documentation should get better settlements
        # Base range: 70-85% of claim
        # Document score adds 10% to minimum, 5% to maximum
        base_min = 0.70
        base_max = 0.85
        
        # Stronger boost for complete documentation
        doc_boost_min = document_score * 0.15  # Up to 15% boost for 4 docs
        doc_boost_max = document_score * 0.08  # Up to 8% boost for 4 docs
        
        settle_min = int(claim_amount * (base_min + doc_boost_min))
        settle_max = int(claim_amount * (base_max + doc_boost_max))
        
        # Generate deep analysis
        deep_analysis = generate_deep_analysis(
            claim_amount, delay_days, document_count, document_score,
            dispute_type, jurisdiction, probability, feature_importance
        )
        
        return jsonify({
            'success': True,
            'probability': round(float(probability * 100), 2),
            'priority': priority,
            'priority_class': priority_class,
            'settle_min': f"{settle_min:,}",
            'settle_max': f"{settle_max:,}",
            'delay_days': int(delay_days),
            'document_score': float(document_score),
            'claim_amount': f"{claim_amount:,}",
            'deep_analysis': deep_analysis
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
def generate_deep_analysis(claim_amount, delay_days, document_count, document_score, 
                          dispute_type, jurisdiction, probability, feature_importance):
    """Generate detailed analysis of factors affecting the score"""
    
    analysis = []
    
    # Analyze delay days impact
    if delay_days < 100:
        analysis.append({
            'factor': 'Payment Delay',
            'impact': 'positive',
            'icon': 'fa-check-circle',
            'description': f'Short delay period ({delay_days} days) increases settlement likelihood. Disputes with delays under 100 days typically see faster resolution.'
        })
    elif delay_days < 300:
        analysis.append({
            'factor': 'Payment Delay',
            'impact': 'neutral',
            'icon': 'fa-minus-circle',
            'description': f'Moderate delay period ({delay_days} days). This is within typical negotiation timeframes but may require careful handling.'
        })
    else:
        analysis.append({
            'factor': 'Payment Delay',
            'impact': 'negative',
            'icon': 'fa-exclamation-circle',
            'description': f'Extended delay period ({delay_days} days) may complicate settlement. Longer delays often correlate with reduced settlement probability.'
        })
    
    # Analyze document completeness
    if document_score >= 0.75:
        analysis.append({
            'factor': 'Documentation',
            'impact': 'positive',
            'icon': 'fa-check-circle',
            'description': f'Strong documentation ({document_count} documents, {document_score:.2f} score). Comprehensive evidence significantly improves settlement chances.'
        })
    elif document_score >= 0.5:
        analysis.append({
            'factor': 'Documentation',
            'impact': 'neutral',
            'icon': 'fa-minus-circle',
            'description': f'Adequate documentation ({document_count} documents, {document_score:.2f} score). Consider gathering additional supporting evidence if available.'
        })
    else:
        analysis.append({
            'factor': 'Documentation',
            'impact': 'negative',
            'icon': 'fa-exclamation-circle',
            'description': f'Limited documentation ({document_count} documents, {document_score:.2f} score). Insufficient evidence may weaken negotiating position.'
        })
    
    # Analyze claim amount
    if claim_amount < 200000:
        analysis.append({
            'factor': 'Claim Amount',
            'impact': 'positive',
            'icon': 'fa-check-circle',
            'description': f'Lower claim amount (₹{claim_amount:,}) typically facilitates faster settlements with higher success rates.'
        })
    elif claim_amount < 1000000:
        analysis.append({
            'factor': 'Claim Amount',
            'impact': 'neutral',
            'icon': 'fa-minus-circle',
            'description': f'Medium claim amount (₹{claim_amount:,}). Requires balanced negotiation approach between parties.'
        })
    else:
        analysis.append({
            'factor': 'Claim Amount',
            'impact': 'negative',
            'icon': 'fa-exclamation-circle',
            'description': f'High claim amount (₹{claim_amount:,}) may require more extensive negotiation and review processes.'
        })
    
    # Analyze dispute type
    analysis.append({
        'factor': 'Dispute Type',
        'impact': 'neutral',
        'icon': 'fa-gavel',
        'description': f'Case classified as "{dispute_type}". Historical data for this dispute category has been factored into the analysis.'
    })
    
    # Analyze jurisdiction
    analysis.append({
        'factor': 'Jurisdiction',
        'impact': 'neutral',
        'icon': 'fa-map-location-dot',
        'description': f'Case jurisdiction: {jurisdiction}. Regional patterns and precedents have been considered in this assessment.'
    })
    
    # Overall recommendation
    if probability > 0.6:
        analysis.append({
            'factor': 'Overall Assessment',
            'impact': 'positive',
            'icon': 'fa-thumbs-up',
            'description': 'Strong indicators suggest high settlement potential. Recommend prioritizing this case for negotiation.'
        })
    elif probability > 0.3:
        analysis.append({
            'factor': 'Overall Assessment',
            'impact': 'neutral',
            'icon': 'fa-balance-scale',
            'description': 'Mixed indicators suggest moderate settlement potential. Careful evaluation and strategic negotiation recommended.'
        })
    else:
        analysis.append({
            'factor': 'Overall Assessment',
            'impact': 'negative',
            'icon': 'fa-exclamation-triangle',
            'description': 'Current indicators suggest challenges in reaching settlement. Consider alternative dispute resolution mechanisms.'
        })
    
    return analysis

if __name__ == "__main__":
    app.run(debug=True , port=1536)