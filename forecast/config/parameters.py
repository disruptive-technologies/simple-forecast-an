
# Holt-Winters
alpha  = 0.02
beta   = 0.01
gamma  = 0.75
theta  = 10

# data related
season_length  = 7
n_seasons_init = 7

# forecast
n_forecast     = season_length*5
n_step_ahead   = max(1, int(n_forecast/2))
n_step_ahead   = season_length
bound_modifier = 1.96
