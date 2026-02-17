import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.prediction import run_xgb_prediction
import json

def test_prediction_logging():
    print("Testing prediction logging...")
    
    # Mock inputs
    result = run_xgb_prediction(
        claim_amount=500000,
        delay_days=150,
        document_count=5,
        dispute_type="Payment Dispute",
        jurisdiction="Maharashtra"
    )
    
    print("Prediction Result:", json.dumps(result, indent=2))
    
    if "case_id" in result and result["case_id"]:
        print(f"Case ID returned: {result['case_id']}")
    else:
        print("ERROR: Case ID not returned.")
        
    # Check log file
    log_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "prediction_audit.jsonl"))
    if os.path.exists(log_file):
        print(f"Log file found at: {log_file}")
        with open(log_file, "r") as f:
            lines = f.readlines()
            last_line = lines[-1]
            log_entry = json.loads(last_line)
            print("Last Log Entry:", json.dumps(log_entry, indent=2))
            
            if log_entry["case_id"] == result["case_id"]:
                print("SUCCESS: Log entry matches returned Case ID.")
            else:
                print("ERROR: Log entry Case ID does not match.")
    else:
        print(f"ERROR: Log file not found at {log_file}")

if __name__ == "__main__":
    test_prediction_logging()
