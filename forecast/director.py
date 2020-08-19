# packages
import os
import sys
import time
import json
import argparse
import datetime
import requests
import sseclient
import numpy             as np
import matplotlib.pyplot as plt

# project
import config.styling    as stl
import config.parameters as prm
import forecast.helpers  as hlp
from   forecast.sensor   import Sensor


class Director():
    """
    Keeps track of all sensors in project.
    Spawns one Sensor object per sensors.
    When new event_data json is received, relay it to the correct object.
    """

    def __init__(self, username, password, project_id, api_url_base):
        # give to self
        self.username     = username
        self.password     = password
        self.project_id   = project_id
        self.api_url_base = api_url_base

        # parse system arguments
        self.__parse_sysargs()

        # use local file
        if self.args['path']:
            # perform some initial setups
            self.__local_setup()

            # import file as event history format
            self.event_history = hlp.import_as_event_history(self.args['path'])
        
        # use API
        else:
            # set filters for fetching data
            self.__set_filters()

            # set stream endpoint
            self.stream_endpoint = "{}/projects/{}/devices:stream".format(self.api_url_base, self.project_id)

            # fetch list of devices in project
            self.__fetch_project_devices()

            # spawn devices instances
            self.__spawn_devices()

            # fetch event history
            if self.fetch_history:
                self.__fetch_event_history()

        # some cout
        self.print_devices_information()


    def __parse_sysargs(self):
        """
        Parse for command line arguments.
    
        """
    
        # create parser object
        parser = argparse.ArgumentParser(description='Temperature forecast on Stream and Event History.')
    
        # general arguments
        now = (datetime.datetime.utcnow().replace(microsecond=0)).isoformat() + 'Z'
        parser.add_argument('--path',      metavar='', help='Absolute path to local .csv file.',                   required=False, default=None)
        parser.add_argument('--starttime', metavar='', help='Event history UTC starttime [YYYY-MM-DDTHH:MM:SSZ].', required=False, default=now)
        parser.add_argument('--endtime',   metavar='', help='Event history UTC endtime [YYYY-MM-DDTHH:MM:SSZ].',   required=False, default=now)
    
        # boolean flags
        parser.add_argument('--plot',       action='store_true', help='Plot the resulting forecast.')
        parser.add_argument('--plot-init',  action='store_true', help='Plot the initialization results.')
        parser.add_argument('--plot-debug', action='store_true', help='Plot algorithm operation.')
    
        # convert to dictionary
        self.args = vars(parser.parse_args())
    
        # set history flag
        if now == self.args['starttime']:
            self.fetch_history = False
        else:
            self.fetch_history = True


    def __local_setup(self):
        """
        Sanitize path argument and generate fake devices list to spawn.

        """

        # verify valid path
        if not os.path.exists(self.args['path']):
            hlp.print_error('Path [{}] is not valid.'.format(self.args['path']))

        # make a fake list of devices
        self.devices = [{'name': 'local_file', 'type': 'temperature'}]

        # set fetch flag
        self.fetch_history = True

        # spawn devices
        self.__spawn_devices()


    def __set_filters(self):
        """
        Set filters for data fetched through API.

        """

        # historic events
        self.history_params = {
            'page_size': 1000,
            'start_time': self.args['starttime'],
            'end_time': self.args['endtime'],
            'event_types': ['temperature'],
        }

        # stream events
        self.stream_params = {
            'event_types': ['temperature'],
        }


    def __fetch_project_devices(self):
        """
        Fetch information about all devices in project.

        """

        # request list
        devices_list_url = "{}/projects/{}/devices".format(self.api_url_base,  self.project_id)
        device_listing = requests.get(devices_list_url, auth=(self.username, self.password))
        
        # remove fluff
        if device_listing.status_code < 300:
            self.devices = device_listing.json()['devices']
        else:
            print(device_listing.json())
            hlp.print_error('Status Code: {}'.format(device_listing.status_code), terminate=True)


    def __spawn_devices(self):
        """Use list of devices to spawn Sensor objects for each."""

        # empty lists of devices
        self.sensors = {}

        # iterate list of devices
        for device in self.devices:
            # verify temperature type
            if device['type'] == 'temperature':
                # get device id
                device_id = os.path.basename(device['name'])

                # new key in sensor dictionary
                self.sensors[device_id] = Sensor(device, device_id, self.args)


    def __fetch_event_history(self):
        """
        For each sensor in project, request all events since --starttime from API.

        """

        # initialise empty event list
        self.event_history = []

        # iterate devices
        for device in self.devices:
            # isolate device identifier
            device_id = os.path.basename(device['name'])
        
            # some printing
            print('-- Getting event history for {}'.format(device_id))
        
            # initialise next page token
            self.history_params['page_token'] = None
        
            # set endpoints for event history
            event_list_url = "{}/projects/{}/devices/{}/events".format(self.api_url_base, self.project_id, device_id)
        
            # perform paging
            while self.history_params['page_token'] != '':
                event_listing = requests.get(event_list_url, auth=(self.username, self.password), params=self.history_params)
                event_json = event_listing.json()
        
                if event_listing.status_code < 300:
                    self.history_params['page_token'] = event_json['nextPageToken']
                    self.event_history += event_json['events']
                else:
                    print(event_json)
                    hlp.print_error('Status Code: {}'.format(event_listing.status_code), terminate=True)
        
                if self.history_params['page_token'] is not '':
                    print('\t-- paging')
        
        # sort event history in time
        self.event_history.sort(key=hlp.json_sort_key, reverse=False)


    def run_history(self):  
        """
        Iterate historic event data.
    
        """

        # do nothing if no starttime is given
        if not self.fetch_history:
            return

        # initialise debug plot
        if self.args['plot_debug']:
            self.initialise_debug_plot()
    
        # estimate occupancy for history 
        cc = 0
        for i, event_data in enumerate(self.event_history):
            cc = hlp.loop_progress(cc, i, len(self.event_history), 25, name='event history')
            # serve event to director
            self.__new_event_data(event_data, cout=False)

            # plot debug
            if self.args['plot_debug']:
                self.plot_debug()
    
        # initialise plot
        if self.args['plot']:
            print('\nClose the blocking plot to start stream.')
            print('A new non-blocking plot will appear for stream.')
            self.initialise_plot()
            self.plot_progress(blocking=True)


    def run_stream(self, n_reconnects=5):
        """
        Stream events for sensors in project.
    
        Parameters
        ----------
        n_reconnects : int
            Number of retries if connection lost.

        """

        # don't run if local file
        if self.args['path']:
            return
    
        # cout
        print("Listening for events... (press CTRL-C to abort)")
    
        # reinitialise plot
        if self.args['plot']:
            self.initialise_plot()
            self.plot_progress(blocking=False)
    
        # loop indefinetly
        nth_reconnect = 0
        while nth_reconnect < n_reconnects:
            try:
                # reset reconnect counter
                nth_reconnect = 0
        
                # get response
                response = requests.get(self.stream_endpoint, auth=(self.username, self.password), headers={'accept':'text/event-stream'}, stream=True, params=self.stream_params)
                client = sseclient.SSEClient(response)
        
                # listen for events
                print('Connected.')
                for event in client.events():
                    # new data received
                    event_data = json.loads(event.data)['result']['event']
        
                    # serve event to director
                    self.__new_event_data(event_data)
        
                    # plot progress
                    if self.args['plot']:
                        self.plot_progress(blocking=False)
            
            except requests.exceptions.ConnectionError:
                nth_reconnect += 1
                print('Connection lost, reconnection attempt {}/{}'.format(nth_reconnect, n_reconnects))
            except requests.exceptions.ChunkedEncodingError:
                nth_reconnect += 1
                print('An error occured, reconnection attempt {}/{}'.format(nth_reconnect, n_reconnects))
            
            # wait 1s before attempting to reconnect
            time.sleep(1)


    def initialise_plot(self):
        """Create figure and axis objects for progress plot."""

        self.hfig, self.hax = plt.subplots(len(self.sensors), 1, sharex=True)
        if len(self.sensors) == 1:
            self.hax = [self.hax]


    def initialise_debug_plot(self):
        """Create figure and axis objects for debug plot."""

        self.dfig, self.dax = plt.subplots(4, 1, sharex=True)


    def print_devices_information(self):
        """Print information about active devices in stream."""

        print('\nDirector initialised for sensors:')
        # print sensors
        for sensor in self.sensors:
            print('-- {:<30}'.format(sensor))
        print()


    def __new_event_data(self, event_data, cout=True):
        """Receive new event_data json and pass it along to the correct device object.

        Parameters:
            event_data -- Data json containing new event data.
            cout       -- Print device information to console if True.
        """

        # get id of source sensor
        source_id = os.path.basename(event_data['targetName'])

        # verify temperature event
        if 'temperature' in event_data['data'].keys():
            # check if source device is known
            if source_id in self.sensors.keys():
                # serve event to sensor
                self.sensors[source_id].new_event_data(event_data)
                if cout: print('-- {:<30}'.format(source_id))


    def plot_progress(self, blocking=False):
        """Plot data and forecast from most recent sample.

        parameters:
            blocking -- Will block execution if True. Required for interaction.
        """

        # iterate sensors
        for i, sid in enumerate(self.sensors.keys()):

            # isolate sensor
            sensor = self.sensors[sid]
            self.hax[i].cla()

            if sensor.n_samples > 1:
                # get timeaxes
                model_tx    = hlp.ux2tx(sensor.model['unixtime'])

                # get forecast
                fx, ft, fu, fl = sensor.get_forecast(prm.n_forecast)
                fx = hlp.ux2tx(fx)

                self.hax[i].plot(model_tx, sensor.model['temperature'], color=stl.NS[1], label='Temperature')
                self.hax[i].axvline(model_tx[-1], color='k', linestyle='--', label='Time Now')
                self.hax[i].plot(fx, ft, color=stl.NS[1], linestyle='--', label='Forecast')
                self.hax[i].fill_between(fx, fl, fu, color=stl.NS[1], alpha=0.33, label='Forecast Interval')
                self.hax[i].legend(loc='upper left')
                self.hax[i].set_xlabel('Timestamp')
                self.hax[i].set_ylabel('Temperature [degC]')

        if blocking:
            plt.show()
        else:
            plt.pause(0.01)


    def plot_debug(self):
        """Plot data and more detailed algorithm operation."""

        # iterate sensors
        for i, sid in enumerate(self.sensors.keys()):
            # isolate sensor
            sensor = self.sensors[sid]

            if sensor.n_samples % int(prm.season_length/0.25) == 0 and len(sensor.forecast['unixtime']) > 0:

                n_days = 20
                tax = np.array(sensor.model['unixtime'])[np.array(sensor.model['unixtime']) > int(sensor.model['unixtime'][-1])-60*60*24*n_days]
                fax = np.array(sensor.forecast['unixtime'])[np.array(sensor.forecast['unixtime']) > int(sensor.forecast['unixtime'][-1])-60*60*24*n_days]

                self.dax[0].cla()
                self.dax[0].plot(tax, np.array(sensor.model['temperature'])[-len(tax):], color=stl.NS[1], label='Temperature')
                self.dax[0].legend(loc='upper left')
                self.dax[0].set_ylabel('Temperature [degC]')
                self.dax[0].set_xlim([tax[0], tax[-1]])
                self.dax[1].cla()
                self.dax[1].plot(tax, np.array(sensor.model['level'])[-len(tax):], color=stl.NS[1], label='Level')
                self.dax[1].legend(loc='upper left')
                self.dax[1].set_ylabel('Temperature [degC]')
                self.dax[1].set_xlim([tax[0], tax[-1]])
                self.dax[2].cla()
                self.dax[2].plot(tax, np.array(sensor.model['trend'])[-len(tax):], color=stl.NS[1], label='Trend')
                self.dax[2].legend(loc='upper left')
                self.dax[2].set_ylabel('Slope')
                self.dax[2].set_xlim([tax[0], tax[-1]])
                self.dax[3].cla()
                self.dax[3].plot(tax, np.array(sensor.model['season'])[-len(tax):], color=stl.NS[1], label='Season')
                self.dax[3].legend(loc='upper left')
                self.dax[3].set_xlabel('Unixtime')
                self.dax[3].set_ylabel('Temperature [degC]')
                self.dax[3].set_xlim([tax[0], tax[-1]])

                plt.waitforbuttonpress()

