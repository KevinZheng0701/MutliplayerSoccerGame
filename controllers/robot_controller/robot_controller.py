from controller import Robot, Motion
import socket
import threading
import math
from collections import deque

class Nao(Robot):
    PHALANX_MAX = 8

    def __init__(self):
        Robot.__init__(self)
        self.currentlyPlaying = False
        self.load_motion_files()
        self.find_and_enable_devices()

    def load_motion_files(self):
        """Load motion files for the robot"""
        self.handWave = Motion("../../motions/HandWave.motion")
        self.largeForwards = Motion("../../motions/Forwards50.motion")
        self.smallForwards = Motion("../../motions/Forwards.motion")
        self.backwards = Motion("../../motions/Backwards.motion")
        self.shoot = Motion("../../motions/Shoot.motion")
        self.sideStepLeft = Motion("../../motions/SideStepLeft.motion")
        self.sideStepRight = Motion("../../motions/SideStepRight.motion")
        self.standupFromFront = Motion("../../motions/StandUpFromFront.motion")
        self.standupFromBack = Motion("../../motions/StandUpFromBack.motion")
        self.turnLeft40 = Motion("../../motions/TurnLeft40.motion")
        self.turnLeft60 = Motion("../../motions/TurnLeft60.motion")
        self.turnRight40 = Motion("../../motions/TurnRight40.motion")
        self.turnRight60 = Motion("../../motions/TurnRight60.motion")
        self.turn180 = Motion("../../motions/TurnLeft180.motion")
        self.taiChi = Motion("../../motions/TaiChi.motion")

    def start_motion(self, motion):
        """Starts a robot motion"""
        # Interrupt current motion
        if self.currentlyPlaying and self.currentlyPlaying != motion:
            self.currentlyPlaying.stop()
        # Start new motion
        motion.play()
        self.currentlyPlaying = motion

    def stop_motion(self):
        """Stops the currently playing motion and resets the motion state"""
        if self.currentlyPlaying:
            self.currentlyPlaying.stop()
        self.currentlyPlaying = False

    def play_standup_motion(self):
        """Play the standup motion"""
        self.start_motion(self.standupFromBack)

    def play_kick_ball(self):
        """Play the kick motion"""
        self.start_motion(self.shoot)

    def get_acceleration(self):
        """Get the current acceleration"""
        return self.accelerometer.getValues()

    def print_acceleration(self):
        """Prints the current acceleration of the robot"""
        # The accelerometer axes are oriented as on the real robot however the sign of the returned values may be opposite
        acc = self.get_acceleration()
        print("----------accelerometer----------")
        print("acceleration: [ x y z ] = [%f %f %f]" % (acc[0], acc[1], acc[2]))

    def get_velocity(self):
        """Get the current velocity"""
        return self.gyro.getValues()

    def print_gyro(self):
        """Prints the current velocity of the robot"""
        # The gyro axes are oriented as on the real robot however the sign of the returned values may be opposite
        vel = self.get_velocity()
        print("----------gyro----------")
        print(
            "angular velocity: [ x y ] = [%f %f]" % (vel[0], vel[1])
        )  # Z value is meaningless due to the orientation of the Gyro

    def get_position(self):
        """Get the position of the robot"""
        return self.gps.getValues()

    def print_gps(self):
        """Prints the current position of the robot"""
        pos = self.get_position()
        print("----------gps----------")
        print("position: [ x y z ] = [%f %f %f]" % (pos[0], pos[1], pos[2]))

    def get_rotation(self):
        """Get the rotation of the robot"""
        return self.inertialUnit.getRollPitchYaw()

    def print_inertial_unit(self):
        """Prints the current rotation of the robot"""
        # The InertialUnit roll/pitch angles are equal to naoqi's AngleX/AngleY
        rpy = self.get_rotation()
        print("----------inertial unit----------")
        print("roll/pitch/yaw: [%f %f %f]" % (rpy[0], rpy[1], rpy[2]))

    def print_foot_sensors(self):
        """Prints the forces on the foot sensors"""
        fsv = []  # Force sensor values
        fsv.append(self.fsr[0].getValues())
        fsv.append(self.fsr[1].getValues())
        left, right = [], []
        newtonsLeft, newtonsRight = 0, 0
        # The coefficients were calibrated against the real robot so as to obtain realistic sensor values.
        left.append(
            fsv[0][2] / 3.4 + 1.5 * fsv[0][0] + 1.15 * fsv[0][1]
        )  # Left Foot Front Left
        left.append(
            fsv[0][2] / 3.4 + 1.5 * fsv[0][0] - 1.15 * fsv[0][1]
        )  # Left Foot Front Right
        left.append(
            fsv[0][2] / 3.4 - 1.5 * fsv[0][0] - 1.15 * fsv[0][1]
        )  # Left Foot Rear Right
        left.append(
            fsv[0][2] / 3.4 - 1.5 * fsv[0][0] + 1.15 * fsv[0][1]
        )  # Left Foot Rear Left
        right.append(
            fsv[1][2] / 3.4 + 1.5 * fsv[1][0] + 1.15 * fsv[1][1]
        )  # Right Foot Front Left
        right.append(
            fsv[1][2] / 3.4 + 1.5 * fsv[1][0] - 1.15 * fsv[1][1]
        )  # Right Foot Front Right
        right.append(
            fsv[1][2] / 3.4 - 1.5 * fsv[1][0] - 1.15 * fsv[1][1]
        )  # Right Foot Rear Right
        right.append(
            fsv[1][2] / 3.4 - 1.5 * fsv[1][0] + 1.15 * fsv[1][1]
        )  # Right Foot Rear Left

        for i in range(0, len(left)):
            left[i] = max(min(left[i], 25), 0)
            right[i] = max(min(right[i], 25), 0)
            newtonsLeft += left[i]
            newtonsRight += right[i]

        print("----------foot sensors----------")
        print("+ left ---- right +")
        print("+-------+ +-------+")
        print(
            "|"
            + str(round(left[0], 1))
            + "  "
            + str(round(left[1], 1))
            + "| |"
            + str(round(right[0], 1))
            + "  "
            + str(round(right[1], 1))
            + "|  front"
        )
        print("| ----- | | ----- |")
        print(
            "|"
            + str(round(left[3], 1))
            + "  "
            + str(round(left[2], 1))
            + "| |"
            + str(round(right[3], 1))
            + "  "
            + str(round(right[2], 1))
            + "|  back"
        )
        print("+-------+ +-------+")
        print(
            "total: %f Newtons, %f kilograms"
            % ((newtonsLeft + newtonsRight), ((newtonsLeft + newtonsRight) / 9.81))
        )

    def print_foot_bumpers(self):
        """Prints the forces on the foot bumpers"""
        ll = self.lfootlbumper.getValue()
        lr = self.lfootrbumper.getValue()
        rl = self.rfootlbumper.getValue()
        rr = self.rfootrbumper.getValue()

        print("----------foot bumpers----------")
        print("+ left ------ right +")
        print("+--------+ +--------+")
        print("|" + str(ll) + "  " + str(lr) + "| |" + str(rl) + "  " + str(rr) + "|")
        print("|        | |        |")
        print("|        | |        |")
        print("+--------+ +--------+")

    def print_ultrasound_sensors(self):
        """Prints the value of the ultrasound sensors"""
        dist = []
        for i in range(0, len(self.us)):
            dist.append(self.us[i].getValue())

        print("-----ultrasound sensors-----")
        print("left: %f m, right %f m" % (dist[0], dist[1]))

    def print_camera_image(self, camera):
        """Prints the view of the camera"""
        scaled = 2  # Defines by which factor the image is subsampled
        width = camera.getWidth()
        height = camera.getHeight()

        # Read rgb pixel values from the camera
        image = camera.getImage()

        print("----------camera image (gray levels)---------")
        print(
            "original resolution: %d x %d, scaled to %d x %f"
            % (width, height, width / scaled, height / scaled)
        )

        for y in range(0, height // scaled):
            line = ""
            for x in range(0, width // scaled):
                gray = (
                    camera.imageGetGray(image, width, x * scaled, y * scaled) * 9 / 255
                )  # Rescale between 0 and 9
                line = line + str(int(gray))
            print(line)

    def set_all_leds_color(self, rgb):
        """Set the colors of the leds"""
        # These leds take RGB values
        for i in range(0, len(self.leds)):
            self.leds[i].set(rgb)
        # Ear leds are single color (blue) and take values between 0 - 255
        self.leds[5].set(rgb & 0xFF)
        self.leds[6].set(rgb & 0xFF)

    def set_hands_angle(self, angle):
        """Controls the hands of the robot"""
        for i in range(0, self.PHALANX_MAX):
            clampedAngle = angle
            if clampedAngle > self.maxPhalanxMotorPosition[i]:
                clampedAngle = self.maxPhalanxMotorPosition[i]
            elif clampedAngle < self.minPhalanxMotorPosition[i]:
                clampedAngle = self.minPhalanxMotorPosition[i]
            if len(self.rphalanx) > i and self.rphalanx[i] is not None:
                self.rphalanx[i].setPosition(clampedAngle)
            if len(self.lphalanx) > i and self.lphalanx[i] is not None:
                self.lphalanx[i].setPosition(clampedAngle)

    def find_and_enable_devices(self):
        """Start and find the parts of the robot"""
        # Get the time step of the current world.
        self.timeStep = int(self.getBasicTimeStep())

        # Camera
        self.cameraTop = self.getDevice("CameraTop")
        self.cameraBottom = self.getDevice("CameraBottom")
        self.cameraTop.enable(4 * self.timeStep)
        self.cameraBottom.enable(4 * self.timeStep)

        # Accelerometer
        self.accelerometer = self.getDevice("accelerometer")
        self.accelerometer.enable(4 * self.timeStep)

        # Gyro
        self.gyro = self.getDevice("gyro")
        self.gyro.enable(4 * self.timeStep)

        # Gps
        self.gps = self.getDevice("gps")
        self.gps.enable(4 * self.timeStep)

        # Inertial unit
        self.inertialUnit = self.getDevice("inertial unit")
        self.inertialUnit.enable(self.timeStep)

        # Ultrasound sensors
        self.us = []
        usNames = ["Sonar/Left", "Sonar/Right"]
        for i in range(0, len(usNames)):
            self.us.append(self.getDevice(usNames[i]))
            self.us[i].enable(self.timeStep)

        # Foot sensors
        self.fsr = []
        fsrNames = ["LFsr", "RFsr"]
        for i in range(0, len(fsrNames)):
            self.fsr.append(self.getDevice(fsrNames[i]))
            self.fsr[i].enable(self.timeStep)

        # Foot bumpers
        self.lfootlbumper = self.getDevice("LFoot/Bumper/Left")
        self.lfootrbumper = self.getDevice("LFoot/Bumper/Right")
        self.rfootlbumper = self.getDevice("RFoot/Bumper/Left")
        self.rfootrbumper = self.getDevice("RFoot/Bumper/Right")
        self.lfootlbumper.enable(self.timeStep)
        self.lfootrbumper.enable(self.timeStep)
        self.rfootlbumper.enable(self.timeStep)
        self.rfootrbumper.enable(self.timeStep)

        # There are 7 controlable LED groups in Webots
        self.leds = []
        self.leds.append(self.getDevice("ChestBoard/Led"))
        self.leds.append(self.getDevice("RFoot/Led"))
        self.leds.append(self.getDevice("LFoot/Led"))
        self.leds.append(self.getDevice("Face/Led/Right"))
        self.leds.append(self.getDevice("Face/Led/Left"))
        self.leds.append(self.getDevice("Ears/Led/Right"))
        self.leds.append(self.getDevice("Ears/Led/Left"))

        # Get phalanx motor tags for RHand/LHand containing 2x8 motors
        self.lphalanx = []
        self.rphalanx = []
        self.maxPhalanxMotorPosition = []
        self.minPhalanxMotorPosition = []
        for i in range(0, self.PHALANX_MAX):
            self.lphalanx.append(self.getDevice("LPhalanx%d" % (i + 1)))
            self.rphalanx.append(self.getDevice("RPhalanx%d" % (i + 1)))
            # Assume right and left hands have the same motor position bounds
            self.maxPhalanxMotorPosition.append(self.rphalanx[i].getMaxPosition())
            self.minPhalanxMotorPosition.append(self.rphalanx[i].getMinPosition())

        # Shoulder pitch motors
        self.RShoulderPitch = self.getDevice("RShoulderPitch")
        self.LShoulderPitch = self.getDevice("LShoulderPitch")
    
class SoccerRobot(Nao):
    def __init__(self):
        Nao.__init__(self)
        self.player_team = {}
        self.ball_position = [0, 0, 0]
        self.player_states = {}  # Store player positions and role status
        self.sock = None
        self.team_number = 0
        self.player_id = 0
        self.state = None
        self.role = None
        self.action_queue = deque() # Priority queue for handling actions
        self.target_position = [0, 0] # The position the robot is heading towards
        self.target_rotation = [0, 0] # The rotation the robot is targeting
        self.setup_time = 0 # The delay before running the robot to ensure physics calculations are all done
        self.start_time = 0
        self.last_position = [0, 0]
        self.last_rotation = 0
        self.paused = True

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
        print(message)
        message_parts = message.split("|")
        message_type = message_parts[0]
        match message_type:
            case "POS":
                player_id = message_parts[1]
                x_position, y_position = float(message_parts[2]), float(message_parts[3])
                angle = float(message_parts[4])
                # Update the position and rotation of the players
                if player_id != self.player_id:
                    self.update_position(player_id, x_position, y_position)
                    self.update_rotation(player_id, angle)
            case "BALL":
                x_position, y_position, z_position = float(message_parts[1]), float(message_parts[2]), float(message_parts[3])
                self.update_ball_position(x_position, y_position, z_position)
            case "ACK":
                print("Acknowledgement.")
            case "MOVE":
                print("Moving.")
            case "GOAL":
                print("Scored a goal.")
            case "KICK":
                print("Ball kick.")
            case "GET":
                print("Requesting information.")
            case "ROLE":
                self.role = message_parts[1]
                print(f'📢 Assigned Role: {self.role}')
            case "START":
                self.paused = False
                self.setup_time = float(message_parts[1])
            case "INFO":
                team_number = message_parts[1]
                player_id = message_parts[2]
                # Set player information
                if not self.player_id:
                    self.team_number = team_number
                    self.player_id = player_id
                    print(f'🆔 Assigned to team {self.team_number} with Player ID: {self.player_id}')
                else:
                    # Set up player default state
                    self.player_states[player_id] = [None, [0, 0], [0, 0, 0, 0]]
                    self.player_team[player_id] = team_number
                    print(f'📢 New teammate: {player_id}') if team_number == self.team_number else print(f'📢 New opponent: {player_id}')
            case _:
                print(message)
                print("❓ Unknown message type")

    def determine_action(self):
        """Determine what to do based on role and current game state"""
        # If the robot has fallen then ensure it is getting up first
        print(self.state, self.role)
        if self.state == "Standing" and self.is_standup_motion_in_action():
            pass
        if self.has_fallen():
            self.play_standup_motion()
        elif self.state == "Moving":
            self.move_to_position(self.target_position)
        elif self.state == "Turning":
            self.turn_to_direction(self.target_rotation, 2)
        elif self.state == "Kicking":
            # Reset kicking state after kick is done
            if self.currentlyPlaying == self.shoot and self.currentlyPlaying.isOver():
                self.state = None
        match self.role:
            case "Goalie":
                pass
            case "Striker":
                pass
            case "Midfielder":
                pass
            case "Defender":
                pass
            case _:
                # If the ball moved 
                if self.get_distance(self.ball_position, self.target_position) > 0.5:
                    self.go_to(self.ball_position[0], self.ball_position[1])
                # Player with no role should just head towards the ball
                if not self.state:
                    if self.get_distance(self.ball_position, self.get_position()) > 0.2:
                        self.go_to(self.ball_position[0], self.ball_position[1])
                    elif self.state != "Kicking":
                        self.play_kick_ball()
                  
    def has_fallen(self, force_threshold = 5):
        """Determines if the robot has fallen using foot pressure sensors"""
        """
        Skips fall detection until the setup time has passed and the current motion is complete.
        When robots are repositioned using the Supervisor, their foot sensors may temporarily 
        report low values due to incomplete contact with the ground. This delay allows the 
        physics engine to settle the robot and ensures foot sensors register proper ground contact.
        """
        if not self.is_motion_over() or not self.is_setup_time_over(2):
            return False
        
        fsv = []  # Force sensor values
        fsv.append(self.fsr[0].getValues())  # Left foot
        fsv.append(self.fsr[1].getValues())  # Right foot

        # Compute total force on each foot
        newtonsLeft = sum([
            fsv[0][2] / 3.4 + 1.5 * fsv[0][0] + 1.15 * fsv[0][1],  # Left Front Left
            fsv[0][2] / 3.4 + 1.5 * fsv[0][0] - 1.15 * fsv[0][1],  # Left Front Right
            fsv[0][2] / 3.4 - 1.5 * fsv[0][0] - 1.15 * fsv[0][1],  # Left Rear Right
            fsv[0][2] / 3.4 - 1.5 * fsv[0][0] + 1.15 * fsv[0][1]   # Left Rear Left
        ])

        newtonsRight = sum([
            fsv[1][2] / 3.4 + 1.5 * fsv[1][0] + 1.15 * fsv[1][1],  # Right Front Left
            fsv[1][2] / 3.4 + 1.5 * fsv[1][0] - 1.15 * fsv[1][1],  # Right Front Right
            fsv[1][2] / 3.4 - 1.5 * fsv[1][0] - 1.15 * fsv[1][1],  # Right Rear Right
            fsv[1][2] / 3.4 - 1.5 * fsv[1][0] + 1.15 * fsv[1][1]   # Right Rear Left
        ])

        total_force = newtonsLeft + newtonsRight
        if total_force < force_threshold:
            print(f"⚠️ Robot has fallen! Total force: {total_force:.2f}N")
            return True
        #print(f"Robot is standing. Total force: {total_force:.2f}N")
        return False
    
    def is_standup_motion_in_action(self):
        """Checks if the robot is in process of standing up"""
        if self.currentlyPlaying == self.standupFromBack or self.currentlyPlaying == self.standupFromFront and not self.currentlyPlaying.isOver():
            return True
        return False

    def send_player_state(self, force = False):
        """Sends position and rotation changes to the server"""
        position, angle = self.get_position(), self.get_rotation()[2]
        if force or self.get_distance(position, self.last_position) > 0.25 or abs(self.calculate_angle_difference(angle, self.last_rotation)) > math.radians(5):
            self.sock.sendall(f'POS|{self.player_id}|{position[0]:.3f}|{position[1]:.3f}|{angle:.3f}\n'.encode("utf-8"))
            self.last_position = [position[0], position[1]]
            self.last_rotation = angle

    def go_to(self, x_position, y_position, threshold = 0.2):
        """Function to tell the robot to go a certain position"""
        self.set_target_position(x_position, y_position)
        position = self.get_position()
        # If the robot reached the target position then stop moving
        distance = self.get_distance(position, self.target_position)
        if distance < threshold:
            print(f'At position {x_position}, {y_position}.')
            self.state = None
            return
        # Turn before moving
        x_current, y_current = position[0], position[1]
        direction = self.normalize_vector([x_position - x_current, y_position - y_current])
        if self.turn_to_direction(direction, 2):
            self.start_turn(direction)
        else:
            self.state = "Moving"
            self.start_motion(self.smallForwards)

    def move_to_position(self, position, threshold = 0.2):
        """Move the robot to the target position"""
        curr_position = self.get_position()
        x_current, y_current = curr_position[0], curr_position[1]
        # If the robot reached the target position then stop moving
        distance = self.get_distance([x_current, y_current], position)

        if distance < threshold:
            print(f'At position {x_current}, {y_current}.')
            self.stop_motion()
            self.state = None
            return True
        
        if self.is_motion_over():
            # Before moving again, ensure robot direction is correct
            direction = self.normalize_vector([position[0] - x_current, position[1] - y_current])
            if self.turn_to_direction(direction):
                self.start_turn(direction)
                return False
            # Take small steps when it is close else large steps
            if distance < threshold * 2: 
                self.start_motion(self.smallForwards)
            else: 
                self.start_motion(self.largeForwards)
        return False

    def turn_to_direction(self, direction, threshold = 5):
        """Turn the robot towards the target direction"""
        # Find the angle to turn to within [-pi, pi]
        current_angle = self.get_rotation()[2]
        target_angle = math.atan2(direction[1], direction[0])
        angle_difference = self.calculate_angle_difference(current_angle, target_angle)

        # Positive angle indicates a left turn and negative angle indicates a right turn
        print(f"Current yaw: {math.degrees(current_angle):.2f}°, Target yaw: {math.degrees(target_angle):.2f}°, Yaw diff: {abs(math.degrees(angle_difference)):.2f}°")
        if abs(angle_difference) < math.radians(threshold):
            if self.state == "Turning":
                self.stop_turn_and_start_moving()
            return False # Return false for no turning needed
        
        # If the motion is not playing, then play it
        if self.is_motion_over():
            self.start_motion(self.turnLeft40 if angle_difference > 0 else self.turnRight40)
        return True

    def normalize_vector(self, vector):
        """Normalizes a vector"""
        norm = math.sqrt(sum(val ** 2 for val in vector))
        return [v / norm for v in vector] if norm != 0 else vector
    
    def get_distance(self, point_one, point_two):
        """Returns the Euclidean distance between two points in xy-plane"""
        return math.sqrt((point_two[0] - point_one[0]) ** 2 + (point_two[1] - point_one[1]) ** 2)
    
    def calculate_angle_difference(self, angle1, angle2):
        """Returns the angular difference in radians between two angles"""
        return (angle2 - angle1 + math.pi) % (2 * math.pi) - math.pi

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

    def update_position(self, player, x, y):
        """Update the position of the player"""
        self.player_states[player][1] = [x, y]

    def update_rotation(self, player, angle):
        """Update the rotation of the player"""
        self.player_states[player][2] = angle

    def update_ball_position(self, x, y, z):
        """Update the position of the ball"""
        self.ball_position[0] = x
        self.ball_position[1] = y
        self.ball_position[2] = z

    def is_setup_time_over(self, multiplier = 1):
        """Returns True if the setup time has passed"""
        return self.getTime() >= self.start_time + self.setup_time * multiplier

    def is_motion_over(self):
        """Returns whether the current motion finish playing"""
        return not self.currentlyPlaying or self.currentlyPlaying.isOver()

host = "127.0.0.1"
port = 5555

soccer_robot = SoccerRobot()
timeStep = soccer_robot.timeStep

soccer_robot.step(timeStep) # Wait for the game server to be up

client_thread = threading.Thread(target=soccer_robot.connect_to_server, args=(host, port,))
client_thread.start()

# Webots main loop
while soccer_robot.step(timeStep) != -1:
    if not soccer_robot.paused and soccer_robot.is_setup_time_over():
        soccer_robot.determine_action()
        soccer_robot.send_player_state()