class RandomMissionGenerator(object):
    """Generates random  missions"""
    def __init__(self, name):
        self.name = name
        self.types = ['PTP','MPTP','Extraction']
        self.ptp_params = ['alt','x','y','x_d','y_d','z_d']
        self.extraction_params = list(self.ptp_params).append('wait')
        # Failure Flags and Quality Attributes use the same list
        self.quaility_attributes = ['ReportRate','Time','Battery','MaxHeight',\
        'MinHeight','DistanceTraveled']
        self.intents = list(self.quality_attributes).remove('ReportRate')


    def get_random_by_type(self, param):
        if param == 'alt':
            return random.uniform(1, 50)
        elif param == 'wait':
            return random.uniform(0,50)
        elif param in list(self.ptp_params).remove('alt'):
            return random.uniform(0, 50)


    def get_multiple_locations(self, number_of_locations):
        locations = []
        for x in range(number_of_locations):
            location = {}
            for param in list(self.ptp_params).remove('alt'):
                location[param] = self.get_random_by_type(param)
            locations.append(locations)
        return locations


    def get_mission_action(self):
        action_data = {}
        psudo_random_number = random.randint(0,len(self.types))
        if psudo_random_number == 0:
            action_data['Type'] = self.types[0]
            for param in self.ptp_params:
                action_data[param] = self.get_random_by_type(param)
            return action_data
        elif psudo_random_number == 1:
            action_data['Type'] = self.types[1]
            action_data['Locations'] = self.get_multiple_locations(random.randint(10))
            return action_data
        elif psudo_random_number == 2:
            action_data['Type'] = self.types[2]
            for param in self.extraction_params:
                action_data[param] = self.get_random_by_type(param)
            return action_data


    # We want all the data about the run, so we set all to true
    def get_quality_attributes(self):
        quality_attributes_data = {}
        for param in self.quaility_attributes:
            if param == 'ReportRate':
                quality_attributes_data[param] = QUALITY_ATTRUBUTE_INFORM_RATE
            quality_attributes_data[param] = True
        return quality_attributes_data


    def get_intents(self, mission_action):
        ros = ROSHandler()
        current_x_y = ros.monitor(None,None,None,True)
        if mission_action['Type'] == 'PTP':
            print 'ha'


    def generate_random_mission(self):
        json = {'MDescription':{'RobotType':'Copter','LaunchFile':None},\
        'Map':Non}
        mission_action = self.get_mission_action()
        quality_attributes = self.get_quality_attributes()
        intents = self.get_intents(mission_action)
        json['Action':mission_action]
        json['Quality_Attributes'] = quality_attributes
