# server.py
import os
import tempfile
import pandas as pd
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from database import Database
import logging
import json

# Initialize Flask app and set secret key
app = Flask(__name__)
app.secret_key = 'my_very_secret_key_1234567890'  # Use a secure key for production

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instantiate the database module
db = Database()

# Global variables to store uploaded data
global_df = None
global_columns = []

# Route for the login page
@app.route("/")
def index():
    return render_template("login.html")

# Dashboard route – currently no session check (for prototyping)
@app.route('/dashboard')
def dashboard():
    # To enforce authentication, uncomment the following lines:
    # if not session.get('logged_in'):
    #     return redirect(url_for('index'))
    return render_template("dashboard.html")

# Login endpoint – expects JSON payload with hard-coded credentials
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if username == "Admin" and password == "Admin@123":
        session['logged_in'] = True
        return jsonify({"status": "success", "message": "Login successful!"})
    else:
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

# File upload endpoint – accepts a file, inserts data via the Database module, and returns column names
@app.route('/upload', methods=['POST'])
def upload_file():
    global global_df, global_columns
    file = request.files.get('file')
    if not file:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as temp_file:
            temp_file.write(file.read())
            temp_path = temp_file.name

        # Insert data into the database and get numeric max values
        success, message, numeric_maxes = db.insert_data(temp_path)
        if success:
            # Read the file to obtain a DataFrame and extract column names
            if file.filename.endswith('.csv'):
                df = pd.read_csv(temp_path)
            else:
                df = pd.read_excel(temp_path)
            global_df = df
            global_columns = df.columns.tolist()
            response = {
                "status": "success",
                "message": message,
                "columns": global_columns,
                "numericMax": numeric_maxes  # Include numeric max values in response
            }
        else:
            response = {"status": "error", "message": message}
        os.unlink(temp_path)  # Remove the temporary file
        return jsonify(response)
    except Exception as e:
        logger.error("Error in file upload: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/search', methods=['POST'])
def search():
    global global_df
    # Temporarily disable session check for testing:
    # if not session.get('logged_in'):
    #     return jsonify({"status": "error", "message": "Not logged in"}), 403
    if global_df is None:
        return jsonify({"status": "error", "message": "No data available"}), 400
    data = request.get_json()
    filters = data.get('filters', {})
    selected_columns = data.get('selectedColumns', [])
    filtered_df = global_df.copy()

    try:
        # Apply filters (range or text search)
        for column, filter_values in filters.items():
            if "range" in filter_values:
                min_range, max_range = filter_values["range"]
                filtered_df = filtered_df[(filtered_df[column] >= min_range) & (filtered_df[column] <= max_range)]
            elif "text" in filter_values:
                filtered_df = filtered_df[
                    filtered_df[column].astype(str).str.contains(filter_values["text"], case=False, na=False)
                ]
        if selected_columns:
            filtered_df = filtered_df[selected_columns]

        # Replace NaN values with the string "None"
        filtered_df = filtered_df.where(pd.notnull(filtered_df), "None")

        # Debug: Log the filtered DataFrame
        logger.info("Filtered DataFrame:\n%s", filtered_df)

        # Convert DataFrame to a list of dictionaries
        results = filtered_df.to_dict(orient='records')

        response = {
            "status": "success",
            "results": json.loads(json.dumps(results, default=str)),
            "record_count": len(results)
        }
        return jsonify(response)
    except ValueError as ve:
        logger.error("ValueError encountered: %s", ve)
        return jsonify({"status": "error", "message": "Invalid value encountered"}), 400
    except KeyError as ke:
        logger.error("KeyError encountered: %s", ke)
        return jsonify({"status": "error", "message": "Invalid key encountered"}), 400
    except Exception as e:
        logger.error("Unexpected error encountered: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
