import rospy
from nav_msgs.msg      import Odometry
from mavros_msgs.msg   import BatteryStatus
from sensor_msgs.msg   import NavSatFix


system_variables = {}
system_variables['altitude']  = lambda : rospy.client.wait_for_message('/mavros/local_position/odom', Odometry, timeout=1.0).pose.pose.position.z
system_variables['latitude']  = lambda : rospy.client.wait_for_message('/mavros/global_position/global', NavSatFix, timeout=1.0).latitude
system_variables['longitude'] = lambda : rospy.client.wait_for_message('/mavros/global_position/global', NavSatFix, timeout=1.0).longitude
system_variables['battery']   = lambda : rospy.client.wait_for_message('/mavros/battery', BatteryStatus, timeout=1.0).remaining


def read_variable(variable):
    return system_variables[variable]()
