from flask import Blueprint, jsonify, request
import MetaTrader5 as mt5
import logging
from flasgger import swag_from

order_bp = Blueprint('order', __name__)
logger = logging.getLogger(__name__)

@order_bp.route('/order', methods=['POST'])
@swag_from({
    'tags': ['Order'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'symbol': {'type': 'string'},
                    'volume': {'type': 'number'},
                    'type': {'type': 'string', 'enum': ['BUY', 'SELL']},
                    'price': {'type': 'number', 'description': 'Optional. If provided, a Pending Order (Limit/Stop) is placed automatically.'},
                    'deviation': {'type': 'integer', 'default': 20},
                    'magic': {'type': 'integer', 'default': 0},
                    'comment': {'type': 'string', 'default': ''},
                    'type_filling': {'type': 'string', 'enum': ['ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', 'ORDER_FILLING_RETURN']},
                    'sl': {'type': 'number'},
                    'tp': {'type': 'number'}
                },
                'required': ['symbol', 'volume', 'type']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Order executed successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'result': {'type': 'object'}
                }
            }
        },
        400: {'description': 'Bad request or order failed.'},
        500: {'description': 'Internal server error.'}
    }
})
def send_order_endpoint():
    """
    Send Smart Order (Market or Pending)
    ---
    description: Execute a Market Order (if no price) or a Smart Pending Order (if price is provided).
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Order data is required"}), 400

        required_fields = ['symbol', 'volume', 'type']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        # Get current market data (Needed for both Market and Smart Pending)
        tick = mt5.symbol_info_tick(data['symbol'])
        if tick is None:
            return jsonify({"error": f"Failed to get symbol info for {data['symbol']}"}), 400

        # --- LOGIC BRANCHING START ---
        
        # Check if user wants a specific price (Pending Order)
        target_price = data.get('price')
        
        request_data = {
            "symbol": data['symbol'],
            "volume": float(data['volume']),
            "deviation": data.get('deviation', 20),
            "magic": data.get('magic', 0),
            "comment": data.get('comment', ''),
            "type_time": mt5.ORDER_TIME_GTC, # Good Till Cancelled (Standard for Pending)
        }

        # Branch 1: SMART PENDING ORDER (Price is present)
        if target_price is not None:
            target_price = float(target_price)
            request_data["action"] = mt5.TRADE_ACTION_PENDING
            request_data["price"] = target_price
            
            # Pending orders usually require ORDER_FILLING_RETURN
            request_data["type_filling"] = mt5.ORDER_FILLING_RETURN

            # Determine Order Type (Limit vs Stop)
            if data['type'] == 'BUY':
                # Buying:
                # If Target < Market (Ask) -> LIMIT (Buy the dip)
                # If Target > Market (Ask) -> STOP (Buy the breakout)
                if target_price < tick.ask:
                    request_data["type"] = mt5.ORDER_TYPE_BUY_LIMIT
                else:
                    request_data["type"] = mt5.ORDER_TYPE_BUY_STOP
                    
            elif data['type'] == 'SELL':
                # Selling:
                # If Target > Market (Bid) -> LIMIT (Sell the top)
                # If Target < Market (Bid) -> STOP (Sell the breakdown)
                if target_price > tick.bid:
                    request_data["type"] = mt5.ORDER_TYPE_SELL_LIMIT
                else:
                    request_data["type"] = mt5.ORDER_TYPE_SELL_STOP
            else:
                return jsonify({"error": "Invalid order type (Must be BUY or SELL)"}), 400

        # Branch 2: LEGACY MARKET ORDER (No price)
        else:
            request_data["action"] = mt5.TRADE_ACTION_DEAL
            request_data["type_filling"] = data.get('type_filling', mt5.ORDER_FILLING_IOC)
            
            if data['type'] == 'BUY':
                request_data["type"] = mt5.ORDER_TYPE_BUY
                request_data["price"] = tick.ask
            elif data['type'] == 'SELL':
                request_data["type"] = mt5.ORDER_TYPE_SELL
                request_data["price"] = tick.bid
            else:
                return jsonify({"error": "Invalid order type"}), 400

        # --- LOGIC BRANCHING END ---

        # Add optional SL/TP if provided
        if 'sl' in data:
            request_data["sl"] = float(data['sl'])
        if 'tp' in data:
            request_data["tp"] = float(data['tp'])

        # Send order to MT5
        result = mt5.order_send(request_data)
        
        if result is None:
             return jsonify({"error": "Order send failed (Unknown error)"}), 500

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_code, error_str = mt5.last_error()
            
            return jsonify({
                "error": f"Order failed: {result.comment}",
                "mt5_error": error_str,
                "mt5_retcode": result.retcode,
                "request_sent": request_data,
                "result": result._asdict()
            }), 400

        return jsonify({
            "message": "Order executed successfully",
            "request_type": "PENDING" if target_price else "MARKET",
            "result": result._asdict()
        })
    
    except Exception as e:
        logger.error(f"Error in send_order_endpoint: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
