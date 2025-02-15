from controller import Robot
import socket
import threading
import uuid

host = "127.0.0.1"
port = 5555
clients = {}
team1 = set()
team2 = set()

# Start the server and awaits for connections
def start_server():
  print("Starting server...")
  server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  server.bind((host, port))
  server.listen()
  print(f"Server started on {host}:{port}!")
  while True:
    connection, address = server.accept()
    handle_client_connection(connection, address)
    thread = threading.Thread(target=handle_client_communication, args=(connection, address))
    thread.start()

# Handles connection of clients with the server
def handle_client_connection(connection, address):
  # Generate a unique id for client 
  player_id = str(uuid.uuid4())
  print(f"New client connection: {player_id}, {address}.")
  # Add player to a team
  clients[player_id] = connection
  if len(team1) < len(team2):
    team_number = 1
    team1.add(player_id)
  else:
    team_number = 2
    team2.add(player_id)
  # Send player id and team number to the client and broadcast this to other clients
  connection.sendall(f"SETUP|{team_number}|{player_id}".encode("utf-8"))
  broadcast(f"ADD|{team_number}|{player_id}", player_id)

# Handles communication with clients
def handle_client_communication(connection, address):
  try:
    while True:
      data = connection.recv(1024)
      if not data:
        print(f"Client {address} disconnected.")
        break
      message = data.decode("utf-8")
      print(f"Received from {address}: {message}")
      handle_message(message, connection)
  except ConnectionResetError:
    print(f"Client {address} forcibly closed the connection.")
  except Exception as e:
    print(f"Error with {address}: {e}")
  finally:
    player_id = None
    for id, conn in clients.items():
      if conn == connection:
        player_id = id
        break
    if player_id:
      del clients[player_id]
      team1.discard(player_id)
      team2.discard(player_id)
    connection.close()

# Handle messages from clients
def handle_message(message, sender):
  message_parts = message.split("|")
  message_type = message_parts[0]
  sender_id = message_parts[1]
  match message_type:
    case "ACK":
      print("Acknowledgement.")
    case "MOVE":
      print("Moving.")
      #position = message_parts[1]
      #broadcast(f"MOVE|{sender}|{position}", sender)
    case "GOAL":
      print("Scored a goal.")
      #broadcast(f"GOAL|{sender}")
    case "KICK":
      print("Ball kick.")
      #broadcast(f"KICK|{sender}")
    case "GET":
      print("Requesting information.")
      #sender.sendall("Data".encode("utf-8"))
    case _:
      print("Unknown Type.")

# Sends message to every client besides the sender
def broadcast(message, sender=None):
  for id, conn in clients.items():
    if id != sender:
      conn.sendall(message.encode("utf-8"))

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

robot = Robot()
timestep = int(robot.getBasicTimeStep())

# Webots main loop
while robot.step(timestep) != 1:
  pass