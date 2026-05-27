"""
inflation_engine_tufe.py
Extended inflation engine with TUFE category tagging
Wraps existing inflation_engine loaders and adds TUFE category classification
"""

import os
import glob
import re
import warnings
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, List, Tuple

warnings.filterwarnings('ignore')

from inflation_engine import (
    load_market_data,
    load_clothing_data,
    load_construction_data,
    _extract_date,
    _clean_price
)
from tufe_parser import load_tufe
from product_mapper import ProductMapper


class TUFEInflationEngine:
    def __init__(self, tufe_parser=None, use_cache: bool = True):
        if tufe_parser is None:
            tufe_path = r'C:\Users\arhan\PycharmProjects\InflationResearchStudy\Inflations\Codes\TUFE'
            self.tufe = load_tufe(tufe_path)
        else:
            self.tufe = tufe_parser
        
        self.mapper = ProductMapper(self.tufe)
        self.use_cache = use_cache
        self.mapping_cache = {}
        
    def _tag_with_tufe(self, df: pd.DataFrame, category_hint: str) -> pd.DataFrame:
        if df.empty:
            df['TUFE_Code'] = None
            df['TUFE_Confidence'] = 0.0
            return df
        
        # 🔥 OPTIMIZATION: Only map unique products! 
        # (This prevents massive slow-downs on large stores like A101)
        unique_products = df['ProductName'].unique()
        mapping_results = {}
        
        for prod in unique_products:
            prod_str = str(prod).strip()
            cache_key = (prod_str, category_hint)
            
            if self.use_cache and cache_key in self.mapping_cache:
                mapping_results[prod] = self.mapping_cache[cache_key]
            else:
                code, conf = self.mapper.map_product(prod_str, category_hint=category_hint)
                mapping_results[prod] = (code, conf)
                if self.use_cache:
                    self.mapping_cache[cache_key] = (code, conf)
        
        # Map the results back to the full dataframe instantly
        df['TUFE_Code'] = df['ProductName'].map(lambda x: mapping_results[x][0])
        df['TUFE_Confidence'] = df['ProductName'].map(lambda x: mapping_results[x][1])
        
        return df
    
    def load_market_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        df = load_market_data(input_dir)
        if not df.empty: df = self._tag_with_tufe(df, 'food')
        return df
    
    def load_clothing_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        df = load_clothing_data(input_dir)
        if not df.empty: df = self._tag_with_tufe(df, 'clothing')
        return df
    
    def load_construction_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        df = load_construction_data(input_dir)
        if not df.empty: df = self._tag_with_tufe(df, 'furniture')
        return df
    
    def load_cosmetics_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        files = glob.glob(os.path.join(input_dir, "*.csv"))
        df_list = []
        for file in files:
            date_str = _extract_date(os.path.basename(file))
            if not date_str: continue
            try:
                df = pd.read_csv(file, delimiter=';', header=None, on_bad_lines='skip')
                if df.shape[1] < 2:
                    df = pd.read_csv(file, delimiter=',', header=0, on_bad_lines='skip')
                if df.shape[1] < 2: continue
                
                df.columns = ['ProductName', 'Price'] + [f'col_{i}' for i in range(2, df.shape[1])]
                df['Active_Price'] = pd.to_numeric(df['Price'], errors='coerce')
                df['Category'] = 'Cosmetics'
                df['Date'] = pd.to_datetime(date_str)
                df['Store'] = Path(file).stem
                df_list.append(df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']])
            except Exception:
                pass
        
        result = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        if not result.empty: result = self._tag_with_tufe(result, 'cosmetics')
        return result
    
    def load_tech_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        files = glob.glob(os.path.join(input_dir, "*.csv"))
        df_list = []
        for file in files:
            date_str = _extract_date(os.path.basename(file))
            if not date_str: continue
            try:
                df = pd.read_csv(file, header=0, on_bad_lines='skip')
                df.columns = [c.strip() for c in df.columns]
                
                product_col = next((c for c in df.columns if 'product' in c.lower() or 'name' in c.lower()), df.columns[0])
                price_col = next((c for c in df.columns if 'price' in c.lower()), df.columns[1] if len(df.columns) > 1 else None)
                if price_col is None: continue
                
                df = df.rename(columns={product_col: 'ProductName', price_col: 'Price'})
                df['Price'] = df['Price'].astype(str).str.replace('Başlangıç:', '', regex=False).str.strip()
                df['Active_Price'] = _clean_price(df['Price'])
                
                df['Category'] = 'Technology'
                df['Date'] = pd.to_datetime(date_str)
                df['Store'] = Path(file).stem.rsplit('_', 1)[0]
                df_list.append(df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']])
            except Exception:
                pass
        
        result = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        if not result.empty: result = self._tag_with_tufe(result, 'technology')
        return result
    
    def load_homegoods_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        files = glob.glob(os.path.join(input_dir, "*.csv"))
        df_list = []
        for file in files:
            date_str = _extract_date(os.path.basename(file))
            if not date_str: continue
            try:
                df = pd.read_csv(file, header=0, on_bad_lines='skip')
                if df.shape[1] < 2: continue
                
                df = df.iloc[:, 0:2].copy()
                df.columns = ['ProductName', 'Price']
                df['Active_Price'] = pd.to_numeric(df['Price'], errors='coerce')
                df['Category'] = 'HomeGoods'
                df['Date'] = pd.to_datetime(date_str)
                df['Store'] = Path(file).stem.rsplit('_', 1)[0]
                df_list.append(df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']])
            except Exception:
                pass
        
        result = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        if not result.empty: result = self._tag_with_tufe(result, 'furniture')
        return result
    
    def load_rent_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        files = glob.glob(os.path.join(input_dir, "*.csv"))
        df_list = []
        for file in files:
            date_str = _extract_date(os.path.basename(file))
            if not date_str: continue
            try:
                df = pd.read_csv(file, header=0, on_bad_lines='skip')
                if df.shape[1] < 2: continue
                
                df = df.iloc[:, 0:2].copy()
                df.columns = ['ProductName', 'Price']
                df['Active_Price'] = _clean_price(df['Price'])
                
                city = Path(file).parent.name
                df['Category'] = 'Rent'
                df['Date'] = pd.to_datetime(date_str)
                df['Store'] = city
                
                def extract_room_count(product_name):
                    match = re.search(r'(\d+)\s*(?:oda|bedroom|br|yatak)', str(product_name), re.IGNORECASE)
                    return match.group(1) if match else '0'
                
                df['RoomCount'] = df['ProductName'].apply(extract_room_count)
                df['ProductName'] = df['Store'] + '_' + df['RoomCount'] + 'Room'
                
                df_list.append(df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']])
            except Exception:
                pass
        
        result = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        if not result.empty: result = self._tag_with_tufe(result, 'housing')
        return result
    
    def get_mapping_quality_report(self) -> Dict:
        unmapped_summary = self.mapper.get_unmapped_summary()
        return {
            'cache_size': len(self.mapping_cache),
            'total_mapped': len(self.mapping_cache) - unmapped_summary['total_unmapped'],
            'total_unmapped': unmapped_summary['total_unmapped'],
            'unmapped_by_store': unmapped_summary['by_store'],
            'unmapped_by_hint': unmapped_summary['by_category_hint'],
            'unmapped_samples': unmapped_summary['samples']
        }

def load_all_categories_with_tufe(base_dir: str) -> Dict[str, pd.DataFrame]:
    engine = TUFEInflationEngine()
    results = {}
    categories = {
        'Markets': ('market', 'Markets'),
        'ClothingStores': ('clothing', 'ClothingStores'),
        'Cosmetics': ('cosmetics', 'Cosmetics'),
        'ConstructionSuppliesMarkets': ('construction', 'ConstructionSuppliesMarkets'),
        'TechnologicalProducts': ('tech', 'TechnologicalProducts'),
        'HomeGoods': ('homegoods', 'HomeGoods'),
        'HousesRent': ('rent', 'HousesRent'),
    }
    for display_name, (key, dir_name) in categories.items():
        category_dir = os.path.join(base_dir, dir_name)
        if not os.path.exists(category_dir): continue
        if key == 'market': df = engine.load_market_data_with_tufe(category_dir)
        elif key == 'clothing': df = engine.load_clothing_data_with_tufe(category_dir)
        elif key == 'cosmetics': df = engine.load_cosmetics_data_with_tufe(category_dir)
        elif key == 'construction': df = engine.load_construction_data_with_tufe(category_dir)
        elif key == 'tech': df = engine.load_tech_data_with_tufe(category_dir)
        elif key == 'homegoods': df = engine.load_homegoods_data_with_tufe(category_dir)
        elif key == 'rent': df = engine.load_rent_data_with_tufe(category_dir)
        else: continue
        
        if not df.empty: results[display_name] = df
    return results