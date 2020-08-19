
# Holt-Winters
alpha  = 0.02       # level smoothing factor
beta   = 0.01       # trend smoothing factor
gamma  = 0.75       # season smoothing factor

# data related
season_length  = 110    # number of samples in a season
n_seasons_init = 7      # number of seasons used in HW initialisation

# forecast
n_forecast     = season_length*2            # number of samples to forecast
n_step_ahead   = season_length              # number of samples ahead to use for residual
bound_modifier = 1.96                       # scaler for bounds

