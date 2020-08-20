# project
from forecast.director import Director

# Fill in from the Service Account and Project:
USERNAME   = "SERVICE_ACCOUNT_KEY"       # this is the key
PASSWORD   = "SERVICE_ACCOUT_SECRET"     # this is the secret
PROJECT_ID = "PROJECT_ID"                # this is the project id

# set url base
API_URL_BASE = "https://api.disruptive-technologies.com/v2"


if __name__ == '__main__':

    # initialise Director instance
    d = Director(USERNAME, PASSWORD, PROJECT_ID, API_URL_BASE)

    # iterate historic events
    d.run_history()

    # stream realtime events
    d.run_stream(n_reconnects=5)

