# packages
import sys
import argparse
import datetime
import numpy  as np
import pandas as pd


def convert_event_data_timestamp(ts):
    """Convert the default event_data timestamp format to Pandas and unixtime format.

    Parameters:
        ts -- event_data timestamp format

    Returns:
        timestamp -- Pandas Timestamp object format.
        unixtime  -- Integer number of seconds since 1 January 1970.

    """

    timestamp = pd.to_datetime(ts)
    unixtime  = pd.to_datetime(np.array([ts])).astype(int)[0] // 10**9

    return timestamp, unixtime


def ux2tx(ux):
    """Convert unixtime to datetime format.

    parameters:
        ux -- Unixtime integer.

    returns:
        dt -- Datetime format.
    """

    # create datetime
    dt = pd.to_datetime(ux, unit='s')

    return dt

    
def print_error(text, terminate=True):
    """Print an error to console.
    
    parameters:
        text      -- String to be printed with error.
        terminate -- Terminates execution if True.
    """

    print('ERROR: {}'.format(text))
    if terminate:
        sys.exit()


def loop_progress(i_track, i, N_max, N_steps, name=None, acronym=' '):
    """ print progress to console

    arguments:
    i_track:    tracks how far the progress has come:
    i:          what the current index is.
    N_max:      the maximum value which indicates progress done.
    N_steps:    how many steps which are counted.
    """

    # number of indices in each progress element
    part = N_max / N_steps

    if i_track == 0:
        # print empty bar
        print('    |')
        if name is None:
            print('    └── Progress:')
        else:
            print('    └── {}:'.format(name))
        print('        ├── [ ' + (N_steps-1)*'-' + ' ] ' + acronym)
        i_track = 1
    elif i > i_track + part:
        # update tracker
        i_track = i_track + part

        # print bar
        print('        ├── [ ' + int(i_track/part)*'#' + (N_steps - int(i_track/part) - 1)*'-' + ' ] ' + acronym)

    # return tracker
    return i_track


def dt_timestamp_format(tx):
    """Convert datetime object to DT timestamp format.

    parameters:
        tx -- Datetime object.

    returns:
        dtt -- DT timestamp format.
    """

    year   = '{:04}'.format(tx.year)
    month  = '{:02}'.format(tx.month)
    day    = '{:02}'.format(tx.day)
    hour   = '{:02}'.format(tx.hour)
    minute = '{:02}'.format(tx.minute)
    second = '{:02}'.format(tx.second)

    dtt = year + '-' + month + '-' + day + 'T' + hour + ':' + minute + ':' + second + 'Z'
    return dtt


def api_json_format(timestamp, temperature):
    """Imitate API json format.

    parameters:
        timestamp   -- Event UTC timestamp.
        temperature -- Event temperature value.

    returns:
        json -- API json format.
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
    """Import file as event history json format.

    parameters:
        path -- Absolute path to file.

    returns:
        events -- List of historic events.
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
    """Algebraic linear regression.

    parameters:
        x -- x-axis of data to be fitted.
        y -- y-axis of data to be fitted.

    returns:
        alpha -- Line interscept.
        beta  -- Line slope.
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
    """Return the event update time converted to unixtime.

    Parameters:
        json -- Event data json.

    Returns:
        unixtime -- Event data update time converted to unixtime.
    """

    timestamp = json['data']['temperature']['updateTime']
    _, unixtime = convert_event_data_timestamp(timestamp)
    return unixtime
