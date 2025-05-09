import socket
import threading
import math
from Nao import Nao

GOALIE_X_POSITION = 4.5
MIDFIELDER_DISTANCE = 1


class SoccerRobot(Nao):
    def __init__(self):
        super().__init__()
        self.my_team = set()
        self.opponent_team = set()
        self.ball_position = [0, 0, 0]
        self.player_states = {}  # Store player positions and role status
        self.sock = None
        self.team_number = None
        self.player_id = None
        self.state = None
        self.role = None
        self.target_position = [0, 0]  # The position the robot is heading towards
        self.target_rotation = [0, 0]  # The rotation the robot is targeting
        self.start_time = 0
        self.setup_time = math.inf  # The delay needed for physics calculations
        self.last_state = None
        self.last_position = [0, 0]
        self.last_rotation = 0
        self.recovery_mode = False

    def connect_to_server(self, host, port):
        """Establishes a connection to the game server and sends its GPS position"""
        print("🔄 Attempting to connect to server...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((host, port))
            client_thread = threading.Thread(target=self.listen_for_server)
            client_thread.start()
            print("✅ Successfully connected to server.")
        except Exception as error:
            print(f"⚠️ Connection to server failed: {error}")

    def listen_for_server(self):
        """Listen to messages from the server"""
        try:
            buffer = ""  # Buffer to store the message
            while True:
                data = self.sock.recv(1024)
                if not data:
                    print("⚠️ Disconnected from server.")
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    message, buffer = buffer.split("\n", 1)
                    self.handle_message(message)
        except Exception as error:
            print(f"⚠️ Communication error: {error}")
        finally:
            print(f"Client {self.player_id} closing connection with server.")
            self.sock.close()

    def handle_message(self, message):
        """Handles messages from the server"""
        message_parts = message.split("|")
        message_type = message_parts[0]

        match message_type:
            case "STATE":
                # Message details
                player_id = message_parts[1]
                state = message_parts[2]
                x_position, y_position = float(message_parts[3]), float(
                    message_parts[4]
                )
                angle = float(message_parts[5])

                # Update the position and rotation of the players
                if player_id == self.player_id:
                    print("🔄 Reset robot position")
                    self.state = None  # Resume normal behavior
                else:
                    self.update_state(player_id, state)
                    self.update_position(player_id, x_position, y_position)
                    self.update_rotation(player_id, angle)
            case "BALL":
                x_position, y_position, z_position = (
                    float(message_parts[1]),
                    float(message_parts[2]),
                    float(message_parts[3]),
                )
                self.update_ball_position(x_position, y_position, z_position)
            case "ROLE":
                player_id = message_parts[1]
                role = message_parts[2]
                if player_id == self.player_id:
                    self.role = role
                    print(f"📢 Assigned Role: {self.role}")
                else:
                    self.player_states[player_id][0] = role
            case "REVERT":
                self.create_delay(
                    float(message_parts[1])
                )  # Revert comes as a penalty for network delay
            case "RESET":
                self.recovery_mode = True
            case "INFO":
                player_id = message_parts[1]
                # Set player information
                if not self.player_id:
                    self.player_id = player_id
                    robot_name = self.getName()
                    robot_number = robot_name.split("_")[1]
                    self.team_number = int(robot_number) % 2 + 1
                    message = f"ROBOT|{self.player_id}|{robot_name}|{self.team_number}"
                    self.send_message(message)
                    print(
                        f"🆔 Player ID: {self.player_id} is in team {self.team_number}"
                    )
                else:
                    # Set up player default state
                    team_number = int(message_parts[2])
                    self.player_states[player_id] = [None, "None", [0, 0], 0]
                    if team_number == self.team_number:
                        self.my_team.add(player_id)
                        print(f"📢 New teammate: {player_id}")
                    else:
                        self.opponent_team.add(player_id)
                        print(f"📢 New opponent: {player_id}")
            case "START":
                self.create_delay(float(message_parts[1]))
            case _:
                print(f"❓ Unknown message type: {message}")

    def determine_action(self):
        """Determine what to do based on role and current game state"""
        if not self.is_motion_over():
            return
        # If the robot has fallen then ensure it is getting up first
        if self.has_fallen():
            self.play_standup_motion()
            self.state = "Recovering"
            return
        if self.state == "Recovering" or self.state == "Kicking":
            self.state = None
        if self.recovery_mode:
            # Once in recovery mode and stable, send acknowledge to server
            self.setup_time = math.inf
            message = f"ACK|{self.player_id}"
            self.send_message(message)
            self.recovery_mode = False
            return
        match self.role:
            case "Goalie":
                self.determine_goalie_action()
            case "Striker":
                self.determine_striker_action()
            case "Midfielder":
                self.determine_midfielder_action()
            case _:
                print(f"⚠️ Role not recognized: {self.role}")
        if self.state == "Moving":
            self.move_to_position(self.target_position)
        elif self.state == "Turning":
            self.turn_to_direction(self.target_rotation, moveAfterTurn=True)
        elif self.state == "Sliding":
            self.side_step_to_position(self.target_position[1])
        elif self.state == "Backing":
            self.back_up(self.target_position[0])

    def determine_goalie_action(self, threshold=0.1):
        """Determine what to do as the goalie"""
        # If the ball is far from goal the goalie should just stay along the x axis of the goal
        position = self.get_position()
        ball_x_position, ball_y_position, _ = self.ball_position
        if abs(ball_x_position - position[0]) < 4:
            # Goalie should be facing towards the other team goal
            target_direction = [1, 0] if self.team_number == 1 else [-1, 0]
            if self.turn_to_direction(target_direction, 20):
                return

            # If the robot is in front of the ball, the robot should move back
            goalie_x_axis = (
                -GOALIE_X_POSITION if self.team_number == 1 else GOALIE_X_POSITION
            )
            if not self.is_ball_ahead(ball_x_position, position[0], 0.1):
                self.target_position[0] = goalie_x_axis
                self.state = "Backing"
            # Move the robot in front of the ball
            elif abs(ball_y_position - position[1]) > threshold:
                self.slide_to_y_position(ball_y_position, -1, 1)
            # Move the robot towards the ball
            elif (
                self.get_distance(
                    [ball_x_position, ball_y_position], [goalie_x_axis, position[1]]
                )
                < 1
            ):
                self.go_to(ball_x_position, ball_y_position, threshold)
                # Kick the ball if the robot stopped moving
                if not self.state:
                    self.state = "Kicking"
                    self.play_kick_ball()

    def determine_striker_action(
        self, threshold=0.2, alignment_threshold=0.8, offset=0.35
    ):
        """Determine what to do as the striker"""
        # Player with role Striker should head towards the ball if it is far away
        if self.distance_to_ball() > threshold * 3:
            self.go_to(self.ball_position[0], self.ball_position[1])
            return

        # Find the direction from the ball to the goal and the ball to the robot
        target_goal = GOALIE_X_POSITION if self.team_number == 1 else -GOALIE_X_POSITION
        x_position, y_position, _ = self.get_position()
        ball_to_goal_direction = self.normalize_vector(
            [target_goal - self.ball_position[0], -self.ball_position[1]]
        )
        ball_to_robot_direction = self.normalize_vector(
            [x_position - self.ball_position[0], y_position - self.ball_position[1]]
        )
        dot_product = (
            ball_to_goal_direction[0] * ball_to_robot_direction[0]
            + ball_to_goal_direction[1] * ball_to_robot_direction[1]
        )

        # If the dot product is close to -1 then it means the robot is behind the ball and reasonably aligned
        if dot_product < -alignment_threshold:
            self.go_to(self.ball_position[0], self.ball_position[1])
            # Kick the ball if the robot stopped moving
            if not self.state:
                self.state = "Kicking"
                self.play_kick_ball()
        elif dot_product > alignment_threshold:
            # If the dot product is close to 1 then it means the robot is in front of the ball and must reposition
            point_one, point_two = self.get_rotated_points(
                ball_to_goal_direction, self.ball_position, 120
            )
            dist_one = self.get_distance(point_one, [x_position, y_position])
            dist_two = self.get_distance(point_two, [x_position, y_position])
            best_target = point_one if dist_one < dist_two else point_two
            self.go_to(best_target[0], best_target[1])
        else:
            # The robot is not along the target direction so it should move to a position behind the ball
            x_target = self.ball_position[0] - ball_to_goal_direction[0] * offset
            y_target = self.ball_position[1] - ball_to_goal_direction[1] * offset
            self.go_to(x_target, y_target)

    def determine_midfielder_action(self):
        """Determine what to do as midfielder"""
        sections = {"negative": -MIDFIELDER_DISTANCE, "positive": MIDFIELDER_DISTANCE}
        striker_count = 0
        midfielder_position = None
        # Extract the position of the striker and the other midfielder in the team
        for player_id in self.my_team:
            player_role = self.player_states[player_id][0]
            position = self.player_states[player_id][2]
            if player_role == "Striker":
                striker_count += 1
            elif player_role == "Midfielder":
                midfielder_position = position
        # Changes in the roles might have delay which can cause inconsistency so actions should be skipped until states are consistent
        if striker_count != 1:
            print(striker_count)
            return

        x_position, y_position, _ = self.get_position()
        ball_x_position, ball_y_position, _ = self.ball_position
        # Section allocation depends on both midfielders when there's 4 players on each team
        if len(self.my_team) == 4:
            for offset in sections.values():
                target_y_position = ball_y_position + offset
                robot_distance = self.get_distance(
                    [ball_x_position, target_y_position], [x_position, y_position]
                )
                midfielder_distance = self.get_distance(
                    [ball_x_position, target_y_position], midfielder_position
                )
                if robot_distance < midfielder_distance:
                    self.go_to(ball_x_position, target_y_position)
        else:
            # With only one midfielder, the player should only consider the closet support position
            offset = min(
                sections.items(),
                key=lambda item: abs(y_position - (ball_y_position + item[1])),
            )[1]
            self.go_to(ball_x_position, ball_y_position + offset)

    def has_fallen(self, force_threshold=5):
        """Determines if the robot has fallen using foot pressure sensors"""
        """
        Skips fall detection until the setup time has passed and the current motion is complete.
        When robots are repositioned using the Supervisor, their foot sensors may temporarily 
        report low values due to incomplete contact with the ground. This delay allows the 
        physics engine to settle the robot and ensures foot sensors register proper ground contact.
        """
        if not self.is_motion_over() or not self.is_setup_time_over():
            return False

        fsv = []  # Force sensor values
        fsv.append(self.fsr[0].getValues())  # Left foot
        fsv.append(self.fsr[1].getValues())  # Right foot

        # Compute total force on each foot
        newtonsLeft = sum(
            [
                fsv[0][2] / 3.4 + 1.5 * fsv[0][0] + 1.15 * fsv[0][1],  # Left Front Left
                fsv[0][2] / 3.4
                + 1.5 * fsv[0][0]
                - 1.15 * fsv[0][1],  # Left Front Right
                fsv[0][2] / 3.4 - 1.5 * fsv[0][0] - 1.15 * fsv[0][1],  # Left Rear Right
                fsv[0][2] / 3.4 - 1.5 * fsv[0][0] + 1.15 * fsv[0][1],  # Left Rear Left
            ]
        )

        newtonsRight = sum(
            [
                fsv[1][2] / 3.4
                + 1.5 * fsv[1][0]
                + 1.15 * fsv[1][1],  # Right Front Left
                fsv[1][2] / 3.4
                + 1.5 * fsv[1][0]
                - 1.15 * fsv[1][1],  # Right Front Right
                fsv[1][2] / 3.4
                - 1.5 * fsv[1][0]
                - 1.15 * fsv[1][1],  # Right Rear Right
                fsv[1][2] / 3.4 - 1.5 * fsv[1][0] + 1.15 * fsv[1][1],  # Right Rear Left
            ]
        )

        total_force = newtonsLeft + newtonsRight
        if total_force < force_threshold:
            print(f"⚠️ Robot has fallen! Total force: {total_force:.2f}N")
            return True
        # print(f"Robot is standing. Total force: {total_force:.2f}N")
        return False

    def send_player_state(self, force=False):
        """Sends position, rotation, and state to the server"""
        position, angle = self.get_position(), self.get_rotation()[2]
        if (
            force
            or self.get_distance(position, self.last_position) > 0.25
            or abs(self.calculate_angle_difference(angle, self.last_rotation))
            > math.radians(10)
            or self.state != self.last_state
        ):
            state = self.state if self.state else "Idle"
            message = f"STATE|{self.player_id}|{state}|{position[0]:.3f}|{position[1]:.3f}|{angle:.3f}"
            self.send_message(message)
            self.last_position = [position[0], position[1]]
            self.last_rotation = angle
            self.last_state = self.state

    def go_to(self, x_position, y_position, threshold=0.15):
        """Function to tell the robot to go a certain position"""
        self.set_target_position(x_position, y_position)
        position = self.get_position()
        # If the robot reached the target position then stop moving
        distance = self.get_distance(position, self.target_position)
        if distance < threshold:
            self.state = None
            return

        # Turn before moving
        x_current, y_current = position[0], position[1]
        direction = self.normalize_vector(
            [x_position - x_current, y_position - y_current]
        )
        if self.turn_to_direction(direction):
            self.start_turn(direction)
        else:
            self.state = "Moving"

    def move_to_position(self, target_position, threshold=0.15):
        """Move the robot to the target position"""
        x_position, y_position, _ = self.get_position()
        # If the robot reached the target position then stop moving
        distance = self.get_distance([x_position, y_position], target_position)
        if distance < threshold:
            self.state = None
            return True

        # Before moving again, ensure robot direction is correct
        direction = self.normalize_vector(
            [target_position[0] - x_position, target_position[1] - y_position]
        )
        if self.turn_to_direction(direction, moveAfterTurn=True):
            self.start_turn(direction)
            return False
        # Take small steps when it is close else large steps
        if distance < threshold * 3:
            self.start_motion(self.smallForwards)
        else:
            self.start_motion(self.largeForwards)
        return False

    def turn_to_direction(self, direction, threshold=35, moveAfterTurn=False):
        """Turn the robot towards the target direction"""
        angle_difference = self.get_turn_angle(direction)
        # Positive angle indicates a left turn and negative angle indicates a right turn
        if abs(angle_difference) < math.radians(threshold):
            if moveAfterTurn:
                self.stop_turn_and_start_moving()
            else:
                self.state = None
            return False  # Return false for no turning needed

        self.start_motion(self.turnLeft40 if angle_difference > 0 else self.turnRight40)
        return True

    def slide_to_y_position(
        self, y_position, lower_y_threshold=-math.inf, upper_y_threshold=math.inf
    ):
        """Slide the robot to a certain y position"""
        clamped_pos = max(lower_y_threshold, min(upper_y_threshold, y_position))
        self.target_position[1] = clamped_pos
        self.state = "Sliding"

    def side_step_to_position(self, y_position, threshold=0.1):
        """Move the robot using side step motions"""
        y_current = self.get_position()[1]
        difference = y_position - y_current
        # If the robot reached the target position then stop moving
        if abs(difference) < threshold:
            self.state = None
            return

        # Move the robot
        if self.team_number == 1:
            motion = self.sideStepLeft if difference > 0 else self.sideStepRight
        else:
            motion = self.sideStepRight if difference > 0 else self.sideStepLeft
        self.start_motion(motion)

    def back_up(self, target, threshold=0.1):
        """Makes the robot back up"""
        x_position = self.get_position()[0]
        if abs(target - x_position) < threshold:
            self.state = None
            return
        self.start_motion(self.backwards)

    def is_ball_ahead(self, ball_x, robot_x, min_distance=0.15):
        """Determine whether the ball is in front of behind the player using the x coordinate value"""
        return (
            ball_x - robot_x > min_distance
            if self.team_number == 1
            else robot_x - ball_x > min_distance
        )

    def normalize_vector(self, vector):
        """Normalizes a vector"""
        norm = math.sqrt(sum(val**2 for val in vector))
        return [v / norm for v in vector] if norm != 0 else vector

    def get_distance(self, point_one, point_two):
        """Returns the Euclidean distance between two points in xy-plane"""
        return math.sqrt(
            (point_two[0] - point_one[0]) ** 2 + (point_two[1] - point_one[1]) ** 2
        )

    def get_turn_angle(self, direction):
        """Find the angle to turn to within [-pi, pi]"""
        current_angle = self.get_rotation()[2]
        target_angle = math.atan2(direction[1], direction[0])
        return self.calculate_angle_difference(current_angle, target_angle)

    def calculate_angle_difference(self, angle1, angle2):
        """Returns the angular difference in radians between two angles"""
        return (angle2 - angle1 + math.pi) % (2 * math.pi) - math.pi

    def find_rotated_vector(self, vector, angle):
        """Find the rotated vector after applying a rotation"""
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        x, y = vector
        return [x * cos_a - y * sin_a, x * sin_a + y * cos_a]

    def get_rotated_points(self, direction, origin_point, angle_degree, distance=0.5):
        """Returns two points rotated from the given direction vector by angle_deg offset from the origin_point by the specified distance"""
        # Rotate direction vector by ±angle
        radians = math.radians(angle_degree)
        rotated_left = self.find_rotated_vector(direction, radians)
        rotated_right = self.find_rotated_vector(direction, -radians)

        # Scale by distance and offset from origin
        left_point = [
            origin_point[0] + rotated_left[0] * distance,
            origin_point[1] + rotated_left[1] * distance,
        ]
        right_point = [
            origin_point[0] + rotated_right[0] * distance,
            origin_point[1] + rotated_right[1] * distance,
        ]
        return [left_point, right_point]

    def stop_turn_and_start_moving(self):
        """Stops the current turning motion and transitions the robot to the moving state"""
        self.stop_motion()
        self.state = "Moving"

    def start_turn(self, direction):
        """Starts and set up the turning"""
        self.target_rotation = direction
        self.state = "Turning"

    def set_target_position(self, x_position, y_position):
        """Set a target position"""
        self.target_position = [float(x_position), float(y_position)]

    def distance_to_ball(self):
        """Calculates the Euclidean distance from the player to the ball"""
        position = self.get_position()
        return self.get_distance(position, self.ball_position)

    def update_state(self, player_id, state):
        """Updates the state of the player"""
        self.player_states[player_id][1] = state

    def update_position(self, player, x, y):
        """Update the position of the player"""
        self.player_states[player][2] = [x, y]

    def update_rotation(self, player, angle):
        """Update the rotation of the player"""
        self.player_states[player][3] = angle

    def update_ball_position(self, x, y, z):
        """Update the position of the ball"""
        self.ball_position[0] = x
        self.ball_position[1] = y
        self.ball_position[2] = z

    def send_message(self, message, delay_tolerance=0.5):
        """Send messages with the time and delay allowed"""
        self.sock.sendall(
            f"{message}|{self.getTime()}|{delay_tolerance}\n".encode("utf-8")
        )

    def create_delay(self, duration):
        """
        Adds a delay to the robot's motion or physics update system.

        If no delay is currently active, starts a new one. Otherwise,
        stacks the new delay onto the remaining active delay duration.

        Args:
            float: Time in seconds to delay.
        """
        if self.is_setup_time_over() or self.setup_time == math.inf:
            # No active delay, start a new one
            self.start_time = self.getTime()
            self.setup_time = duration
        else:
            # Stack the new delay onto the current remaining time
            self.setup_time += duration

    def is_setup_time_over(self):
        """
        Checks if the current setup delay period has elapsed.

        Returns:
            bool: True if the delay has ended, False if still active.
        """
        return self.getTime() >= self.start_time + self.setup_time

    def is_motion_over(self):
        """
        Checks if the currently playing motion has finished.

        Returns:
            bool: True if no motion is playing or the motion has ended.
        """
        return not self.currentlyPlaying or self.currentlyPlaying.isOver()


host = "127.0.0.1"
port = 5555

soccer_robot = SoccerRobot()
timeStep = soccer_robot.timeStep

soccer_robot.step(timeStep)  # Wait for the game server to be up

client_thread = threading.Thread(
    target=soccer_robot.connect_to_server,
    args=(
        host,
        port,
    ),
)
client_thread.start()

# Webots main loop
while soccer_robot.step(timeStep) != -1:
    if soccer_robot.is_setup_time_over():
        soccer_robot.determine_action()
        soccer_robot.send_player_state()
