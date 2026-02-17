import os
import json
import uuid
from datetime import datetime

class AuditLogger:
    def __init__(self, log_dir="logs"):
        """
        Initialize the AuditLogger.
        
        Args:
            log_dir (str): Directory where logs will be stored. Defaults to "logs".
        """
        # Ensure the log directory exists
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_dir = os.path.join(self.base_dir, log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "prediction_audit.jsonl")

    def log_prediction(self, inputs, prediction_result, model_version="1.0"):
        """
        Log a prediction event.

        Args:
            inputs (dict): input features used for prediction.
            prediction_result (dict): The result validation from the model.
            model_version (str): Version of the model used.
        """
        case_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            "timestamp": timestamp,
            "case_id": case_id,
            "inputs": inputs,
            "prediction": {
                "probability": prediction_result.get("probability"),
                "decision": prediction_result.get("prediction"),
                "threshold": prediction_result.get("threshold"),
            },
            "model_version": model_version
        }

        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"Failed to write audit log: {e}")
            
        return case_id
