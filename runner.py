#!/usr/bin/python2.7

# TODO: Description!

import time
import json
import sys
import rospy
import math
import thread
from geopy.distance import great_circle

from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import BatteryStatus
from sensor_msgs.msg import NavSatFix
from mavros_msgs.srv import CommandLong, SetMode, CommandBool, CommandTOL

# TODO: Check for mavros first 
# Command IDs in MAVLINK
#COMMANDS = {"TAKEOFF": 24, "SETMODE": 176, "ARM": 400 }
#home coordinates
HOME_COORDINATES              = (-35.3632607, 149.1652351) 
ERROR_LIMIT_DISTANCE          = .4 # 30cm TODO: pick a better name 
TIME_INFORM_RATE              = 10 # seconds. How often log time
QUALITY_ATTRUBUTE_INFORM_RATE = 5  # seconds. 
STABLE_BUFFER_TIME            = 4.0  # Seconds time to wait after each command 


class Error(object):

    def __init__(self, error):
        self.error = error
    
    def format_error(self):
        print '[FORMAT ERROR] JSON file is not properly formated. ('+\
        self.error+')'
        exit()

    def thread_error(self):
        print '[THREAD ERROR] '+ self.error
        exit()
    def failure_flag(self):
        print '[FAILURE FLAG] '
        exit()


class Log(object):

    def __init__(self, log):
        print "[LOG]: " + log


class ROSHandler(object):
    def __init__ (self, target):
        self.mission_on                 = True
        self.initial_set                = [False, False, False]
        self.starting_time              = time.time()
        self.target                     = target
        self.battery                    = [0,0]
        self.min_max_height             = [0,0]
        self.lock_min_max_height        = False
        self.initial_global_coordinates = [0,0]
        self.initial_local_position     = [0,0,0]

        self.current_global_coordinates = [0,0]
        self.current_local_position     = [0,0,0]

        self.global_alt                 = [0,0]
        
    def check_goto_completion(self, expected_coor, pose, pub):
        local_action_time = time.time()
        success = True
        r = rospy.Rate(10)
        self.lock_min_max_height = True
        while great_circle(self.current_global_coordinates,expected_coor).meters\
             >= ERROR_LIMIT_DISTANCE and self.mission_on: 
            r.sleep()
            pub.publish(pose)
            local_action_time = self.inform_time(local_action_time, 2,\
                'Remaining: ' + str(great_circle(self.current_global_coordinates,\
                    expected_coor).meters))
        if great_circle(self.current_global_coordinates,expected_coor).meters\
            >= ERROR_LIMIT_DISTANCE:
            success = False
        self.lock_min_max_height = False

        time.sleep(STABLE_BUFFER_TIME)
        return success

    def check_land_completion(self, alt, wait = STABLE_BUFFER_TIME):
        local_action_time = time.time()
        success = True
        self.lock_min_max_height = True
        while self.current_local_position[2] >= ERROR_LIMIT_DISTANCE and \
            self.mission_on:
            local_action_time = self.inform_time(local_action_time, 5, \
            'Waiting to reach land. Goal: ~0' +' - Current: '\
                +str(self.current_local_position[2]))
        self.lock_min_max_height = False
        if self.current_local_position[2] >= ERROR_LIMIT_DISTANCE:
            success = False
        time.sleep(wait)
        return success



    def check_takeoff_completion(self, alt):
        local_action_time = time.time()
        success = True
        lock_min_max_height = True
        while ((alt+(ERROR_LIMIT_DISTANCE/2)) >= self.current_local_position[2]) \
            and (self.current_local_position[2] <= (alt-(ERROR_LIMIT_DISTANCE/2)))\
            and self.mission_on:
                local_action_time = self.inform_time(local_action_time, 5, \
                'Waiting to reach alt. Goal: '+ str(alt) +' - Current: '\
                +str(self.current_local_position[2]))
        lock_min_max_height = False
        if ((alt+(ERROR_LIMIT_DISTANCE/2)) >= self.current_local_position[2]) \
            and (self.current_local_position[2] <= (alt-(ERROR_LIMIT_DISTANCE/2))):
            success = False
        time.sleep(STABLE_BUFFER_TIME)
        return success

    # Sets the system to GUIDED, arms and takesoff to a given altitude.
    # TODO: add mode to mission parameters? 
    def ros_command_takeoff(self, alt):
        set_mode = rospy.ServiceProxy('/mavros/set_mode', SetMode)
        res = set_mode(0, "GUIDED")

        if res: # DO check res return to match bool 
            Log("Mode changed to GUIDED")
        else:
            Error("System mode could not be changed to GUIDED")

        arm = rospy.ServiceProxy('/mavros/cmd/arming', CommandBool)
        res = arm(True)
        if res:
            Log("System ARMED...")
        else:
            Error("System could not be ARMED.")

        takeoff = rospy.ServiceProxy('/mavros/cmd/takeoff', CommandTOL)
        res = takeoff(0, 0, 0, 0, alt)
        if res:
            Log("System Taking off...")
        else:
            Error("System did not take off.")
        succes = self.check_takeoff_completion(alt)
        if succes:
            Log('System reached height')
        else:
            Log('System did not reach height on time')
        
        
    #def goto_command(self, lat, longitud):

    # Makes a service call to coomand the system to land
    def ros_command_land(self, alt, wait = None):
        land = rospy.ServiceProxy('/mavros/cmd/land', CommandTOL)
        res = land(0, 0, 0, 0, alt)
        if res:
            Log("System landing...")
        else:
            Error("System is not landing.")
        if wait == None:
            success = self.check_land_completion(alt)
        else:
            success = self.check_land_completion(alt, wait)
        if success:
            Log('System has landed')
        else:
            Log('System did not land on time ')


    def get_current_x_y(self):
        x = great_circle(HOME_COORDINATES, ( HOME_COORDINATES[0], self.current_global_coordinates[1],)).meters
        y = great_circle(HOME_COORDINATES, (self.current_global_coordinates[0], HOME_COORDINATES[1],)).meters
        if HOME_COORDINATES[0]> self.current_global_coordinates[0]:
            y *= -1
        if HOME_COORDINATES[1]> self.current_global_coordinates[1]:
            x *= -1


        return x, y

    def get_expected_lat_long(self, x_y, target, x_distance, y_distance):
        expected_lat  = 0
        expected_long = 0
        if float("{0:.0f}".format(math.fabs(y_distance))) == 0:
            expected_lat = self.initial_global_coordinates[0]
        else:
            if target[1]> x_y[1]:
                expected_lat  = self.initial_global_coordinates[0] + ((y_distance / \
                    6378000.0) * (180.0/math.pi))
            else:
                expected_lat  = self.initial_global_coordinates[0] - ((y_distance / \
                    6378000.0) * (180.0/math.pi))
        if float("{0:.0f}".format(math.fabs(x_distance))) == 0:
            expected_long = self.initial_global_coordinates[1]
        else:
            if target[0]> x_y[0]:
                expected_long = self.initial_global_coordinates[1] + ((x_distance / \
                    6378000.0) * (180.0/math.pi) / math.cos(math.radians(\
                    self.initial_global_coordinates[0])))
            else:
                expected_long = self.initial_global_coordinates[1] - ((x_distance / \
                    6378000.0) * (180.0/math.pi) / math.cos(math.radians(\
                    self.initial_global_coordinates[0])))
        return expected_lat, expected_long

    def reset_initial_global_position(self):
        self.initial_set[0] = False
        self.initial_set[1] = False


    # Commands the system to a given location. Verifies the end of the publications
    # by comparing the current position with the expected position.
    # Need to add z for angular displacement. 
    def ros_command_goto(self, target, mptp):
        # It makes sure that the initial position is updated in order to calculate
        # the next coordinate 
        if mptp:
                self.reset_initial_global_position()
        goto_publisher = rospy.Publisher('/mavros/setpoint_position/local',\
            PoseStamped, queue_size=10)
        pose = PoseStamped()
        pose.pose.position.x = target[0]
        pose.pose.position.y = target[1]
        pose.pose.position.z = target[2]
        expected_lat      = None
        expected_long     = None
        expected_coor     = None
        expected_distance = None

        # 0,0 is set to HOME which is the starting position of the system. 
        if target[0] == 0 and target[1] == 0:
            expected_coor = (HOME_COORDINATES[0], HOME_COORDINATES[1])
            
            expected_distance = great_circle(self.initial_global_coordinates, \
                expected_coor).meters
            Log('Using home coordinates: initial' + str(self.initial_global_coordinates)\
                + ' expected: ' + str(expected_coor))
        else:
            current_x, current_y = self.get_current_x_y()
            x_y = (current_x, current_y)
            x_distance = euclidean((target[0], 0),(current_x, 0)) - ERROR_LIMIT_DISTANCE
            y_distance = euclidean((0, target[1]),(0, current_y)) - ERROR_LIMIT_DISTANCE
            expected_lat, expected_long = self.get_expected_lat_long(x_y, target, \
                x_distance, y_distance)
            expected_coor = (expected_lat, expected_long)
            Log('Using other coordinates: initial' + str(\
                self.initial_global_coordinates)\
                + ' expected: ' + str(expected_coor))
            expected_distance = great_circle(self.initial_global_coordinates, \
                expected_coor).meters


        self.current_global_coordinates = self.initial_global_coordinates
        Log('Remaining distance to travel :  ' + str( great_circle(self.current_global_coordinates,expected_coor).meters))
        success = self.check_goto_completion(expected_coor, pose, goto_publisher)
        if success:
            Log('Position reached')
        else:
            Log('System did not reach position on time')

    # Callback for local position sub. It also updates the min and the max height
    def ros_monitor_callback_local_position(self, data):
        if data.pose.position.z > self.min_max_height[1] and not \
            self.lock_min_max_height:
            self.min_max_height[1] = data.pose.position.z
        if data.pose.position.z < self.min_max_height[0] and not \
            self.lock_min_max_height:
            self.min_max_height[0] = data.pose.position.z

        if not self.initial_set[0]:
            self.initial_local_position[0]        = data.pose.position.x
            self.initial_local_position[1]        = data.pose.position.y
            self.initial_local_position[2]        = data.pose.position.z
            self.initial_set[0]                   = True
        self.current_local_position[0]            = data.pose.position.x
        self.current_local_position[1]            = data.pose.position.y
        self.current_local_position[2]            = data.pose.position.z
        

    # Callback for global position sub
    def ros_monitor_callback_global_position(self, data):
        if not self.initial_set[1]:
            self.initial_global_coordinates[0]    = data.latitude 
            self.initial_global_coordinates[1]    = data.longitude
            self.global_alt[0]                    = data.altitude
            self.initial_set[1]                   = True
        self.current_global_coordinates[0]        = data.latitude
        self.current_global_coordinates[1]        = data.longitude
        self.global_alt[1]                        = data.altitude

    def ros_monitor_callback_battery(self, data):
        if not self.initial_set[2]:
            self.battery[0]                       = data.remaining
            self.initial_set[2]                   = True
        self.battery[1]                           = data.remaining


    def inform_time(self, temp_time, time_rate = TIME_INFORM_RATE , \
            message = ''):
        current_time = time.time()
        if  (current_time - temp_time) > time_rate:
                Log('Current time: ' + str(time.time() - self.starting_time)+ \
                    ': '+ str(message))
                return current_time
        else:
            return temp_time

    def check_failure_flags(self, failure_flags):
        if time.time() - self.starting_time >= float(failure_flags['Time']):
            return True, 'Time exceeded'
        elif self.battery[0] - self.battery[1] >= float(failure_flags['Battery']):
            return True, 'Battery exceeded'
        elif self.current_local_position[2] >= failure_flags['MaxHeight']:
            return True, 'Max Height exceeded'
        else:
            return False, None

    def check_quality_attributes(self, quality_attributes, current_data, _time):
        if time.time() - _time >= float(quality_attributes['ReportRate']):
            current_data.append({'Time': time.time() - self.starting_time, \
                'Battery': self.battery[0]-self.battery[1], 'MinHeight': \
                self.min_max_height[0], 'MaxHeight': self.min_max_height[1]})
            return time.time(), current_data
        else:
            return _time, current_data

    # Starts two subscribers to populate the system's location. It also ensures 
    # failure flags. *More to be added 
    def ros_monitor(self, quality_attributes, intents, failure_flags):        
        local_pos_sub   = rospy.Subscriber('/mavros/local_position/pose', \
            PoseStamped \
         , self.ros_monitor_callback_local_position, queue_size=10)
        global_pos_sub  = rospy.Subscriber('/mavros/global_position/global', \
            NavSatFix \
         , self.ros_monitor_callback_global_position)
        battery_sub     = rospy.Subscriber('/mavros/battery', BatteryStatus, \
          self.ros_monitor_callback_battery)

        report_data = {'QualityAttributes':[],'FailureFlags':'None'}
        temp_time   = time.time() #time used for failure flags and time inform
        qua_time    = time.time() #time used for the rate of attribute reports
        while self.mission_on:
            temp_time = self.inform_time(temp_time)
            fail, reason = self.check_failure_flags(failure_flags)
            if fail:
                report_data['FailureFlags'] = reason
                self.mission_on = False
            else:
                qua_time, qua_report = self.check_quality_attributes(\
                    quality_attributes,report_data['QualityAttributes'], qua_time)
                report_data['QualityAttributes'] = qua_report

        report_generator = Report(self, report_data)
        report_generator.generate()

    def ros_set_mission_over(self):
        self.mission_on = False

class Report(object):
    def __init__(self, ros_handler_self ,report_data):
        self.report_data      = report_data
        self.ros_handler_self = ros_handler_self

    def generate(self):
        print self.report_data['QualityAttributes']
        print self.report_data['FailureFlags']


class Mission(object):

    # Starts mission point to point. Function starts a monitor thread which constantly 
    # updates the systems location and data required for the mission.
    def execute_point_to_point(self, action_data, quality_attributes, intents, \
        failure_flags):
        ros = ROSHandler('mavros')
        main = rospy.init_node('HoustonMonitor')
        try:
            thread.start_new_thread(ros.ros_monitor, (quality_attributes, intents, \
             failure_flags))
            time.sleep(2) # TODO Check for populated
            ros.ros_command_takeoff(action_data[6]) #position 6 is alt
            ros.ros_command_goto(action_data, False)
            ros.ros_command_land(action_data[6])
            ros.ros_set_mission_over()

        except:
            #Error('unable to start thread').thread_error()
            raise 

    def execute_multiple_point_to_point(self, action_data, quality_attributes,\
        intents, failure_flags):
        ros = ROSHandler('mavros')
        main = rospy.init_node('HoustonMonitor')
        try:
            thread.start_new_thread(ros.ros_monitor, (quality_attributes, intents, \
                failure_flags))
            time.sleep(2)
            # TODO: Mulitple altitudes 
            ros.ros_command_takeoff(action_data[6])
            for target in action_data:
                ros.ros_command_goto(target, True)
            ros.ros_command_land(action_data[6])
            ros.ros_set_mission_over()
        except:
            raise

    def execute_extraction(self, action_data, quality_attributes, intents, \
        failure_flags):
        ros = ROSHandler('mavros')
        main = rospy.init_node('HoustonMonitor')
        
        # TODO: Allow Houston to save locations of interest. In this case for home locaiton
        # diferent from HOME, since we are dealing with a posible starting home 

        try:
            thread.start_new_thread(ros.ros_monitor, (quality_attributes, intents, \
                failure_flags))
            time.sleep(2)
            initial_x_y = ros.get_current_x_y()
            ros.ros_command_takeoff(action_data[6])
            ros.ros_command_goto(action_data, False)
            ros.ros_command_land(action_data[6], action_data[7]) # 7 wait time
            ros.ros_command_takeoff(action_data[6])
            action_data[0] = initial_x_y[0]
            action_data[1] = initial_x_y[1]
            ros.ros_command_goto(action_data, False)
            ros.ros_command_land(action_data[6])
            ros.ros_set_mission_over()
        except:
            raise
    # Checks that all the required parameters for a correct mission run are present 
    def check_parameters(self, parameters):
        gen_parameters = {'Time', 'Battery', 'MaxHeight', 'MinHeight'}
        if 'QualityAttributes' in parameters:
            if not all  (param in parameters['QualityAttributes'] for param \
                in gen_parameters):
                Error("QualityAttributes description does not have enough attributes")
        else:
            Error('QualityAttributes not found.')
        if 'Intents' in parameters:
            if not all (param in parameters['Intents'] for param in gen_parameters):
                Error("Intents description does not have enough attributes")
        else:
            Error("Intents not found")
        if 'FailureFlags' in parameters:
            if not all (param in parameters['FailureFlags'] for param in gen_parameters):
                Error("FailureFlags description does not have enough attributes")
        else:
            Error("FailureFlags not found")
        return True

    # Executes mission
    def execute(self):
        mission_action = self.mission_info['Action']
        parameter_pass = self.check_parameters(self.mission_info)
        quality_attributes = self.mission_info['QualityAttributes']
        intents = self.mission_info['Intents']
        failure_flags = self.mission_info['FailureFlags']
        if (mission_action['Type'] == 'PTP') and parameter_pass:
            start_x = float(mission_action['x'])
            start_y = float(mission_action['y'])
            start_z = float(mission_action['z'])
            end_x   = float(mission_action['x_d'])
            end_y   = float(mission_action['y_d'])
            end_z   = float(mission_action['y_d'])
            alt     = float(mission_action['alt'])
            action_data = (start_x, start_y, start_z, end_x, end_y, end_z, alt)
            self.execute_point_to_point(action_data, quality_attributes, intents,\
             failure_flags)
        elif (mission_action['Type'] == 'MPTP' and parameter_pass):
            action_data = []
            for location in mission_action['Locations']:
                start_x = float(location['x'])
                start_y = float(location['y'])
                start_z = float(location['z'])
                end_x   = float(location['x_d'])
                end_y   = float(location['y_d'])
                end_z   = float(location['y_d'])
                alt     = float(location['alt'])
                action_data.append((start_x,start_y,start_z,end_x,end_y,end_z,alt))
            self.execute_multiple_point_to_point(action_data,quality_attributes,\
                intents,failure_flags)
        elif (mission_action['Type'] == 'Extraction' and parameter_pass):
            action_data = []
            start_x = float(mission_action['x'])
            start_y = float(mission_action['y'])
            start_z = float(mission_action['z'])
            end_x   = float(mission_action['x_d'])
            end_y   = float(mission_action['y_d'])
            end_z   = float(mission_action['y_d'])
            alt     = float(mission_action['alt'])
            wait    = float(mission_action['wait'])
            action_data = [start_x,start_y,start_z,end_x,end_y,end_z,alt,wait]
            self.execute_extraction(action_data,quality_attributes,\
                intents,failure_flags)
        else:
            print 'Mission type found not supported'

    def __init__(self, mission_info):
        self.robot_type  = mission_info['RobotType']
        self.launch_file = mission_info['LaunchFile']
        self.map         = mission_info['Map']
        self.mission_info = mission_info['Mission']



def check_json(json_file):
    if not 'MDescription' in json_file:
        Error('MDescription').format_error()
    elif not 'RobotType' in json_file['MDescription']:
        Error('RobotType').format_error()
    elif not 'LaunchFile' in json_file['MDescription']:
        Error('LaunchFile').format_error()
    elif not 'Map' in json_file['MDescription']:
        Error('Map').format_error()
    elif not 'Mission' in json_file['MDescription']:
        Error('Mission').format_error()
    elif not 'Name' in json_file['MDescription']['Mission']:
        Error('Mission - Name').format_error()
    elif not 'Action' in json_file['MDescription']['Mission']:
        Error('Mission - Action').format_error()
    elif not 'QualityAttributes' in json_file['MDescription']['Mission']:
        Error('Mission - QualityAttrubutes').format_error()
    elif not 'Intents' in json_file['MDescription']['Mission']:
        Error('Mission - Intents').format_error()
    elif not 'FailureFlags' in json_file['MDescription']['Mission']:
        Error('Mission - FailrueFlags').format_error()
    else:
        print Log('JSON file meets format requirements.')


def euclidean(a, b):
    assert isinstance(a, tuple) and isinstance(b, tuple)
    assert len(a) != []
    assert len(a) == len(b)
    d = sum((x - y) ** 2 for (x, y) in zip(a, b))
    return math.sqrt(d)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ('Please provide a mission description file. (JSON)')
        exit()
    with open(sys.argv[1]) as file:
        json_file = json.load(file)

    #check_json(json_file)
    #mission = Mission(json_file['MDescription'])
    # done this way since the only mission currently supported is point to point
    #mission_results = mission.execute()


    check_json(json_file)
    mission = Mission(json_file['MDescription'])
    # done this way since the only mission currently supported is point to point
    mission_results = mission.execute()
