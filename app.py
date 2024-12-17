import os
from dotenv import load_dotenv
import boto3
from flask import Flask, request, jsonify, render_template
from threading import Lock
# Load environment variables
load_dotenv()


# Get environment variables
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
QUEUE_URL = os.getenv('QUEUE_URL')

# Flask app configuration
app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY

# AWS SQS client
sqs_client = boto3.client(
    "sqs",
    region_name="eu-north-1",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

messages = []  # List to store messages for polling
online_users = set()  # Store online users
lock = Lock()

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
#Addition of user in online users
def register_user():
    username = request.json.get("username")
    if username:
        with lock:
            online_users.add(username)
        return jsonify({"status": "success", "online_users": list(online_users)}), 200
    return jsonify({"status": "error", "message": "Invalid username"}), 400


@app.route("/send_message", methods=["POST"])
def send_message():
    sender = request.json.get("sender")
    receiver = request.json.get("receiver")
    message = request.json.get("message")

    if sender and receiver and message:
        room = f"{sender}-{receiver}" if sender < receiver else f"{receiver}-{sender}"

        # Store the message in memory
        with lock:
            messages.append({"room": room, "sender": sender, "message": message})

        # Optional: Send the message to SQS
        sqs_client.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=message,
            MessageAttributes={
                "room": {"DataType": "String", "StringValue": room},
                "sender": {"DataType": "String", "StringValue": sender},
            },
        )
        return jsonify({"status": "success"}), 200

    return jsonify({"status": "error", "message": "Invalid data"}), 400


@app.route("/fetch_messages", methods=["GET"])
def fetch_messages():
    room = request.args.get("room")
    if not room:
        return jsonify({"status": "error", "message": "Room not specified"}), 400

    with lock:
        # Get messages for the requested room
        room_messages = [msg for msg in messages if msg["room"] == room]

    return jsonify({"status": "success", "messages": room_messages}), 200


@app.route("/get_online_users", methods=["GET"])
def get_online_users():
    return jsonify({"status": "success", "online_users": list(online_users)}), 200


if __name__ == "__main__":
    app.run()
