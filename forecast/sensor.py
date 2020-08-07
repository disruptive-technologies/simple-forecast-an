# packages
import sys
import numpy             as np
import matplotlib.pyplot as plt

# project
import forecast.helpers           as hlp
import forecast.config.styling    as stl
import forecast.config.parameters as prm


class Sensor():
    """
    One Sensor object for each sensor in project.
    It keeps track of the algorithm state between events.
    When new event_data json is received, iterate algorithm one sample.
    """

    def __init__(self, device, device_id, args):
        # give to self
        self.device    = device
        self.device_id = device_id
        self.args      = args

        # contains level, trend and season for modelled data
        self.model = {
            'unixtime':          [], # shared unixtime timeaxis
            'temperature':       [], # temperature values
            'level':             [], # modeled level
            'trend':             [], # modeled trend
            'season':            [], # modeled season
        }

        # contains latest n-day forecast
        self.local_forecast = {
            'unixtime':       np.zeros(prm.n_forecast), # shared unixtime timeaxis
            'temperature':    np.zeros(prm.n_forecast), # forecasted temperature values
            'upper_bound':    np.zeros(prm.n_forecast), # upper confidence bounds
            'lower_bound':    np.zeros(prm.n_forecast), # lower confidence bounds
        }

        # contains all previous forecasts in history
        self.forecast = {
            'unixtime':    [], # shared unixtime timeaxis
            'temperature': [], # temperature values
            'residual':    [], # forecast residual
        }

        # variables
        self.n_samples    = 0 # number of event samples received
        self.initialised  = False
        self.residual_std = 0


    def initialise_init_plot(self):
        self.ifig, self.iax = plt.subplots(3, 1, sharex=True)


    def new_event_data(self, event_data):
        """Receive new event from Director and iterate algorithm.

        parameters:
            event_data -- Event json containing temperature data.
        """

        # convert timestamp to unixtime
        _, unixtime = hlp.convert_event_data_timestamp(event_data['data']['temperature']['updateTime'])

        # append new temperature value
        self.model['unixtime'].append(unixtime)
        self.model['temperature'].append(event_data['data']['temperature']['value'])
        self.n_samples += 1

        # initialise holt winters
        if self.n_samples < prm.season_length * prm.n_seasons_init:
            return
        elif not self.initialised:
            self.initialise_holt_winters()
        else:
            # iterate Holt-Winters
            self.iterate_holt_winters()

        # forecast
        self.model_forecast()


    def initialise_holt_winters(self):
        """Calculate initial level, trend and seasonal component.
        Based on: https://robjhyndman.com/hyndsight/hw-initialization/
        """

        # convert to numpy array for indexing
        temperature = np.array(self.model['temperature'])

        # fit a 3xseason moving average to temperature
        ma = np.zeros(self.n_samples)
        for i in range(self.n_samples):
            # define ma interval
            xl = max(0,              i - int(1.5*prm.season_length))
            xr = min(self.n_samples, i + int(1.5*prm.season_length+1))

            # mean
            ma[i] = np.mean(temperature[xl:xr])

        # subtract moving average
        df = temperature - ma

        # generate average seasonal component
        avs = []
        for i in range(prm.season_length):
            avs.append(np.mean([df[i+j*prm.season_length] for j in range(prm.n_seasons_init)]))

        # expand average season into own seasonal component
        for i in range(self.n_samples):
            self.model['season'].append(avs[i%len(avs)])

        # subtract initial season from original temperature to get adjusted temperature
        adjusted = temperature - np.array(self.model['season'])

        # fit a linear trend to adjusted temperature
        xax  = np.arange(self.n_samples)
        a, b = hlp.algebraic_linreg(xax, adjusted)
        linreg = a + xax*b

        # set initial level, slope, and brutlag deviation
        for i in range(self.n_samples):
            self.model['level'].append(linreg[i])
            self.model['trend'].append(b)

        if self.args['plot_init']:
            self.initialise_init_plot()
            self.init_plot(adjusted)

        # flip flag
        self.initialised = True


    def iterate_holt_winters(self):
        """Update level, trend and seasonal component of Holt-Winters model."""

        # calculate level (l), trend (b), and season (s) components
        l = prm.alpha*(self.model['temperature'][-1] - self.model['season'][-prm.season_length]) + (1 - prm.alpha)*(self.model['level'][-1] + self.model['trend'][-1])
        b = prm.beta*(l - self.model['level'][-1]) + (1 - prm.beta)*self.model['trend'][-1]
        s = prm.gamma*(self.model['temperature'][-1] - self.model['level'][-1] - self.model['trend'][-1]) + (1 - prm.gamma)*self.model['season'][-prm.season_length]

        # append components
        self.model['level'].append(l)
        self.model['trend'].append(b)
        self.model['season'].append(s)


    def model_forecast(self):
        """Holt-Winters n-step ahead forecasting and prediction interval calculation.
        Forecast based on: https://otexts.com/fpp2/prediction-intervals.html
        Prediction intervals based on: https://otexts.com/fpp2/prediction-intervals.html
        """

        # use average step length the last 24h
        tax = np.array(self.model['unixtime'])[np.array(self.model['unixtime']) > int(self.model['unixtime'][-1])-60*60*24]
        ux_step = np.mean(tax[1:] - tax[:-1])

        for t in range(prm.n_forecast):
            # holt winters forecast
            self.local_forecast['unixtime'][t] = self.model['unixtime'][-1] + (t+1)*ux_step
            self.local_forecast['temperature'][t] = self.model['level'][-1] + t*self.model['trend'][-1] + self.model['season'][-prm.season_length + (t-1)%prm.season_length]

            # prediction interval
            k = ((t-1)/prm.season_length)
            self.local_forecast['upper_bound'][t] = self.local_forecast['temperature'][t] + self.residual_std*np.sqrt(k+1)*prm.bound_modifier
            self.local_forecast['lower_bound'][t] = self.local_forecast['temperature'][t] - self.residual_std*np.sqrt(k+1)*prm.bound_modifier

        # append forecast
        self.forecast['unixtime'].append(self.local_forecast['unixtime'][min(prm.n_step_ahead-1, prm.n_forecast-1)])
        self.forecast['temperature'].append(self.local_forecast['temperature'][min(prm.n_step_ahead-1, prm.n_forecast-1)])

        # calculate residual
        if len(self.forecast['temperature']) > prm.n_step_ahead:
            res = abs(self.model['temperature'][-1] - self.forecast['temperature'][-prm.n_step_ahead-1])
        else:
            res = 0
        self.forecast['residual'].append(res)

        # update residual standard deviation
        self.residual_std = np.std(np.array(self.forecast['residual'])[max(0, len(self.forecast['residual'])-prm.n_forecast):])


    def init_plot(self, adjusted):
        """Plot the initialization results.

        parameters:
            adjusted -- Seasonally adjusted temperature data.
        """

        self.iax[0].plot(self.model['temperature'], color=stl.NS[1], label='Temperature')
        self.iax[0].plot(adjusted, color=stl.VB[1], label='Adjusted Temperature')
        self.iax[0].plot(self.model['level'], color=stl.SS[1], label='Initial Level')
        self.iax[0].legend(loc='upper left')

        self.iax[1].plot(self.model['trend'], color=stl.SS[1], label='Initial Trend')
        self.iax[1].legend(loc='upper left')

        self.iax[2].plot(df,  color=stl.NS[1], label='Differentiated')
        self.iax[2].plot(self.model['season'], color=stl.SS[1], label='Initial Season')
        self.iax[2].legend(loc='upper left')
        plt.show()


