# packages
import sys
import numpy  as np
import pandas as pd


def convert_event_data_timestamp(ts):
    """
    Convert the default event_data timestamp format to Pandas and unixtime format.

    Parameters
    ----------
    ts : str
        UTC timestamp in custom API event data format.

    Returns
    -------
    timestamp : datetime
        Pandas Timestamp object format.
    unixtime : int
        Integer number of seconds since 1 January 1970.

    """

    timestamp = pd.to_datetime(ts)
    unixtime  = pd.to_datetime(np.array([ts])).astype(int)[0] // 10**9

    return timestamp, unixtime


def ux2tx(ux):
    """
    Convert unixtime to datetime format.

    Parameters
    ----------
    ux : int 
        Time in number of seconds in 01-01-1970.

    Returns
    -------
    dt : datetime 
        Time in Pandas datetime format.

    """

    # create datetime
    dt = pd.to_datetime(ux, unit='s')

    return dt

    
def print_error(text, terminate=True):
    """
    Print an error message and terminate as desired.

    Parameters
    ----------
    terminate : bool
        Terminate execution if True.
    """

    print('ERROR: {}'.format(text))
    if terminate:
        sys.exit()


def loop_progress(i_track, i, n_max, n_steps, name=None, acronym=' '):
    """
    Print loop progress to console.

    Parameters
    ----------
    i_track : int
        Tracks how far the progress has come:
    i : int
        Current index in loop.
    n_max : int
        Maximum value which indicates progress done.
    n_steps : int
        Number of steps to be counted.
    name : str
        Title of progress print.
    acronym : str 
        An acronym to put after progress bar.

    """

    # number of indices in each progress element
    part = n_max / n_steps

    if i_track == 0:
        # print empty bar
        print('    |')
        if name is None:
            print('    └── Progress:')
        else:
            print('    └── {}:'.format(name))
        print('        ├── [ ' + (n_steps-1)*'-' + ' ] ' + acronym)
        i_track = 1
    elif i > i_track + part:
        # update tracker
        i_track = i_track + part

        # print bar
        print('        ├── [ ' + int(i_track/part)*'#' + (n_steps - int(i_track/part) - 1)*'-' + ' ] ' + acronym)

    # return tracker
    return i_track


def dt_timestamp_format(tx):
    """
    Convert datetime object to DT timestamp format.

    Parameters
    ----------
    tx : Pandas datetime object.

    Returns
    -------
    dtt : str 
        DT timestamp format.

    """

    # isolate each component
    year   = '{:04}'.format(tx.year)
    month  = '{:02}'.format(tx.month)
    day    = '{:02}'.format(tx.day)
    hour   = '{:02}'.format(tx.hour)
    minute = '{:02}'.format(tx.minute)
    second = '{:02}'.format(tx.second)

    # combine string
    dtt = year + '-' + month + '-' + day + 'T' + hour + ':' + minute + ':' + second + 'Z'

    return dtt


def api_json_format(timestamp, temperature):
    """
    Imitate API json format.

    Parameters
    ----------
    timestamp : str 
        Event UTC timestamp.
    temperature : float 
        Event temperature value.

    Returns
    -------
    json : dict 
        API json format.

    """

    json = {
        'targetName': 'local_file',
        'data': {
            'temperature': {
                'value':      temperature,
                'updateTime': timestamp,
            }
        }
    }

    return json


def import_as_event_history(path):
    """
    Import file as event history json format.

    Parameters
    ----------
    path : str 
        Absolute path to file.

    Returns
    -------
    events : list 
        List of historic events.

    """

    # initialise output list
    events = []

    # import through pandas dataframe
    df = pd.read_csv(path)

    # verify columns existance
    if not 'temperature' in df.columns or not 'unix_time' in df.columns:
        print_error('Imported file should have columns \'temperature\' and \'unix_time\'.')

    # extract UTC timestamps
    tx = pd.to_datetime(df['unix_time'], unit='s')

    # iterate events
    for i in range(len(df)):
        # convert unixtime to DT format
        timestamp = dt_timestamp_format(tx[i])

        # create event json format
        json = api_json_format(timestamp, df['temperature'].iloc[i])

        # append output
        events.append(json)

    return events


def algebraic_linreg(x, y):
    """
    Algebraic linear regression.

    Parameters
    ----------
    x : array_like 
        x-axis of data to be fitted.
    y : array_like 
        y-axis of data to be fitted.

    Returns
    -------
    alpha : float 
        Fitted line interscept.
    beta : float
        Fitted line slope.

    """

    s = {
        (0, 0): np.sum(np.ones_like(x)),
        (1, 0): np.sum(x),
        (0, 1): np.sum(y),
        (2, 0): np.sum(np.square(x)),
        (1, 1): np.sum(np.multiply(x, y)),
        (0, 2): np.sum(np.square(y))
    }

    beta = ((s[(0,0)]*s[(1,1)] - s[(1,0)]*s[(0,1)]) / 
             (s[(0,0)]*s[(2,0)] - s[(1,0)]**2))
    
    alpha = (s[(0,1)] - beta*s[(1,0)]) / s[(0,0)]

    return alpha, beta


def json_sort_key(json):
    """
    Return the event update time converted to unixtime.

    Parameters
    ----------
    json : dict 
        Event data json as dictionary.

    Returns
    -------
    unixtime : int 
        Event data update time in seconds since 01-01-1970.

    """

    timestamp = json['data']['temperature']['updateTime']
    _, unixtime = convert_event_data_timestamp(timestamp)

    return unixtime

