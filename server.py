from flask import Flask, request, jsonify

app = Flask(__name__)

# Store sensor value
sensor_data = {
    "temp": None,
    "hum": None,
    "light": None,
    "move" : None
}

@app.route('/update', methods=['POST'])
def update_sensor():
    data = request.json  # Expect JSON data
    if not data:
        return jsonify({"error": "No JSON data received"}), 400

    # Update sensor_data dict with any keys sent
    for key in sensor_data.keys():
        if key in data:
            sensor_data[key] = data[key]

    return jsonify({"message": "Data updated successfully", "data": sensor_data})

@app.route('/data', methods=['GET'])
def get_data():
    # Return latest sensor values
    return jsonify(sensor_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
