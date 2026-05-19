import os

# Data Settings
TICKER = "AAPL"
PERIOD = "10y"
TEST_SIZE = 0.2

# Directories
DIRS = {
    'MODELS': 'models',
    'RESULTS': 'results',
    'PLOTS': 'results/plots',
    'DATA': 'data'
}

for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

def get_model_path(model_name):
    return os.path.join(DIRS['MODELS'], f"{TICKER}_{model_name}.pkl")

def get_result_path(filename):
    return os.path.join(DIRS['RESULTS'], f"{TICKER}_{filename}")

def get_plot_path(filename):
    return os.path.join(DIRS['PLOTS'], f"{TICKER}_{filename}")
