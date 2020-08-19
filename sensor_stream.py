# project
from forecast.director import Director

# Fill in from the Service Account and Project:
USERNAME   = "bsarver24te000b24bpg"       # this is the key
PASSWORD   = "8362c483e011479fb1066d9b20a0817b"     # this is the secret
PROJECT_ID = "bsarslgg7oekgsc2jb20"                # this is the project id

# set url base
API_URL_BASE = "https://api.disruptive-technologies.com/v2"


if __name__ == '__main__':

    # initialise Director instance
    d = Director(USERNAME, PASSWORD, PROJECT_ID, API_URL_BASE)

    # iterate historic events
    d.run_history()

    # stream realtime events
    d.run_stream(n_reconnects=5)

