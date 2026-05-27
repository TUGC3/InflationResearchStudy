"""
full_calculate_tufe.py
Aggregate TUFE-weighted inflation across all sectors
Produces composite Turkey-wide inflation report using TUFE hierarchical weights
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

# Add script directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from tufe_parser import load_tufe


class FullCalculateTUFE:
    """Aggregate TUFE-weighted inflation across all sectors"""
    
    def __init__(self, tufe_parser=None):
        """
        Initialize calculator
        
        Args:
            tufe_parser: Pre-loaded TUFEParser instance
        """
        if tufe_parser is None:
            tufe_path = os.path.join(script_dir, 'TUFE')
            self.tufe = load_tufe(tufe_path)
        else:
            self.tufe = tufe_parser
    
    def load_category_reports(self, reports_dir: str) -> Dict[str, pd.DataFrame]:
        """
        Load category inflation reports from TUFE analysis
        
        Args:
            reports_dir: Directory containing TUFE analysis reports
            
        Returns:
            Dictionary mapping category names to DataFrames
        """
        reports = {}
        
        # Look for TUFE_*_tufe_total_inflation.csv files
        pattern = 'TUFE_*_tufe_total_inflation.csv'
        
        for file_path in Path(reports_dir).glob(pattern):
            try:
                category_name = file_path.name.replace('TUFE_', '').replace('_tufe_total_inflation.csv', '')
                df = pd.read_csv(file_path)
                
                # Ensure YearMonth column exists
                if 'YearMonth' not in df.columns:
                    print(f"⚠️ Skipping {file_path.name}: Missing YearMonth column")
                    continue
                
                reports[category_name] = df
                print(f"  ✓ Loaded {category_name}: {len(df)} months")
                
            except Exception as e:
                print(f"  ❌ Error loading {file_path.name}: {e}")
        
        return reports
    
    def _get_category_weight(self, category_name: str) -> float:
        """
        Get TUFE weight for a category
        
        Maps category names from reports to TUFE top-level categories
        
        Args:
            category_name: Category name from report file
            
        Returns:
            Weight value (0-100)
        """
        # Map category names to TUFE codes
        category_mapping = {
            'Markets': '1',  # Food
            'ClothingStores': '2',  # Clothing
            'ConstructionSuppliesMarkets': '4',  # Furniture
            'HomeGoods': '4',  # Furniture
            'TechnologicalProducts': '6',  # Communication
            'Cosmetics': '11',  # Personal care
            'HousesRent': '3',  # Housing/Rent
        }
        
        code = category_mapping.get(category_name)
        if not code:
            print(f"⚠️ Unknown category mapping: {category_name}")
            return 0.0
        
        # Get weight from TUFE
        cat = self.tufe.get_category_by_code(code)
        if cat:
            return cat['weight']
        
        # Fallback: manual weights (TUIK 2026)
        fallback_weights = {
            'Markets': 24.4444,  # Food
            'ClothingStores': 7.9038,  # Clothing
            'ConstructionSuppliesMarkets': 7.9201,  # Furniture
            'HomeGoods': 7.9201,  # Furniture
            'TechnologicalProducts': 3.1035,  # Communication
            'Cosmetics': 1.8720,  # Personal care (partial)
            'HousesRent': 11.4020,  # Housing
        }
        
        weight = fallback_weights.get(category_name, 0.0)
        if weight > 0:
            print(f"  ⚠️ Using fallback weight for {category_name}: {weight}")
        
        return weight
    
    def calculate_composite_inflation(self, reports: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Calculate composite TUFE inflation across all categories
        
        Args:
            reports: Dictionary of category DataFrames
            
        Returns:
            DataFrame with [YearMonth, category_inflation columns, Composite_Inflation_%]
        """
        if not reports:
            print("❌ No reports to aggregate")
            return pd.DataFrame()
        
        # Get unique months across all reports
        all_months = set()
        for df in reports.values():
            if 'YearMonth' in df.columns:
                all_months.update(df['YearMonth'].unique())
        
        all_months = sorted(list(all_months))
        
        if not all_months:
            print("❌ No months found in reports")
            return pd.DataFrame()
        
        # Build composite dataframe
        composite = pd.DataFrame({'YearMonth': all_months})
        
        # Add each category's inflation
        weights = {}
        for category_name, df in reports.items():
            weight = self._get_category_weight(category_name)
            weights[category_name] = weight
            
            # Rename inflation column to category name
            df_copy = df[['YearMonth', 'TUFE_Inflation_%']].copy()
            df_copy = df_copy.rename(columns={'TUFE_Inflation_%': f'{category_name}_Inflation_%'})
            
            composite = composite.merge(df_copy, on='YearMonth', how='left')
        
        # Calculate weighted composite
        inflation_cols = [f'{cat}_Inflation_%' for cat in reports.keys()]
        weight_values = [weights[cat] for cat in reports.keys()]
        
        def calculate_weighted(row):
            values = []
            weights_used = []
            for col, weight in zip(inflation_cols, weight_values):
                if pd.notna(row[col]) and weight > 0:
                    values.append(row[col])
                    weights_used.append(weight)
            
            if not values:
                return np.nan
            
            total_weight = sum(weights_used)
            if total_weight == 0:
                return np.nan
            
            return sum(v * w for v, w in zip(values, weights_used)) / total_weight
        
        composite['Composite_TUFE_Inflation_%'] = composite.apply(calculate_weighted, axis=1)
        composite['Composite_TUFE_Inflation_%'] = composite['Composite_TUFE_Inflation_%'].round(2)
        
        # Round category inflation columns
        for col in inflation_cols:
            if col in composite.columns:
                composite[col] = composite[col].round(2)
        
        return composite
    
    def generate_detailed_report(self, composite: pd.DataFrame, 
                                reports: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Generate detailed report with category breakdown
        
        Args:
            composite: Composite DataFrame
            reports: Dictionary of category DataFrames
            
        Returns:
            Detailed report DataFrame
        """
        if composite.empty:
            return pd.DataFrame()
        
        # Start with composite
        detailed = composite.copy()
        
        # Add top-level TUFE category breakdown
        category_codes = {
            'Food': '1',
            'Clothing': '2',
            'Housing': '3',
            'Furniture': '4',
            'Transport': '5',
            'Communication': '6',
            'Health': '7',
            'Recreation': '8',
            'Restaurants': '9',
            'Insurance': '10',
            'PersonalCare': '11',
        }
        
        for tufe_name, code in category_codes.items():
            cat = self.tufe.get_category_by_code(code)
            if cat:
                detailed[f'{tufe_name}_Weight'] = cat['weight']
        
        return detailed
    
    def generate_validation_report(self, reports: Dict[str, pd.DataFrame]) -> Dict:
        """
        Generate validation/quality report
        
        Args:
            reports: Dictionary of category DataFrames
            
        Returns:
            Dictionary with validation metrics
        """
        validation = {
            'total_categories': len(reports),
            'total_months': len(set().union(*[set(df['YearMonth'].unique()) for df in reports.values()])),
            'categories_loaded': list(reports.keys()),
            'category_coverage': {},
        }
        
        all_months = sorted(list(set().union(*[set(df['YearMonth'].unique()) for df in reports.values()])))
        
        for category_name, df in reports.items():
            months_available = len(df)
            coverage = (months_available / len(all_months) * 100) if all_months else 0
            validation['category_coverage'][category_name] = {
                'months_available': months_available,
                'coverage_%': round(coverage, 2),
                'latest_month': df['YearMonth'].max() if 'YearMonth' in df.columns else 'N/A'
            }
        
        return validation
    
    def run_full_calculation(self, reports_dir: str, output_dir: str, 
                            output_name: str = 'TUFE_Full_Report') -> Dict:
        """
        Run full calculation and generate reports
        
        Args:
            reports_dir: Directory containing category inflation reports
            output_dir: Output directory for final reports
            output_name: Base name for output files
            
        Returns:
            Dictionary with generated files and validation data
        """
        print(f"\n🚀 TUFE Full Calculation")
        print(f"📂 Input: {reports_dir}")
        print(f"📂 Output: {output_dir}")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Load category reports
        print("\n📥 Loading category inflation reports...")
        reports = self.load_category_reports(reports_dir)
        
        if not reports:
            print("❌ No category reports found")
            return {}
        
        # Calculate composite inflation
        print("\n📊 Calculating composite TUFE inflation...")
        composite = self.calculate_composite_inflation(reports)
        
        if composite.empty:
            print("❌ Composite calculation failed")
            return {}
        
        # Save composite report
        composite_path = os.path.join(output_dir, f'{output_name}_Composite.csv')
        composite.to_csv(composite_path, index=False, encoding='utf-8-sig')
        print(f"  ✓ Saved composite report: {composite_path}")
        
        # Generate detailed report
        print("\n📋 Generating detailed report...")
        detailed = self.generate_detailed_report(composite, reports)
        
        detailed_path = os.path.join(output_dir, f'{output_name}_Detailed.csv')
        detailed.to_csv(detailed_path, index=False, encoding='utf-8-sig')
        print(f"  ✓ Saved detailed report: {detailed_path}")
        
        # Generate validation report
        print("\n✔️ Generating validation report...")
        validation = self.generate_validation_report(reports)
        
        validation_df = pd.DataFrame({
            'Metric': ['Total Categories', 'Total Months', 'Categories Loaded'],
            'Value': [validation['total_categories'], validation['total_months'], 
                     ', '.join(validation['categories_loaded'])]
        })
        
        validation_path = os.path.join(output_dir, f'{output_name}_Validation.csv')
        validation_df.to_csv(validation_path, index=False, encoding='utf-8-sig')
        print(f"  ✓ Saved validation report: {validation_path}")
        
        # Print summary
        print("\n📈 COMPOSITE INFLATION SUMMARY (Latest 5 Months)")
        print("=" * 80)
        summary_df = composite[['YearMonth', 'Composite_TUFE_Inflation_%']].tail(5)
        for _, row in summary_df.iterrows():
            print(f"  {row['YearMonth']}: {row['Composite_TUFE_Inflation_%']:>7.2f}%")
        
        return {
            'composite': composite,
            'detailed': detailed,
            'validation': validation,
            'files_saved': {
                'composite': composite_path,
                'detailed': detailed_path,
                'validation': validation_path
            }
        }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Full TUFE inflation calculation')
    parser.add_argument('--project-root', 
                       default=os.path.abspath(os.path.join(script_dir, '..', '..')))
    parser.add_argument('--reports-dir', 
                       default='Inflations/Datas/Final_Reports')
    parser.add_argument('--output-dir', 
                       default='Inflations/Datas/Final_Reports')
    
    args = parser.parse_args()
    
    # Resolve paths
    reports_dir = os.path.join(args.project_root, args.reports_dir)
    output_dir = os.path.join(args.project_root, args.output_dir)
    
    # Load TUFE
    tufe_path = os.path.join(script_dir, 'TUFE')
    print(f"Loading TUFE from {tufe_path}...")
    tufe = load_tufe(tufe_path)
    print(f"✓ TUFE loaded\n")
    
    # Run calculation
    calculator = FullCalculateTUFE(tufe_parser=tufe)
    results = calculator.run_full_calculation(reports_dir, output_dir)
    
    if results:
        print("\n✅ Full TUFE calculation complete!")
        print(f"\nOutput files:")
        for file_type, file_path in results.get('files_saved', {}).items():
            print(f"  {file_type}: {file_path}")
    else:
        print("\n❌ Full TUFE calculation failed")


if __name__ == '__main__':
    main()
