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
        
    def _load_standard_csv(self, file_path: str, date_str: str, category_hint: str) -> pd.DataFrame:
        """
        STRICT RULE IMPLEMENTATION:
        1. Product Name -> search 'product-name', 'name', 'product_name' -> fallback to col 0
        2. Price -> search 'price', 'product-price', 'product_price' -> fallback to col 1
        """
        for sep in [',', ';', '\t']:
            try:
                df = pd.read_csv(file_path, sep=sep, on_bad_lines='skip', dtype=str)
                df.columns = [c.strip().lower() for c in df.columns]
                break
            except Exception:
                continue
        else:
            return pd.DataFrame()

        if df.empty or df.shape[1] < 2:
            return pd.DataFrame()

        # 🔍 1. PRODUCT NAME DETECTION
        prod_candidates = ['product-name', 'name', 'product_name']
        prod_col = next((c for c in prod_candidates if c in df.columns), df.columns[0])

        # 🔍 2. PRICE DETECTION
        price_candidates = ['price', 'product-price', 'product_price']
        price_col = next((c for c in price_candidates if c in df.columns),
                         df.columns[1] if len(df.columns) > 1 else None)

        if price_col is None or prod_col == price_col:
            return pd.DataFrame()

        # 📦 STANDARDIZE
        std_df = pd.DataFrame({
            'ProductName': df[prod_col].astype(str).str.strip(),
            'Active_Price': _clean_price(df[price_col])
        })

        std_df = std_df.dropna(subset=['Active_Price'])
        std_df = std_df[std_df['Active_Price'] > 0]
        if std_df.empty:
            return pd.DataFrame()

        std_df['Date'] = pd.to_datetime(date_str)
        std_df['Category'] = category_hint
        std_df['Store'] = Path(file_path).stem.rsplit('_', 1)[0]

        return std_df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']]

    def _tag_with_tufe(self, df: pd.DataFrame, category_hint: str) -> pd.DataFrame:
        if df.empty:
            df['TUFE_Code'] = None
            df['TUFE_Confidence'] = 0.0
            return df

        # ✅ GUARANTEED SAFE UNIQUE EXTRACTION
        unique_products = df['ProductName'].dropna().astype(str).str.strip().unique()

        mapping_results = {}
        for prod in unique_products:
            cache_key = (prod, category_hint)
            if self.use_cache and cache_key in self.mapping_cache:
                mapping_results[prod] = self.mapping_cache[cache_key]
            else:
                code, conf = self.mapper.map_product(prod, category_hint=category_hint)
                mapping_results[prod] = (code, conf)
                if self.use_cache:
                    self.mapping_cache[cache_key] = (code, conf)

        df['TUFE_Code'] = df['ProductName'].map(lambda x: mapping_results.get(x, (None, 0.0))[0])
        df['TUFE_Confidence'] = df['ProductName'].map(lambda x: mapping_results.get(x, (None, 0.0))[1])

        return df

    def _batch_load_and_tag(self, input_dir: str, hint: str) -> pd.DataFrame:
        files = glob.glob(os.path.join(input_dir, "*.csv"))
        df_list = []
        for file in files:
            date_str = _extract_date(os.path.basename(file))
            if not date_str: continue
            df = self._load_standard_csv(file, date_str, hint)
            if not df.empty:
                df_list.append(df)

        result = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        return self._tag_with_tufe(result, hint) if not result.empty else result

    # 🔽 CATEGORY LOADERS (All use the exact strict rule now)
    def load_market_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        return self._batch_load_and_tag(input_dir, 'food')

    def load_clothing_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        return self._batch_load_and_tag(input_dir, 'clothing')

    def load_construction_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        return self._batch_load_and_tag(input_dir, 'furniture')

    def load_cosmetics_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        return self._batch_load_and_tag(input_dir, 'cosmetics')

    def load_tech_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        return self._batch_load_and_tag(input_dir, 'technology')

    def load_homegoods_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        return self._batch_load_and_tag(input_dir, 'furniture')

    def load_rent_data_with_tufe(self, input_dir: str) -> pd.DataFrame:
        files = glob.glob(os.path.join(input_dir, "*.csv"))
        df_list = []
        for file in files:
            date_str = _extract_date(os.path.basename(file))
            if not date_str: continue

            # Rent uses the same strict rule, then adds room extraction
            df = self._load_standard_csv(file, date_str, 'rent')
            if df.empty: continue

            def extract_room_count(name):
                match = re.search(r'(\d+)\s*(?:oda|bedroom|br|yatak)', str(name), re.IGNORECASE)
                return match.group(1) if match else '0'

            df['RoomCount'] = df['ProductName'].apply(extract_room_count)
            df['ProductName'] = df['Store'] + '_' + df['RoomCount'] + 'Room'
            df_list.append(df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']])

        result = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        return self._tag_with_tufe(result, 'housing') if not result.empty else result

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
        'Markets': ('Markets', 'food'),
        'ClothingStores': ('ClothingStores', 'clothing'),
        'Cosmetics': ('Cosmetics', 'cosmetics'),
        'ConstructionSuppliesMarkets': ('ConstructionSuppliesMarkets', 'furniture'),
        'TechnologicalProducts': ('TechnologicalProducts', 'technology'),
        'HomeGoods': ('HomeGoods', 'furniture'),
        'HousesRent': ('HousesRent', 'rent'),
    }
    for display_name, (dir_name, hint) in categories.items():
        category_dir = os.path.join(base_dir, dir_name)
        if not os.path.exists(category_dir): continue

        df = engine._batch_load_and_tag(category_dir, hint) if hint != 'rent' else engine.load_rent_data_with_tufe(category_dir)

        if not df.empty:
            results[display_name] = df

    return results