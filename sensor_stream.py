# packages
import os
import sys
import json
import time
import pprint
import argparse
import requests
import datetime
import sseclient

# project
import forecast.helpers as     helpers
from forecast.director  import Director

# Fill in from the Service Account and Project:
username   = "bsarver24te000b24bpg"       # this is the key
password   = "8362c483e011479fb1066d9b20a0817b"     # this is the secret
project_id = "bsarslgg7oekgsc2jb20"                # this is the project id

# set url base
api_url_base = "https://api.disruptive-technologies.com/v2"

# reconnect on error or connection lost
MAX_RETRIES = 5


def json_sort_key(json):
    """Return the event update time converted to unixtime.

    Parameters:
        json -- Event data json.

    Returns:
        unixtime -- Event data update time converted to unixtime.
    """

    timestamp = json['data']['temperature']['updateTime']
    _, unixtime = helpers.convert_event_data_timestamp(timestamp)
    return unixtime


def get_event_history(devices, event_params):
    """Get list of historic event data.

    parameters:
        devices      -- List of devices in project.
        event_params -- Filters for historic event data.

    returns:
        events -- List of historic events sorted in time.
    """

    # initialise empty event list
    events = []

    # iterate devices
    for device in devices:
        # isolate device identifier
        device_id = os.path.basename(device['name'])
    
        # some printing
        print('-- Getting event history for {}'.format(device_id))
    
        # initialise next page token
        event_params['page_token'] = None
    
        # set endpoints for event history
        event_list_url = "{}/projects/{}/devices/{}/events".format(api_url_base, project_id, device_id)
    
        while event_params['page_token'] != '':
            event_listing = requests.get(event_list_url, auth=(username, password), params=event_params)
            event_json = event_listing.json()
    
            event_params['page_token'] = event_json['nextPageToken']
            events += event_json['events']
    
            if event_params['page_token'] is not '':
                print('\t-- paging')
    
    # sort by time
    events.sort(key=json_sort_key, reverse=False)

    return events


def parse_arguments():
    """Parse for command line arguments.

    Returns:
        arguments -- Dictionary of arguments.
        history   -- Flag to trigger historic event stream.
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
    arguments = vars(parser.parse_args())

    # set history flag
    if now == arguments['starttime']:
        history = False
    else:
        history = True

    return arguments, history


def get_devices():
    """Get list of devices in project.

    returns:
        devices -- List of devices.
    """

    # configure url
    devices_list_url = "{}/projects/{}/devices".format(api_url_base,  project_id)

    # ask for list
    device_listing   = requests.get(devices_list_url, auth=(username, password))
    
    # get list of Devices
    try:
        devices = device_listing.json()['devices']
    except KeyError:
        # probably connection issues if we error here
        helpers.print_error(device_listing.json(), terminate=True)

    return devices


def event_history_stream(d, events):  
    """Iterate historic event data.

    parameters:
        d      -- Director class object.
        events -- List of historic events.
    """

    # estimate occupancy for history 
    cc = 0
    for i, event_data in enumerate(events):
        cc = helpers.loop_progress(cc, i, len(events), 25, name='event history')

        # serve event to director
        d.new_event_data(event_data, cout=False)

        # debug
        if args['plot_debug']:
            d.plot_debug()
    
    # initialise plot
    if args['plot']:
        print('\nClose the blocking plot to start stream.')
        print('A new non-blocking plot will appear for stream.')
        d.initialise_plot()
        d.plot_progress(blocking=True)


def run_api():
    """Use a DT Studio Project through the API."""

    # set filters for event history and stream
    event_params  = {'page_size': 1000, 'start_time': args['starttime'], 'end_time': args['endtime'], 'event_types': ['temperature']}
    stream_params = {'event_types': ['temperature']}

    # Get list of Devices in Project via API
    devices = get_devices()

    # initialise Director with devices list
    d = Director(devices, args)

    # generate endpoints for stream
    devices_stream_url = "{}/projects/{}/devices:stream".format(api_url_base, project_id)

    # get devices event history
    if history:
        event_history_stream(d, get_event_history(devices, event_params))

    # Listen to all events from all Devices in Project via API
    stream(d, devices_stream_url, stream_params, n_reconnects=5)


def run_local():
    """Use a locally stored file."""

    # verify valid path
    if not os.path.exists(args['path']):
        helpers.print_error('Invalid path.')

    # make a fake list of devices
    devices = [{'name': 'local_file', 'type': 'temperature'}]

    # initialise director
    d = Director(devices, args)

    # import as json event data
    events = helpers.import_as_event_history(args['path'])

    # run event history
    event_history_stream(d, events)



def stream(d, devices_stream_url, stream_params, n_reconnects=5):
    """Stream events for sensors in project.

    parameters:
        d                  -- Director class object.
        devices_stream_url -- Url pointing to project.
        stream_params      -- Filters used in stream.
        n_reconnects       -- Number of retries if connection lost.
    """

    # cout
    print("Listening for events... (press CTRL-C to abort)")

    # reinitialise plot
    if args['plot']:
        d.initialise_plot()
        d.plot_progress(blocking=False)

    # loop indefinetly
    nth_reconnect = 0
    while nth_reconnect < n_reconnects:
        try:
            # reset reconnect counter
            nth_reconnect = 0
    
            # get response
            response = requests.get(devices_stream_url, auth=(username,password),headers={'accept':'text/event-stream'}, stream=True, params=stream_params)
            client = sseclient.SSEClient(response)
    
            # listen for events
            print('Connected.')
            for event in client.events():
                # new data received
                event_data = json.loads(event.data)['result']['event']
    
                # serve event to director
                d.new_event_data(event_data)
    
                # plot progress
                if args['plot']:
                    d.plot_progress(blocking=False)
        
        except requests.exceptions.ConnectionError:
            nth_reconnect += 1
            print('Connection lost, reconnection attempt {}/{}'.format(nth_reconnect, MAX_RETRIES))
        except requests.exceptions.ChunkedEncodingError:
            nth_reconnect += 1
            print('An error occured, reconnection attempt {}/{}'.format(nth_reconnect, MAX_RETRIES))
        
        # wait 1s before attempting to reconnect
        time.sleep(1)


if __name__ == '__main__':
    # parse arguments
    args, history = parse_arguments()

    # run from local file or from project through api
    if args['path'] is not None:
        run_local()
    else:
        run_api()

