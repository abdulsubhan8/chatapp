import boto3
from flask import Flask, render_template, request ,send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import threading

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")

# AWS SQS Configuration
sqs_client= boto3.client(
    "sqs",
    region_name="eu-north-1",
    aws_access_key_id='AKIAWMFUPNPZFR6X5BMY',
    aws_secret_access_key='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'
)
QUEUE_URL = "https://sqs.eu-north-1.amazonaws.com/438465162226/User1_User2_Queue"

# In-memory storage for user management
online_users = {}  # {username: sid (socket id)}
active_rooms = {}  # {room_name: [user1, user2]}
user_room_map = {}  # {username: room_name}


@app.route("/")
def serve_frontend():
    return render_template("index.html")


@socketio.on("connect")
def on_connect():
    print("A user connected.")


@socketio.on("disconnect")
def on_disconnect():
    username = None
    for user, sid in online_users.items():
        if sid == request.sid:
            username = user
            break

    if username:
        online_users.pop(username)
        room = user_room_map.get(username)
        if room:
            active_rooms[room].remove(username)
            if not active_rooms[room]:  # If room is empty, delete it
                del active_rooms[room]
            del user_room_map[username]
        emit("user_list", list(online_users.keys()), broadcast=True)
        print(f"{username} disconnected.")


@socketio.on("register")
def register_user(data):
    username = data["username"]
    online_users[username] = request.sid
    emit("user_list", list(online_users.keys()), broadcast=True)


@socketio.on("start_chat")
def start_chat(data):
    sender = data["sender"]
    receiver = data["receiver"]
    room = f"{sender}-{receiver}" if sender < receiver else f"{receiver}-{sender}"

    if room not in active_rooms:
        active_rooms[room] = [sender, receiver]
        user_room_map[sender] = room
        user_room_map[receiver] = room

    join_room(room)
    emit("chat_started", {"room": room, "users": [sender, receiver]}, to=request.sid)
    emit("chat_started", {"room": room, "users": [sender, receiver]}, to=online_users[receiver])


@socketio.on("message")
def handle_message(data):
    username = data["username"]
    room = user_room_map.get(username)
    message = data["message"]

    if room:
        # Send message to SQS
        sqs_client.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=message,
            MessageAttributes={
                "room": {"DataType": "String", "StringValue": room},
                "username": {"DataType": "String", "StringValue": username},
            },
        )
        # Broadcast message
        send(f"{username}: {message}", to=room)

# Start background thread for SQS polling
# threading.Thread(target=receive_sqs_messages, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080)

