"""
tufe_cross_store_compare.py
TUFE-based cross-store inflation comparison
Calculates store inflation using TUFE category weights instead of simple averaging
Also provides category-level inflation breakdown
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
import re
from typing import Dict, List, Tuple, Optional

# Add script directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from inflation_engine_tufe import TUFEInflationEngine, load_all_categories_with_tufe
from tufe_parser import load_tufe


class TUFECrossStoreCompare:
    """TUFE-weighted cross-store inflation comparison"""
    
    def __init__(self, tufe_parser=None):
        if tufe_parser is None:
            tufe_path = r'c:\Users\onurk\Desktop\Projects\InflationResearchStudy\Inflations\Codes\TUFE'
            self.tufe = load_tufe(tufe_path)
        else:
            self.tufe = tufe_parser
        
        self.engine = TUFEInflationEngine(tufe_parser=self.tufe)
    
    def calculate_tufe_category_inflation(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or 'TUFE_Code' not in df.columns:
            return pd.DataFrame()
        
        df = df[df['TUFE_Code'].notna()].copy()
        if df.empty:
            return pd.DataFrame()
        
        df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
        
        category_monthly = df.groupby(['YearMonth', 'TUFE_Code']).agg({
            'Active_Price': ['mean', 'count'],
            'Store': 'nunique'
        }).reset_index()
        
        category_monthly.columns = ['YearMonth', 'TUFE_Code', 'AvgPrice', 'NumProducts', 'NumStores']
        
        category_monthly_sorted = category_monthly.sort_values(['TUFE_Code', 'YearMonth'])
        category_monthly_sorted['Inflation_%'] = (
            category_monthly_sorted.groupby('TUFE_Code')['AvgPrice'].pct_change() * 100
        ).round(2)
        
        category_monthly_sorted = category_monthly_sorted.dropna(subset=['Inflation_%'])
        
        category_monthly_sorted['TUFE_Name'] = category_monthly_sorted['TUFE_Code'].apply(
            lambda code: self.tufe.get_category_by_code(code)['name_en'] 
            if self.tufe.get_category_by_code(code) else 'UNKNOWN'
        )
        
        return category_monthly_sorted[[
            'YearMonth', 'TUFE_Code', 'TUFE_Name', 'Inflation_%', 'NumProducts', 'NumStores'
        ]].sort_values(['YearMonth', 'TUFE_Code'])
    
    def calculate_tufe_weighted_store_inflation(self, df: pd.DataFrame, weight_level: int = 2) -> pd.DataFrame:
        if df.empty or 'TUFE_Code' not in df.columns:
            return pd.DataFrame()
        
        df = df[df['TUFE_Code'].notna()].copy()
        if df.empty:
            return pd.DataFrame()
        
        df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
        
        def get_parent_code(code, level):
            if not code: return None
            parts = str(code).split('_')
            if len(parts) >= level: return '_'.join(parts[:level])
            return None
        
        df['WeightCode'] = df['TUFE_Code'].apply(lambda c: get_parent_code(c, weight_level))
        
        store_category_mom = df.groupby(['Store', 'YearMonth', 'WeightCode']).agg({
            'Active_Price': 'mean'
        }).reset_index()
        
        store_category_mom = store_category_mom.sort_values(['Store', 'WeightCode', 'YearMonth'])
        store_category_mom['Inflation_%'] = (store_category_mom.groupby(['Store', 'WeightCode'])['Active_Price'].pct_change() * 100).round(2)
        store_category_mom = store_category_mom.dropna(subset=['Inflation_%'])
        
        def get_weight(code):
            cat = self.tufe.get_category_by_code(code)
            return cat['weight'] if cat else 0.0
        
        store_category_mom['Weight'] = store_category_mom['WeightCode'].apply(get_weight)
        
        weighted_inflation = store_category_mom.groupby(['Store', 'YearMonth']).apply(
            lambda x: (x['Inflation_%'] * x['Weight']).sum() / x['Weight'].sum() if x['Weight'].sum() > 0 else 0.0
        ).reset_index()
        
        weighted_inflation.rename(columns={weighted_inflation.columns[-1]: 'Weighted_Inflation_%'}, inplace=True)
        return weighted_inflation.sort_values(['YearMonth', 'Store'])
    
    def calculate_total_tufe_inflation(self, df: pd.DataFrame, weight_level: int = 2) -> pd.DataFrame:
        if df.empty or 'TUFE_Code' not in df.columns:
            return pd.DataFrame()
        
        df = df[df['TUFE_Code'].notna()].copy()
        if df.empty:
            return pd.DataFrame()
        
        df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
        
        def get_parent_code(code, level):
            if not code: return None
            parts = str(code).split('_')
            if len(parts) >= level: return '_'.join(parts[:level])
            return None
        
        df['WeightCode'] = df['TUFE_Code'].apply(lambda c: get_parent_code(c, weight_level))
        
        category_monthly = df.groupby(['YearMonth', 'WeightCode']).agg({'Active_Price': 'mean'}).reset_index()
        category_monthly = category_monthly.sort_values(['WeightCode', 'YearMonth'])
        
        category_monthly['Inflation_%'] = (category_monthly.groupby('WeightCode')['Active_Price'].pct_change() * 100).round(2)
        category_monthly = category_monthly.dropna(subset=['Inflation_%'])
        
        def get_weight(code):
            cat = self.tufe.get_category_by_code(code)
            return cat['weight'] if cat else 0.0
        
        category_monthly['Weight'] = category_monthly['WeightCode'].apply(get_weight)
        
        total_inflation = category_monthly.groupby('YearMonth').apply(
            lambda x: (x['Inflation_%'] * x['Weight']).sum() / x['Weight'].sum() if x['Weight'].sum() > 0 else 0.0
        ).reset_index()
        
        total_inflation.rename(columns={total_inflation.columns[-1]: 'TUFE_Inflation_%'}, inplace=True)
        return total_inflation
    
    def run_cross_store_analysis(self, df: pd.DataFrame, dataset_type: str, output_dir: str) -> Dict[str, pd.DataFrame]:
        results = {}
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"  📊 Calculating category-level inflation...")
        category_inflation = self.calculate_tufe_category_inflation(df)
        if not category_inflation.empty:
            save_path = os.path.join(output_dir, f'{dataset_type}_tufe_category_inflation.csv')
            category_inflation.to_csv(save_path, index=False, encoding='utf-8-sig')
            results['category_inflation'] = category_inflation
        
        print(f"  📊 Calculating store-level TUFE-weighted inflation...")
        store_weighted = self.calculate_tufe_weighted_store_inflation(df, weight_level=2)
        if not store_weighted.empty:
            save_path = os.path.join(output_dir, f'{dataset_type}_tufe_store_weighted_inflation.csv')
            store_weighted.to_csv(save_path, index=False, encoding='utf-8-sig')
            results['store_weighted'] = store_weighted
        
        print(f"  📊 Calculating total TUFE inflation...")
        total_inflation = self.calculate_total_tufe_inflation(df, weight_level=2)
        if not total_inflation.empty:
            save_path = os.path.join(output_dir, f'{dataset_type}_tufe_total_inflation.csv')
            total_inflation.to_csv(save_path, index=False, encoding='utf-8-sig')
            results['total_inflation'] = total_inflation
            
        return results


def run_tufe_analysis_for_category(category_name: str, input_dir: str, output_dir: str, tufe_parser=None) -> Dict:
    print(f"\n🚀 TUFE Analysis: {category_name}")
    print(f"📂 Input: {input_dir}")
    print(f"📂 Output: {output_dir}")
    
    analyzer = TUFECrossStoreCompare(tufe_parser=tufe_parser)
    
    category_loaders = {
        'Markets': analyzer.engine.load_market_data_with_tufe,
        'ClothingStores': analyzer.engine.load_clothing_data_with_tufe,
        'Cosmetics': analyzer.engine.load_cosmetics_data_with_tufe,
        'ConstructionSuppliesMarkets': analyzer.engine.load_construction_data_with_tufe,
        'TechnologicalProducts': analyzer.engine.load_tech_data_with_tufe,
        'HomeGoods': analyzer.engine.load_homegoods_data_with_tufe,
        'HousesRent': analyzer.engine.load_rent_data_with_tufe,
    }
    
    loader = category_loaders.get(category_name)
    if not loader:
        print(f"❌ Unknown category: {category_name}")
        return {}
    
    if not os.path.exists(input_dir):
        print(f"❌ Input directory not found: {input_dir}")
        return {}
    
    print(f"📥 Loading {category_name} data...")
    
    frames = []
    store_folders = [d for d in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, d))]
    
    if store_folders:
        for store in store_folders:
            store_path = os.path.join(input_dir, store)
            print(f"   📂 Scanning store: {store}...")
            df = loader(store_path)
            if not df.empty:
                frames.append(df)
                print(f"      ✓ Loaded {len(df):,} records")
            else:
                print(f"      ⚠️ No valid data found for {store}")
    else:
        # Fallback if no subdirectories exist
        print(f"   📂 Scanning root folder: {input_dir}")
        df = loader(input_dir)
        if not df.empty:
            frames.append(df)
            print(f"      ✓ Loaded {len(df):,} records")
            
    if not frames:
        print(f"⚠️ No valid data found for {category_name}")
        return {}
        
    final_df = pd.concat(frames, ignore_index=True)
    print(f"\n✓ Finished Loading! Merged {len(final_df):,} total records from {final_df['Store'].nunique()} stores.")
    
    os.makedirs(output_dir, exist_ok=True)
    results = analyzer.run_cross_store_analysis(final_df, category_name.lower(), output_dir)
    print(f"✓ Analysis complete. Reports saved to: {output_dir}")
    
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TUFE-based cross-store inflation comparison')
    parser.add_argument('--type', default='all')
    parser.add_argument('--project-root', default=os.path.abspath(os.path.join(script_dir, '..', '..')))
    args = parser.parse_args()
    
    tufe_path = os.path.join(args.project_root, 'Inflations', 'Codes', 'TUFE')
    tufe = load_tufe(tufe_path)
    
    categories = {
        'Markets': 'Markets',
        'ClothingStores': 'ClothingStores',
        'Cosmetics': 'Cosmetics',
        'ConstructionSuppliesMarkets': 'ConstructionSuppliesMarkets',
        'TechnologicalProducts': 'TechnologicalProducts',
        'HomeGoods': 'HomeGoods',
        'HousesRent': 'HousesRent',
    }
    
    types_to_process = categories.keys() if args.type == 'all' else [args.type]
    
    for category_name in types_to_process:
        input_dir = os.path.join(args.project_root, 'InflationItems', 'Datas', categories[category_name])
        output_dir = os.path.join(args.project_root, 'Inflations', 'Datas', 'Final_Reports', f'TUFE_{category_name}')
        run_tufe_analysis_for_category(category_name, input_dir, output_dir, tufe_parser=tufe)