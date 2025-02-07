from flask import Flask, request, jsonify
import pandas as pd
from datetime import datetime

user_dict = {
    "1": {"area": "Area1", "region": "Region1", "dwelling_type": "Apartment", "username": "user1", "meter_id": "1"},
    "2": {"area": "Area2", "region": "Region2", "dwelling_type": "House", "username": "user2", "meter_id": "2"},
    "3": {"area": "Area3", "region": "Region3", "dwelling_type": "Apartment", "username": "user3", "meter_id": "3"}
}
raw_data = pd.DataFrame(columns=['meter_id', 'area', 'region', 'dwelling_type', 'username', 'timestamp', 'reading'])

app = Flask(__name__)

@app.route('/meter/reading', methods=['POST'])
def receive_reading():
    global user_dict
    global raw_data
    try:
        receive_data = request.get_json()
        timestamp = receive_data['timestamp']
        reading = receive_data['reading']
        meter_id = receive_data['meter_id']

        if meter_id not in user_dict:
            return jsonify({'status': 'error', 'message': 'Invalid meter_id'}), 400

        raw_data.loc[len(raw_data)] = [
            meter_id,
            user_dict[meter_id]['area'],
            user_dict[meter_id]['region'],
            user_dict[meter_id]['dwelling_type'],
            user_dict[meter_id]['username'],
            timestamp,
            reading
        ]
        print(raw_data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
