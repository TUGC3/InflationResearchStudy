"""
rent_inflation_tufe.py
Specialized rent inflation calculator with city and room-count grouping
Groups rent data by city + room count, aggregates, and integrates with TUFE weighting
"""

import os
import sys
import pandas as pd
import numpy as np
import re
import glob
from pathlib import Path
from typing import Dict, List, Tuple, Optional

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from inflation_engine_tufe import TUFEInflationEngine


class RentInflationTUFE:
    """Specialized rent inflation calculation with city and room-count grouping"""
    
    def __init__(self, tufe_parser=None):
        """
        Initialize rent calculator
        
        Args:
            tufe_parser: Pre-loaded TUFEParser instance
        """
        self.engine = TUFEInflationEngine(tufe_parser=tufe_parser)
    
    def extract_room_count(self, product_name: str) -> Optional[int]:
        """
        Extract room count from product name
        
        Examples:
            "1 Bedroom Apartment" -> 1
            "2-BR Home" -> 2
            "3 Oda Daire" -> 3
            "Studio Apartment" -> 0
            
        Args:
            product_name: Product name to parse
            
        Returns:
            Room count or None if not found
        """
        if pd.isna(product_name):
            return None
        
        product_name = str(product_name).lower()
        
        # Patterns: digit + (bedroom|br|oda)
        patterns = [
            r'(\d+)\s*(?:bedroom|br|bedrooms|oda|odalı)',  # "2 bedroom" or "2 oda"
            r'(\d+)\s*\+?\s*(?:bed)',  # "2 bed"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, product_name)
            if match:
                return int(match.group(1))
        
        # Studio/T1 special cases
        if any(term in product_name for term in ['studio', 'y.0', 't0', 't+0']):
            return 0
        
        return None
    
    def load_rent_data_by_city(self, base_dir: str) -> Dict[str, pd.DataFrame]:
        """
        Load rent data grouped by city
        
        Args:
            base_dir: Base directory containing city subdirectories
            
        Returns:
            Dictionary mapping city names to DataFrames
        """
        city_data = {}
        
        if not os.path.exists(base_dir):
            print(f"❌ Directory not found: {base_dir}")
            return city_data
        
        # List all city subdirectories
        cities = [d for d in os.listdir(base_dir) 
                 if os.path.isdir(os.path.join(base_dir, d))]
        
        print(f"📂 Found {len(cities)} cities in {base_dir}")
        
        for city in cities:
            city_path = os.path.join(base_dir, city)
            
            # Load all CSV files in this city
            files = glob.glob(os.path.join(city_path, "*.csv"))
            
            if not files:
                continue
            
            city_dfs = []
            for file_path in files:
                try:
                    df = self.engine.load_rent_data_with_tufe(city_path)
                    if not df.empty:
                        city_dfs.append(df)
                except Exception as e:
                    print(f"  ⚠️ Error loading {file_path}: {e}")
            
            if city_dfs:
                city_data[city] = pd.concat(city_dfs, ignore_index=True)
                print(f"  ✓ {city}: {len(city_data[city])} records")
        
        return city_data
    
    def aggregate_city_data(self, city_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Aggregate rent data by city + room count
        
        Args:
            city_data: Dictionary of city DataFrames
            
        Returns:
            Aggregated DataFrame with [Date, City, RoomCount, AvgPrice]
        """
        all_data = []
        
        for city, df in city_data.items():
            if df.empty:
                continue
            
            df = df.copy()
            
            # Extract room count from product name
            df['RoomCount'] = df['ProductName'].apply(self.extract_room_count)
            
            # Group by (Date, RoomCount) and calculate average price
            grouped = df.groupby([df['Date'].dt.date, 'RoomCount']).agg({
                'Active_Price': 'mean',
                'Store': 'count'  # Count of records
            }).reset_index()
            
            grouped.columns = ['Date', 'RoomCount', 'AvgPrice', 'SampleSize']
            grouped['City'] = city
            grouped['Date'] = pd.to_datetime(grouped['Date'])
            
            all_data.append(grouped)
        
        if not all_data:
            return pd.DataFrame()
        
        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values(['City', 'RoomCount', 'Date'])
        
        return result
    
    def calculate_city_inflation(self, city_data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate month-over-month inflation by city and room count
        
        Args:
            city_data: Aggregated city data
            
        Returns:
            DataFrame with [YearMonth, City, RoomCount, Inflation_%]
        """
        if city_data.empty:
            return pd.DataFrame()
        
        city_data = city_data.copy()
        city_data['YearMonth'] = city_data['Date'].dt.strftime('%Y-%m')
        
        # Group by (City, RoomCount, YearMonth) and calculate average price
        monthly = city_data.groupby(['City', 'RoomCount', 'YearMonth']).agg({
            'AvgPrice': 'mean',
            'SampleSize': 'sum'
        }).reset_index()
        
        # Calculate month-over-month inflation
        monthly = monthly.sort_values(['City', 'RoomCount', 'YearMonth'])
        
        monthly['Inflation_%'] = (
            monthly.groupby(['City', 'RoomCount'])['AvgPrice'].pct_change() * 100
        ).round(2)
        
        # Drop first month for each (City, RoomCount) pair
        monthly = monthly.dropna(subset=['Inflation_%'])
        
        return monthly[[
            'YearMonth', 'City', 'RoomCount', 'Inflation_%', 'SampleSize'
        ]]
    
    def calculate_country_rent_inflation(self, city_inflation: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate city inflation to country level using sample-size weighting
        
        Args:
            city_inflation: City-level inflation data
            
        Returns:
            DataFrame with [YearMonth, Rent_Inflation_%]
        """
        if city_inflation.empty:
            return pd.DataFrame()
        
        # Group by YearMonth and calculate weighted average
        country_inflation = city_inflation.groupby('YearMonth').apply(
            lambda x: (x['Inflation_%'] * x['SampleSize']).sum() / x['SampleSize'].sum()
            if x['SampleSize'].sum() > 0 else 0.0
        ).reset_index(name='Rent_Inflation_%')
        
        country_inflation['Rent_Inflation_%'] = country_inflation['Rent_Inflation_%'].round(2)
        
        return country_inflation
    
    def run_rent_analysis(self, input_dir: str, output_dir: str) -> Dict:
        """
        Run full rent inflation analysis and save reports
        
        Args:
            input_dir: Input directory with city subdirectories
            output_dir: Output directory for reports
            
        Returns:
            Dictionary with analysis results
        """
        print(f"\n🏠 Rent Inflation Analysis (City + Room-Count Grouping)")
        print(f"📂 Input: {input_dir}")
        print(f"📂 Output: {output_dir}")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Load city data
        print(f"\n📥 Loading rent data by city...")
        city_data = self.load_rent_data_by_city(input_dir)
        
        if not city_data:
            print("⚠️ No city data loaded")
            return {}
        
        # Aggregate data
        print(f"\n🔀 Aggregating by city and room count...")
        aggregated = self.aggregate_city_data(city_data)
        
        if aggregated.empty:
            print("⚠️ No aggregated data")
            return {}
        
        print(f"  ✓ {len(aggregated)} city-room records")
        
        # Save aggregated data
        aggregated_path = os.path.join(output_dir, 'rent_city_roomcount_aggregated.csv')
        aggregated.to_csv(aggregated_path, index=False, encoding='utf-8-sig')
        print(f"  ✓ Saved: {aggregated_path}")
        
        # Calculate city inflation
        print(f"\n📊 Calculating city-level inflation...")
        city_inflation = self.calculate_city_inflation(aggregated)
        
        if not city_inflation.empty:
            city_inflation_path = os.path.join(output_dir, 'rent_city_inflation.csv')
            city_inflation.to_csv(city_inflation_path, index=False, encoding='utf-8-sig')
            print(f"  ✓ Saved: {city_inflation_path}")
        
        # Calculate country inflation
        print(f"\n📊 Calculating country-level rent inflation...")
        country_inflation = self.calculate_country_rent_inflation(city_inflation)
        
        if not country_inflation.empty:
            country_path = os.path.join(output_dir, 'rent_country_inflation.csv')
            country_inflation.to_csv(country_path, index=False, encoding='utf-8-sig')
            print(f"  ✓ Saved: {country_path}")
            
            # Print summary
            print(f"\n📈 Country Rent Inflation Summary (Latest 5 Months)")
            print("=" * 60)
            for _, row in country_inflation.tail(5).iterrows():
                print(f"  {row['YearMonth']}: {row['Rent_Inflation_%']:>7.2f}%")
        
        # Generate quality report
        print(f"\n✔️ Generating quality report...")
        quality_report = self._generate_quality_report(city_inflation, aggregated)
        
        quality_path = os.path.join(output_dir, 'rent_quality_report.csv')
        pd.DataFrame(quality_report).to_csv(quality_path, index=False, encoding='utf-8-sig')
        print(f"  ✓ Saved: {quality_path}")
        
        return {
            'aggregated': aggregated,
            'city_inflation': city_inflation,
            'country_inflation': country_inflation,
            'quality_report': quality_report,
            'files_saved': {
                'aggregated': aggregated_path,
                'city_inflation': city_inflation_path if not city_inflation.empty else None,
                'country': country_path if not country_inflation.empty else None,
                'quality': quality_path
            }
        }
    
    def _generate_quality_report(self, city_inflation: pd.DataFrame, 
                                aggregated: pd.DataFrame) -> List[Dict]:
        """Generate quality statistics report"""
        report = []
        
        # Overall statistics
        report.append({
            'Category': 'Overall',
            'Metric': 'Total Records',
            'Value': len(aggregated)
        })
        
        report.append({
            'Category': 'Overall',
            'Metric': 'Total Cities',
            'Value': aggregated['City'].nunique() if 'City' in aggregated.columns else 0
        })
        
        report.append({
            'Category': 'Overall',
            'Metric': 'Room Types',
            'Value': aggregated['RoomCount'].nunique() if 'RoomCount' in aggregated.columns else 0
        })
        
        report.append({
            'Category': 'Overall',
            'Metric': 'Date Range',
            'Value': f"{aggregated['Date'].min().date()} to {aggregated['Date'].max().date()}"
            if 'Date' in aggregated.columns and not aggregated.empty else 'N/A'
        })
        
        # Per-city statistics
        if 'City' in city_inflation.columns:
            for city in city_inflation['City'].unique():
                city_records = len(city_inflation[city_inflation['City'] == city])
                report.append({
                    'Category': f'City: {city}',
                    'Metric': 'Inflation Records',
                    'Value': city_records
                })
        
        return report


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Rent inflation analysis with city grouping')
    parser.add_argument('--project-root', 
                       default=os.path.abspath(os.path.join(script_dir, '..', '..')))
    
    args = parser.parse_args()
    
    # Setup paths
    input_dir = os.path.join(args.project_root, 'InflationItems', 'Datas', 'HousesRent')
    output_dir = os.path.join(args.project_root, 'Inflations', 'Datas', 'Final_Reports', 'TUFE_Rent')
    
    # Run analysis
    calculator = RentInflationTUFE()
    results = calculator.run_rent_analysis(input_dir, output_dir)
    
    if results:
        print("\n✅ Rent analysis complete!")
    else:
        print("\n❌ Rent analysis failed")


if __name__ == '__main__':
    main()
