from flask import Flask, request, jsonify
import threading
import long_running_task

app = Flask(__name__)

@app.route('/webhook', defined methods=['POST'])
def receive_webhook():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Start the processing in the background
    thread = threading.Thread(target=long_running_task.run, args=(data,))
    thread.start()
    
    return jsonify({"status": "success", "message": "Task started"}), 202

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
