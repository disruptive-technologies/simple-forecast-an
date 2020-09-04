# packages
import numpy             as np

# project
import forecast.helpers  as hlp
import config.parameters as prm


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


    def new_event_data(self, event_data):
        """
        Receive new event from Director and iterate algorithm.

        Parameters
        ----------
        event_data : dict
            Event json containing temperature data.

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
            self.__initialise_holt_winters()
        else:
            # iterate Holt-Winters
            self.__iterate_holt_winters()

        # forecast
        self.__model_forecast()


    def __initialise_holt_winters(self):
        """
        Calculate initial level, trend and seasonal component.
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

        # flip flag
        self.initialised = True


    def __iterate_holt_winters(self):
        """
        Update level, trend and seasonal component of Holt-Winters model.

        """

        # calculate level (l), trend (b), and season (s) components
        l = prm.alpha*(self.model['temperature'][-1] - self.model['season'][-prm.season_length]) + (1 - prm.alpha)*(self.model['level'][-1] + self.model['trend'][-1])
        b = prm.beta*(l - self.model['level'][-1]) + (1 - prm.beta)*self.model['trend'][-1]
        s = prm.gamma*(self.model['temperature'][-1] - self.model['level'][-1] - self.model['trend'][-1]) + (1 - prm.gamma)*self.model['season'][-prm.season_length]

        # append components
        self.model['level'].append(l)
        self.model['trend'].append(b)
        self.model['season'].append(s)


    def __model_forecast(self):
        """
        Holt-Winters n-step ahead forecasting and prediction interval calculation.
        Forecast based on: https://otexts.com/fpp2/prediction-intervals.html
        Prediction intervals based on: https://otexts.com/fpp2/prediction-intervals.html

        """

        # use average step length the last 24h
        tax = np.array(self.model['unixtime'])[np.array(self.model['unixtime']) > int(self.model['unixtime'][-1])-60*60*24]
        ux_step = np.mean(tax[1:] - tax[:-1])

        # forecast value
        fux = (prm.n_step_ahead+1)*ux_step
        fvv = self.model['level'][-1] + prm.n_step_ahead*self.model['trend'][-1] + self.model['season'][-prm.season_length + (prm.n_step_ahead-1)%prm.season_length]
        self.forecast['unixtime'].append(fux)
        self.forecast['temperature'].append(fvv)

        # calculate residual
        if len(self.forecast['temperature']) > prm.n_step_ahead:
            res = abs(self.model['temperature'][-1] - self.forecast['temperature'][-prm.n_step_ahead-1])
        else:
            res = 0
        self.forecast['residual'].append(res)

        # update residual standard deviation
        self.residual_std = np.std(np.array(self.forecast['residual'])[max(0, len(self.forecast['residual'])-prm.n_forecast):])


    def get_forecast(self, n):
        """
        Forecast n samples into the future using current HW state.

        Parameters
        ----------
        n : int
            Number of samples to forecast.

        """

        # initialise empty
        timestamp   = np.zeros(n)*np.nan
        temperature = np.zeros(n)*np.nan
        upper_bound = np.zeros(n)*np.nan
        lower_bound = np.zeros(n)*np.nan

        if len(self.model['season']) > prm.season_length:
            # use average step length the last 24h
            tax = np.array(self.model['unixtime'])[np.array(self.model['unixtime']) > int(self.model['unixtime'][-1])-60*60*24]
            ux_step = np.mean(tax[1:] - tax[:-1])
            for t in range(n):
                # holt winters forecast
                timestamp[t] = self.model['unixtime'][-1] + (t+1)*ux_step
                temperature[t] = self.model['level'][-1] + t*self.model['trend'][-1] + self.model['season'][-prm.season_length + (t-1)%prm.season_length]

                # prediction interval
                k = ((t-1)/prm.season_length)
                upper_bound[t] = temperature[t] + self.residual_std*np.sqrt(k+1)*prm.bound_modifier
                lower_bound[t] = temperature[t] - self.residual_std*np.sqrt(k+1)*prm.bound_modifier

        return timestamp, temperature, upper_bound, lower_bound


