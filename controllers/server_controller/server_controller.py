from controller import Supervisor
import socket
import threading
import uuid
import math

GOALIE_X_POSITION = 4.5  # The starting x position of the goalie robot
ROBOT_X_POSITION = 2.5 # The starting x position of the robots
ROBOT_Z_POSITION = 0.333 # The starting z position of the robots represents the height

class Team:
    def __init__(self, team_number = 0, capacity = 0):
        self.players = set()
        self.team_lock = threading.Lock()
        self.capacity = capacity
        self.team_number = team_number

    def __len__(self):
        """Return the number of players in the team"""
        return len(self.players)
    
    def add_player(self, player):
        """Add a player to the team"""
        with self.team_lock:
            if len(self.players) < self.capacity:
                self.players.add(player)

    def remove_player(self, player):
        """Remove a player from the team"""
        with self.team_lock:
            self.players.discard(player)

    def get_players(self):
        """Get all players from the team"""
        return list(self.players)
    
    def get_team_strategy(self, state, ball):
        """Decide the role for each player"""
        return None
    
    def get_team_number(self):
        """Get the team number"""
        return self.team_number
    
    def has(self, player_id):
        """Returns true if player is in the team else false"""
        return player_id in self.players
    
class GameServer(Supervisor):
    def __init__(self, players_limit = 6):
        if players_limit < 2:
            print("⚠️ Minimum player size is 2.")
            players_limit = 2
        elif players_limit > 8:
            print("⚠️ Minimum player size is 8.")
            players_limit = 8
        super().__init__() # Initialize as a supervisor so it has access to objects in the world
        self.players_limit = players_limit
        self.client_lock = threading.Lock()
        self.clients = {} # Store player id to their connections
        self.team1 = Team(1, players_limit // 2)
        self.team2 = Team(2, players_limit // 2)
        self.player_states = {}  # Store player game stats
        self.players = {} # Store the reference to the robots
        self.ball = self.getFromDef("BALL") # Get the soccer ball in the world
        self.last_ball_position = [0, 0, 0]
        self.game_started = False

    def start_server(self, host, port):
        """Starts the server and wait for connections"""
        print("🔄 Starting server...")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((host, port))
            server.listen(self.players_limit)
            print(f"✅ Server started on {host}:{port}")
        except ConnectionError as error:
            print(f"⚠️ Error binding server: {error}")
            return
        while True:
            try:
                connection, address = server.accept()
                self.handle_client_connection(connection, address)
                thread = threading.Thread(
                    target=self.listen_for_client, args=(connection,)
                )
                thread.start()
            except Exception as e:
                print(f"⚠️ Error while accepting connection: {e}")
                break

    def listen_for_client(self, connection):
        """Listens for incoming messages from clients"""
        try:
            buffer = ""  # Buffer to store the message
            while True:
                data = connection.recv(1024)
                if not data:
                    print("⚠️ Client disconnected from server.")
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    message, buffer = buffer.split("\n", 1)
                    self.handle_message(message)
        except Exception as error:
            print(f"⚠️ Client error: {error}")
        finally:
            self.remove_client(connection)

    def handle_message(self, message):
        """Handles messages from the clients"""
        message_parts = message.split("|")
        message_type = message_parts[0]
        sender = message_parts[1]
        match message_type:
            case "POS":
                # Update the position of the client and broadcast it to every other clients
                x_position, y_position = float(message_parts[2]), float(message_parts[3])
                angle = float(message_parts[4])
                self.update_position(sender, x_position, y_position)
                self.update_rotation(sender, angle)
                self.broadcast(message + "\n", sender)
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
            case "ROBOT":
                self.players[sender] = self.getFromDef(message_parts[2]) # Add the robot reference
                # If all clients joined, then start the game by first assigning initial roles
                if len(self.players) == self.players_limit:
                    self.assign_initial_team_states(self.team1)
                    self.assign_initial_team_states(self.team2)
                    self.send_initial_states()
                    self.start_game()
            case _:
                print(message)
                print("Unknown Type.")

    def handle_client_connection(self, connection, address):
        """Handles new client connections and assigns the client a team and a unqiue identifer"""
        player_id = str(uuid.uuid4())
        print(f"🆔 New client connection: {player_id}, {address}.")

        # Add player to the clients list
        with self.client_lock:
            self.clients[player_id] = connection

        # Assign client a team
        if len(self.team1) <= len(self.team2):
            team_number = 1
            self.team1.add_player(player_id)
        else:
            team_number = 2
            self.team2.add_player(player_id)

        # Send previously connected robots the notice of newly connected client
        self.broadcast(f'INFO|{player_id}|{team_number}\n')

        # Send previously connected robots to the new client
        team1 = self.team1.get_players()
        team2 = self.team2.get_players()        
        for id in team1:
            if id != player_id:
                connection.sendall(f'INFO|{id}|1\n'.encode("utf-8"))
        for id in team2:
            if id != player_id:
                connection.sendall(f'INFO|{id}|2\n'.encode("utf-8"))
        print(f"📢 Clients connected: {len(self.clients)}")

    def send_initial_states(self):
        """Broadcasts the initial state of the game(players and ball)"""
        # Send the role and starting information to all the clients
        for player, details in self.player_states.items():
            role = details[0]
            x_position, y_position = details[2]
            angle = details[3]
            state_message = f'POS|{player}|{x_position}|{y_position}|{angle}\n'
            self.broadcast(state_message, player)
            role_message = f'ROLE|{player}|{role}\n'
            self.broadcast(role_message)
        # Send ball position to clients
        self.send_ball_position(True)

    def assign_initial_team_states(self, team):
        """Assigns starting states to players in a team"""
        players = team.get_players()
        team_number = team.get_team_number()
        x_position, angle = self.get_initial_x_position_and_rotation(team_number)
        y_position = self.calculate_player_y_position(0)

        # In the order of role, current action, xy coordinate, rotation, etc
        self.player_states[players[0]] = ["Striker", None, [x_position, y_position], angle]
        self.apply_player_state_in_simulation(players[0])

        if len(players) >= 2:
            goalie_x_position = -GOALIE_X_POSITION if team_number == 1 else GOALIE_X_POSITION
            self.player_states[players[1]] = ["Goalie",  None, [goalie_x_position, y_position], angle]
            self.apply_player_state_in_simulation(players[1])
            
            for i in range(2, len(players)):
                y_position = self.calculate_player_y_position(i)
                self.player_states[players[i]] = ["Midfielder", None, [x_position, y_position], angle]
                self.apply_player_state_in_simulation(players[i])

    def get_initial_x_position_and_rotation(self, team_number):
        """Returns the starting x position and rotation angle of the player based on team"""
        x = ROBOT_X_POSITION
        angle = 0
        if team_number == 1:
            x *= -1
        else:
            angle = math.pi
        return (x, angle)

    def calculate_player_y_position(self, player_index):
        """Finds the y position based on the index of the player"""
        y = player_index // 2
        return y if player_index % 2 == 0 else -y # If the index is even then the position will be on the right else it will be on the left

    def apply_player_state_in_simulation(self, player_id):
        """Updates the position and rotation of the robot"""
        player_state = self.player_states[player_id]
        robot = self.players[player_id]

        # Update the rotation
        rotation_field = robot.getField("rotation")
        rotation_field.setSFRotation([0, 0, 1, player_state[3]])

        # Update the position
        translation_field = robot.getField("translation")
        translation_field.setSFVec3f([player_state[2][0], player_state[2][1], ROBOT_Z_POSITION])

    def start_game(self):
        """Sends a start message to the players"""
        self.broadcast(f'START|1\n')
        self.game_started = True

    def is_player_near_ball(self, player_id, threshold = 0.5):
        """Checks if the player is close enough to the ball"""
        distance = self.player_distance_to_ball(player_id)
        return distance <= threshold
   
    def player_distance_to_ball(self, player_id):
        """Calculates the Euclidean distance from a player to the ball"""
        player_state = self.player_states[player_id]
        x_position, y_position = player_state[2], player_state[3]
        ball_position = self.ball.getPosition()
        return self.get_distance([x_position, y_position], ball_position)

    def send_ball_position(self, force = False):
        """Sends the current ball position to the clients"""
        ball_position = self.ball.getPosition()
        # If there is substanal change in the ball position or a force send
        if force or self.get_distance(ball_position, self.last_ball_position) > 0.1:
            self.last_ball_position = ball_position
            self.broadcast(f'BALL|{ball_position[0]:.2f}|{ball_position[1]:.2f}|{ball_position[2]:.2f}\n')

    def get_distance(self, point_one, point_two):
        """Returns the Euclidean distance between two points in xy-plane"""
        return math.sqrt((point_two[0] - point_one[0]) ** 2 + (point_two[1] - point_one[1]) ** 2)

    def update_position(self, player_id, x, y):
        """Updates the position of the player"""
        self.player_states[player_id][2] = [x, y]

    def update_rotation(self, player_id, angle):
        """Updates the rotation of the player"""
        self.player_states[player_id][3] = angle

    def remove_client(self, connection):
        """Removes disconnected clients"""
        with self.client_lock:
            for player_id, conn in self.clients.items():
                if conn == connection:
                    del self.clients[player_id]
                    self.team1.remove_player(player_id)
                    self.team2.remove_player(player_id)
                    print(f"❌ Removing player {player_id}")
                    break
        connection.close()

    def broadcast(self, message, sender = None):
        """Sends message to every client besides the sender"""
        for id, conn in self.clients.items():
            if id != sender:
                conn.sendall(message.encode("utf-8"))
    
    def update_roles_based_on_proximity(self):
        """Update roles: assign Striker to closest player to ball per team; others become Midfielders."""
        print("🧠 Role update check triggered.")
        team_roles = {1: [], 2: []}

        # Group player distances by team
        ball_position = self.ball.getPosition()
        for player_id, state in self.player_states.items():
            team = 1 if self.team1.has(player_id) else 2
            if state[0] != "Goalie":
                pos = state[2]
                distance = self.get_distance(pos, ball_position)
                team_roles[team].append((player_id, distance))

        for team, players in team_roles.items():
            if not players:
                continue

            # Sort by distance to ball
            players.sort(key=lambda x: x[1])
            closest_player = players[0][0]

            print(f"🔍 Team {team} - Closest to ball: {closest_player}")  

            # Assign roles
            for i, (player_id, _) in enumerate(players):
                new_role = "Striker" if player_id == closest_player else "Midfielder"
                if self.player_states[player_id][0] != new_role:
                    print(f"🔁 Changing {player_id} to {new_role}")
                    self.player_states[player_id][0] = new_role
                    self.broadcast(f"ROLE|{player_id}|{new_role}\n")
                    
                    last = self.last_roles.get(player_id)
                    if last != new_role:
                        if new_role == "Striker":
                            print(f"⚽ {player_id} is now the closest and becomes Striker.", flush=True)
                        else:
                            print(f"📥 {player_id} is no longer closest and becomes Midfielder.", flush=True)
                        self.last_roles[player_id] = new_role

host = "127.0.0.1"
port = 5555

# Start the server in a separate thread
game_server = GameServer(6)
server_thread = threading.Thread(target=game_server.start_server, args=(host, port,), daemon=True)
server_thread.start()

timestep = int(game_server.getBasicTimeStep())

# Webots main loop
while game_server.step(timestep) != 1:
    if game_server.game_started:
        game_server.send_ball_position()
        game_server.update_roles_based_on_proximity()
