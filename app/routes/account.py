from flask import Blueprint, jsonify
import MetaTrader5 as mt5
import logging
from flasgger import swag_from

account_bp = Blueprint('account', __name__)
logger = logging.getLogger(__name__)

@account_bp.route('/account', methods=['GET'])
@swag_from({
    'tags': ['Account'],
    'responses': {
        200: {
            'description': 'Account information retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'login': {'type': 'integer'},
                    'balance': {'type': 'number'},
                    'equity': {'type': 'number'},
                    'profit': {'type': 'number'},
                    'margin': {'type': 'number'},
                    'margin_free': {'type': 'number'},
                    'margin_level': {'type': 'number'},
                    'leverage': {'type': 'integer'},
                    'currency': {'type': 'string'},
                    'server': {'type': 'string'},
                    'company': {'type': 'string'},
                    'name': {'type': 'string'}
                }
            }
        },
        500: {
            'description': 'Failed to retrieve account info.'
        }
    }
})
def get_account_info():
    """
    Get Account Information
    ---
    description: Returns the current financial state of the trading account (Balance, Equity, Margin, etc.).
    """
    try:
        # Fetch account info from MT5
        account_info = mt5.account_info()

        if account_info is None:
            # If MT5 is not connected or fails
            error_code, error_str = mt5.last_error()
            return jsonify({
                "error": "Failed to retrieve account info",
                "mt5_error": error_str,
                "mt5_retcode": error_code
            }), 500

        # Convert the MT5 object to a dictionary so it can be JSONified
        result = account_info._asdict()

        return jsonify({
            "message": "Account info retrieved",
            "data": result
        })

    except Exception as e:
        logger.error(f"Error in get_account_info: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500