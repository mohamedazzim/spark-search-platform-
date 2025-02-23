# database.py
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import os
from typing import Dict, Union, List, Tuple
import logging

class Database:
    def __init__(self, db_path: str = "data/resumes.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self.setup_logging()
        Path("data").mkdir(exist_ok=True)
        self.table_created = False
    
    def setup_logging(self):
        """Set up logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='resume_search.log'
        )
        self.logger = logging.getLogger(__name__)

    def get_numeric_max_values(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate maximum values for numeric columns."""
        numeric_maxes = {}
        for col in df.columns:
            if df[col].dtype in [np.float64, np.int64]:
                try:
                    # Convert column to numeric, coerce errors to NaN
                    numeric_vals = pd.to_numeric(df[col], errors='coerce')
                    if not numeric_vals.isna().all():  # If column has valid numeric values 
                        max_val = float(numeric_vals.max())
                        if not np.isnan(max_val):
                            numeric_maxes[col] = max_val
                except Exception as e:
                    self.logger.warning(f"Error calculating max for column {col}: {e}")
        return numeric_maxes

    def create_table_from_df(self, df: pd.DataFrame) -> None:
        """Dynamically create table based on DataFrame columns."""
        try:
            columns = []
            for col in df.columns:
                if df[col].dtype in [np.float64, np.int64]:
                    col_type = "REAL"
                else:
                    col_type = "TEXT"
                columns.append(f'"{col}" {col_type}')
            
            columns_sql = ", ".join(columns)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TABLE IF EXISTS resumes")
                create_table_sql = f"CREATE TABLE resumes ({columns_sql})"
                cursor.execute(create_table_sql)
                
                # Create indexes for performance
                for col in df.columns:
                    try:
                        cursor.execute(f'CREATE INDEX "idx_{col}" ON resumes("{col}")')
                    except sqlite3.OperationalError as e:
                        self.logger.warning(f"Failed to create index for {col}: {e}")
                
                conn.commit()
                self.table_created = True
        except Exception as e:
            self.logger.error(f"Error creating table: {e}")
            raise

    def clean_numeric(self, value: Union[str, float, int]) -> float:
        """Clean and convert numeric values."""
        if pd.isna(value):
            return np.nan
        try:
            if isinstance(value, str):
                value = value.lower()
                for suffix in ['lpa', 'years', 'k', 'inr', '$']:
                    value = value.replace(suffix, '')
                value = value.strip()
            return float(value)
        except (ValueError, TypeError):
            return np.nan

    def clean_text(self, value: str) -> str:
        """Clean text values."""
        if pd.isna(value):
            return ""
        return str(value).strip()

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process and clean dataframe before insertion."""
        processed = df.copy()
        numeric_cols = processed.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            processed[col] = processed[col].apply(self.clean_numeric)
        text_cols = processed.select_dtypes(include=['object']).columns
        for col in text_cols:
            processed[col] = processed[col].apply(self.clean_text)
        return processed

    def insert_data(self, file_path: str) -> Tuple[bool, str, Dict[str, float]]:
        """Insert data from CSV/Excel file into the database."""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                raise ValueError("Unsupported file format")
            
            if not self.table_created:
                self.create_table_from_df(df)
            
            df_cleaned = self.process_dataframe(df)
            numeric_maxes = self.get_numeric_max_values(df_cleaned)
            
            with sqlite3.connect(self.db_path) as conn:
                df_cleaned.to_sql('resumes', conn, if_exists='replace', index=False)
            
            self.logger.info(f"Successfully inserted {len(df_cleaned)} records")
            return True, f"Successfully inserted {len(df_cleaned)} records", numeric_maxes
        except Exception as e:
            self.logger.error(f"Error inserting data: {e}")
            return False, f"Error inserting data: {str(e)}", {}

    def search_resumes(self, filters: Dict[str, Union[str, tuple, List[str]]]) -> pd.DataFrame:
        """Search resumes based on provided filters."""
        try:
            query = "SELECT * FROM resumes WHERE 1=1"
            params = []
            
            for column, value in filters.items():
                if value:
                    if isinstance(value, tuple):
                        query += f' AND "{column}" BETWEEN ? AND ?'
                        params.extend(value)
                    elif isinstance(value, list):
                        placeholders = ','.join(['?' for _ in value])
                        query += f' AND "{column}" IN ({placeholders})'
                        params.extend(value)
                    else:
                        query += f' AND LOWER("{column}") LIKE LOWER(?)'
                        params.append(f"%{value}%")
            
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn, params=params)
            return df
        except Exception as e:
            self.logger.error(f"Error searching resumes: {e}")
            return pd.DataFrame()

    def get_unique_values(self, column: str) -> List[str]:
        """Get unique values for a column."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = f'SELECT DISTINCT "{column}" FROM resumes WHERE "{column}" IS NOT NULL'
                df = pd.read_sql_query(query, conn)
                return sorted(df[column].dropna().unique().tolist())
        except Exception as e:
            self.logger.error(f"Error getting unique values for {column}: {e}")
            return []

    def get_column_stats(self, column: str) -> Dict[str, float]:
        """Get statistics for numeric columns."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = f'SELECT MIN("{column}"), MAX("{column}"), AVG("{column}") FROM resumes'
                cursor = conn.execute(query)
                min_val, max_val, avg_val = cursor.fetchone()
                return {
                    "min": float(min_val or 0),
                    "max": float(max_val or 0),
                    "avg": float(avg_val or 0)
                }
        except Exception as e:
            self.logger.error(f"Error getting column stats for {column}: {e}")
            return {"min": 0, "max": 0, "avg": 0}