# Import necessary libraries
import numpy as np  # For numerical operations and array handling
import pandas as pd  # For data manipulation and reading CSV files
from sklearn.preprocessing import MinMaxScaler  # For normalizing the data
from sklearn.metrics import mean_absolute_error  # For calculating Mean Absolute Error
from sklearn.metrics import mean_absolute_percentage_error  # For calculating Mean Absolute Percentage Error
import xgboost as xgb  # For using XGBoost model
import os  # For file operations

# Define hyperparameters
split = 0.85  # Proportion of data to use for training (85%)
sequence_length = 10  # Number of previous days to use as features for prediction
epochs = 100  # Number of boosting rounds (though XGBoost calls them n_estimators)
learning_rate = 0.01  # Learning rate for the model

# Create models folder if it doesn't exist
models_folder = "models"  # Folder to save models
if not os.path.exists(models_folder):  # Check if folder exists
    os.makedirs(models_folder)  # Create folder if not

# Load stock price data from CSV file
stock_data = pd.read_csv("stock_price.csv")  # Read the stock price data
column = ['Close']  # Specify the column to use for prediction (closing price)

# Get the total length of the stock data
len_stock_data = stock_data.shape[0]

# Split data into training and testing sets
train_examples = int(len_stock_data * split)  # Calculate number of training examples
train = stock_data.get(column).values[:train_examples]  # Get training data
test = stock_data.get(column).values[train_examples:]  # Get testing data
len_train = train.shape[0]  # Length of training data
len_test = test.shape[0]  # Length of testing data

# Normalize the data using MinMaxScaler
scaler = MinMaxScaler()  # Initialize the scaler
train = scaler.fit_transform(train)  # Fit and transform training data
test = scaler.transform(test)  # Transform testing data (using training fit)

# Prepare training data: create features (X) and target (y)
X_train = []  # List to hold feature sequences
y_train = []  # List to hold target values
for i in range(sequence_length, len_train):  # Start from sequence_length to have enough history
    X_train.append(train[i - sequence_length:i].flatten())  # Flatten the sequence into features
    y_train.append(train[i])  # Target is the next day's price
X_train = np.array(X_train).astype(float)  # Convert to numpy array
y_train = np.array(y_train).astype(float)  # Convert to numpy array

# Prepare testing data: create features (X) and target (y)
X_test = []  # List to hold feature sequences
y_test = []  # List to hold target values
for i in range(sequence_length, len_test):  # Start from sequence_length
    X_test.append(test[i - sequence_length:i].flatten())  # Flatten the sequence
    y_test.append(test[i])  # Target
X_test = np.array(X_test).astype(float)  # Convert to numpy array
y_test = np.array(y_test).astype(float)  # Convert to numpy array

# Inverse transform y_test to original scale for evaluation
y_test = scaler.inverse_transform(y_test)

# Function to create and train the XGBoost model
def model_create():
    # Set random seed for reproducibility
    np.random.seed(1234)
    
    # Create XGBoost regressor model
    model = xgb.XGBRegressor(
        n_estimators=epochs,  # Number of boosting rounds
        learning_rate=learning_rate,  # Learning rate
        random_state=1234,  # Random seed
        objective='reg:squarederror'  # Objective for regression
    )
    
    # Fit the model on training data
    model.fit(X_train, y_train)
    
    return model

# Function to make predictions on test set
def predict(model):
    predictions = model.predict(X_test)  # Predict using the model
    predictions = scaler.inverse_transform(predictions.reshape(-1, 1))  # Inverse transform to original scale
    return predictions

# Function to evaluate the model performance
def evaluate(predictions):
    mae = mean_absolute_error(predictions, y_test)  # Calculate MAE
    mape = mean_absolute_percentage_error(predictions, y_test)  # Calculate MAPE
    accuracy = 1 - mape  # Calculate accuracy as 1 - MAPE
    return mae, mape, accuracy

# Function to run the model multiple times and average results
def run_model(n):
    total_mae = 0  # Accumulate MAE
    total_mape = 0  # Accumulate MAPE
    total_acc = 0  # Accumulate accuracy
    for i in range(n):  # Run n times
        model = model_create()  # Create and train model
        predictions = predict(model)  # Make predictions
        mae, mape, acc = evaluate(predictions)  # Evaluate
        total_mae += mae
        total_mape += mape
        total_acc += acc
        
        # Save the model
        model_path = os.path.join(models_folder, f"xgb_model_run_{i}.json")  # Path to save model
        model.save_model(model_path)  # Save the model
        print(f"Model saved to {model_path}")  # Print save confirmation
    
    # Return averages and last predictions
    return (total_mae / n), (total_mape / n), (total_acc / n), predictions.tolist()

# Run the model once and print results
mae, mape, acc, preds = run_model(1)

# Print the evaluation metrics
print(f"Mean Absolute Error = {mae}")
print(f"Mean Absolute Percentage Error = {mape}%")
print(f"Accuracy = {acc}")