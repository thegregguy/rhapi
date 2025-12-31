import json
from bugeater import bug

def display(data):
    """
    Clean the data by removing the account number and print using BugEater
    """
    if not data:
        bug.warn("Display received empty data.")
        return None

    if isinstance(data, dict) and 'account_number' in data:
        del data['account_number']
    
    # Use bugeater's inspect for pretty printing
    bug.inspect(data, label="Display Utility")
    return data

if __name__ == "__main__":
    # Custom Debug Script
    bug.section("Utils.py Debug Mode")
    bug.log("Testing display function...")
    test_data = {
        "account_number": "123456789",
        "balance": 1000.50,
        "status": "active"
    }
    display(test_data)
    bug.success("Utils test complete.")
