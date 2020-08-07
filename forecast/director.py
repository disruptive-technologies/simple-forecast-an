# packages
import os
import sys
import numpy             as np
import matplotlib.pyplot as plt

# project
import forecast.config.styling    as stl
import forecast.config.parameters as prm
import forecast.helpers           as hlp
from   forecast.sensor              import Sensor


class Director():
    """
    Keeps track of all sensors in project.
    Spawns one Sensor object per sensors.
    When new event_data json is received, relay it to the correct object.
    """

    def __init__(self, devices, args):
        # add to self
        self.args    = args
        self.devices = devices

        # initialise sensor objects from devices
        self.__spawn_sensors()

        # print some information
        self.print_devices_information()


    def initialise_plot(self):
        """Create figure and axis objects for progress plot."""

        self.hfig, self.hax = plt.subplots(len(self.sensors), 1, sharex=True)
        if len(self.sensors) == 1:
            self.hax = [self.hax]


    def initialise_debug_plot(self):
        """Create figure and axis objects for debug plot."""

        self.dfig, self.dax = plt.subplots(4, 1, sharex=True)


    def __spawn_sensors(self):
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


    def print_devices_information(self):
        """Print information about active devices in stream."""

        print('\nDirector initialised for sensors:')
        # print sensors
        for sensor in self.sensors:
            print('-- {:<30}'.format(sensor))
        print()


    def new_event_data(self, event_data, cout=True):
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
                model_tx    = hlp.ux2tx(sensor.model['unixtime'])
                forecast_tx = hlp.ux2tx(sensor.local_forecast['unixtime'])
                self.hax[i].plot(model_tx, sensor.model['temperature'],             color=stl.NS[1],                 label='Temperature')
                self.hax[i].axvline(model_tx[-1], color='k', linestyle='--', label='Time Now')
                if len(sensor.forecast['temperature']) > 1:
                    self.hax[i].plot(forecast_tx, sensor.local_forecast['temperature'], color=stl.NS[1], linestyle='--', label='Forecast')
                if sum(sensor.local_forecast['unixtime']) > 0:
                    self.hax[i].fill_between(forecast_tx, sensor.local_forecast['lower_bound'], sensor.local_forecast['upper_bound'], color=stl.NS[1], alpha=0.33, label='Forecast Interval')
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

