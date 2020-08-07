# Simple Transformer Temperature Forecasting

## What am I?
This repository contains the example code talked about in [this application note (LINK PENDING)](https://www.disruptive-technologies.com/) proposing a method of using the Disruptive Technologies (DT) Wireless Temperature Sensors for forecasting future values by simple signal modelling. Written in Python 3, it implements the DT Developer API to communicate with a DT Studio project and its sensors. By calling sensor_stream.py, a contineous temperature forecast will be calculated for previous history data and/or a live stream of datapoints from the moment of execution.

## Before Running Any code
A DT Studio project containing temperature sensors should be made. All temperature sensors in the project will attemped forecasted upon.

## Environment Setup
Install dependencies.
```
pip install -r requirements.txt
```

Edit *sensor_stream.py* to provide the following authentication details of your project. Information about setting up your project for API authentication can be found in this [streaming API guide](https://support.disruptive-technologies.com/hc/en-us/articles/360012377939-Using-the-stream-API).
```python
username   = "SERVICE_ACCOUNT_KEY"       # this is the key
password   = "SERVICE_ACCOUT_SECRET"     # this is the secret
project_id = "PROJECT_ID"                # this is the project id
```

## Usage
Running *python3 sensor_stream.py* will start streaming data from all sensors in your project for which a forecast be calculated for either historic data using *--starttime* flag, a stream, or both. Provide the *--plot* flag to visualise the results. 
```
usage: sensor_stream.py [-h] [--path] [--starttime] [--endtime] [--plot]
                        [--plot-init] [--plot-debug]

Temperature forecast on Stream and Event History.

optional arguments:
  -h, --help    show this help message and exit
  --path        Absolute path to local .csv file.
  --starttime   Event history UTC starttime [YYYY-MM-DDTHH:MM:SSZ].
  --endtime     Event history UTC endtime [YYYY-MM-DDTHH:MM:SSZ].
  --plot        Plot the resulting forecast.
  --plot-init   Plot the initialization results.
  --plot-debug  Plot algorithm operation.
```

It is essential that the user inspects the properties of their data and configure the parameters in *./forecast/config/parameters.py* accordingly as no one configuration can work for all data. 

Note: When using the *--starttime* argument for a date far back in time, if many sensors exist in the project, the paging process might take several minutes.



