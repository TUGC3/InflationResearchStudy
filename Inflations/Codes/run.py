"""
run.py  —  Universal runner for the Inflation Research Study
Add a new store or city by copying one of the config blocks below.

Usage:
    python run.py                    # runs all configured sources
    python run.py market             # runs only market sources
    python run.py clothing           # runs only clothing stores
    python run.py construction       # runs only construction markets
    python run.py rent               # runs only rent calculators
    python run.py full               # full TUFE composite report
"""

import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from inflation_engine import run_pipeline
from Full_Calculate import load_all, PATHS, OUTPUT_DIR, calculate_tufe_weighted_summary

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION — Add new stores/cities here
#  Each entry: (dataset_type, input_dir, output_dir, store_label_or_None)
# ══════════════════════════════════════════════════════════════════════════════

project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))

def p(*parts):
    return os.path.join(project_root, *parts)

SOURCES = [
    # ── MARKETS ────────────────────────────────────────────────────────────
    dict(
        dataset_type = 'market',
        input_dirs   = [p('InflationItems', 'Datas', 'Markets', 'Baskent')],
        output_dir   =  p('Inflations',     'Datas', 'Markets', 'Baskent'),
        store_label  = 'Baskent',
    ),
    # Add more markets:
    # dict(
    #     dataset_type = 'market',
    #     input_dirs   = [p('InflationItems', 'Datas', 'Markets', 'Migros')],
    #     output_dir   =  p('Inflations',     'Datas', 'Markets', 'Migros'),
    #     store_label  = 'Migros',
    # ),

    # ── CLOTHING STORES ─────────────────────────────────────────────────────
    dict(
        dataset_type = 'clothing',
        input_dirs   = [p('InflationItems', 'Datas', 'ClothingStores', 'adL')],
        output_dir   =  p('Inflations',     'Datas', 'ClothingStores', 'adL'),
        store_label  = 'adL',
    ),
    # dict(
    #     dataset_type = 'clothing',
    #     input_dirs   = [p('InflationItems', 'Datas', 'ClothingStores', 'LCWaikiki')],
    #     output_dir   =  p('Inflations',     'Datas', 'ClothingStores', 'LCWaikiki'),
    #     store_label  = 'LCWaikiki',
    # ),

    # ── CONSTRUCTION MARKETS ────────────────────────────────────────────────
    dict(
        dataset_type = 'construction',
        input_dirs   = [p('InflationItems', 'Datas', 'ConstructionSuppliesMarkets', 'TasciYapiMarket')],
        output_dir   =  p('Inflations',     'Datas', 'ConstructionSuppliesMarkets', 'TasciYapiMarket'),
        store_label  = 'TasciYapiMarket',
    ),

    # ── HOUSE RENT (per city) ────────────────────────────────────────────────
    dict(
        dataset_type = 'rent',
        input_dirs   = [p('InflationItems', 'Datas', 'HousesRent', 'Izmir')],
        output_dir   =  p('Inflations',     'Datas', 'HousesRent', 'Izmir'),
        store_label  = 'Izmir',
    ),
    # dict(
    #     dataset_type = 'rent',
    #     input_dirs   = [p('InflationItems', 'Datas', 'HousesRent', 'Istanbul')],
    #     output_dir   =  p('Inflations',     'Datas', 'HousesRent', 'Istanbul'),
    #     store_label  = 'Istanbul',
    # ),
]

# ══════════════════════════════════════════════════════════════════════════════

def run_selected(filter_type: str = None):
    for cfg in SOURCES:
        if filter_type and cfg['dataset_type'] != filter_type:
            continue
        run_pipeline(**cfg)


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'

    if mode == 'full':
        import subprocess
        subprocess.run([sys.executable, os.path.join(script_dir, 'Full_Calculate.py')])
    elif mode == 'compare':
        # Cross-store comparison for a type: python run.py compare market
        dtype = sys.argv[2] if len(sys.argv) > 2 else 'market'
        from CrossStore_Compare import run_cross_store
        _project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
        run_cross_store(dtype, _project_root)
    elif mode == 'cities':
        # Multi-city rent: python run.py cities [CityA CityB ...]
        from HousesRent.MultiCity_Rent_Calculator import run_multi_city
        _project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
        city_filter = sys.argv[2:] if len(sys.argv) > 2 else None
        run_multi_city(
            base_dir   = os.path.join(_project_root, 'InflationItems', 'Datas', 'HousesRent'),
            output_dir = os.path.join(_project_root, 'Inflations', 'Datas', 'HousesRent', '_MultiCity'),
            city_filter = city_filter,
        )
    elif mode in ('market', 'clothing', 'construction', 'rent'):
        run_selected(filter_type=mode)
    else:
        run_selected()
