import sqlite3
import pandas as pd

def create_and_populate_tables(db_name = 'sensor_data.db'):
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Define table names and corresponding csv file paths
    tables = {
        "temperature": "sample/temperature.csv",
        "humidity": "sample/humidity.csv",
        "light": "sample/light.csv"
    }

    for table_name, csv_file in tables.items():
        # Read csv file into pandas dataframe
        df = pd.read_csv(csv_file)

        # Write dataframe to SQLite database
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print (f"Table {table_name} created and populated with data from {csv_file}")
    
    # Close connection
    conn.close()

if __name__ == "__main__":
    create_and_populate_tables()