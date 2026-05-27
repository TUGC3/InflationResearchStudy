"""
run_tufe.py
TUFE Inflation Calculation Pipeline Orchestrator
Coordinates all stages: parsing TUFE, loading data, calculating category inflation, aggregating
"""

import os
import sys
import argparse
import json
import traceback
from pathlib import Path
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from tufe_parser import load_tufe, TUFEParser
from tufe_cross_store_compare import (
    TUFECrossStoreCompare, 
    run_tufe_analysis_for_category
)
from full_calculate_tufe import FullCalculateTUFE
from rent_inflation_tufe import RentInflationTUFE


class TUFEPipeline:
    """Orchestrate TUFE inflation calculation pipeline"""
    
    def __init__(self, project_root: str):
        """
        Initialize pipeline
        
        Args:
            project_root: Root directory of InflationResearchStudy project
        """
        self.project_root = project_root
        self.tufe_path = os.path.join(script_dir, 'TUFE')
        self.data_base_dir = os.path.join(project_root, 'InflationItems', 'Datas')
        self.output_base_dir = os.path.join(project_root, 'Inflations', 'Datas', 'Final_Reports')
        
        self.tufe = None
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def setup(self) -> bool:
        """Setup and validate pipeline"""
        print("=" * 80)
        print("🚀 TUFE INFLATION CALCULATION PIPELINE")
        print("=" * 80)
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        self.start_time = datetime.now()
        
        # Validate directories
        print("📁 Validating directories...")
        if not os.path.exists(self.data_base_dir):
            print(f"❌ Data directory not found: {self.data_base_dir}")
            return False
        print(f"  ✓ Data directory: {self.data_base_dir}")
        
        os.makedirs(self.output_base_dir, exist_ok=True)
        print(f"  ✓ Output directory: {self.output_base_dir}")
        
        # Load TUFE
        print(f"\n📖 Loading TUFE file...")
        if not os.path.exists(self.tufe_path):
            print(f"❌ TUFE file not found: {self.tufe_path}")
            return False
        
        try:
            self.tufe = load_tufe(self.tufe_path)
            info = self.tufe.parse()
            print(f"  ✓ TUFE loaded")
            print(f"    - Categories: {info['count']}")
            print(f"    - Total weight: {info['total_weight']:.2f}")
        except Exception as e:
            print(f"❌ Error loading TUFE: {e}")
            return False
        
        return True
    
    def stage_1_category_analysis(self) -> bool:
        """Stage 1: Calculate category-level inflation"""
        print("\n" + "=" * 80)
        print("STAGE 1: CATEGORY INFLATION ANALYSIS")
        print("=" * 80)
        
        categories = {
            'Markets': 'Markets',
            'ClothingStores': 'ClothingStores',
            'Cosmetics': 'Cosmetics',
            'ConstructionSuppliesMarkets': 'ConstructionSuppliesMarkets',
            'TechnologicalProducts': 'TechnologicalProducts',
            'HomeGoods': 'HomeGoods',
        }
        
        for display_name, dir_name in categories.items():
            input_dir = os.path.join(self.data_base_dir, dir_name)
            output_dir = os.path.join(self.output_base_dir, f'TUFE_{display_name}')
            
            if not os.path.exists(input_dir):
                print(f"\n⚠️ Skipping {display_name}: directory not found")
                continue
            
            try:
                print(f"\n📊 Processing {display_name}...")
                results = run_tufe_analysis_for_category(
                    display_name, 
                    input_dir, 
                    output_dir, 
                    tufe_parser=self.tufe
                )
                self.results[f'category_{display_name}'] = results
            except Exception as e:
                print(f"❌ Error processing {display_name}: {e}")
                traceback.print_exc()
                continue
        
        return True
    
    def stage_2_rent_analysis(self) -> bool:
        """Stage 2: Calculate rent inflation with city grouping"""
        print("\n" + "=" * 80)
        print("STAGE 2: RENT INFLATION ANALYSIS")
        print("=" * 80)
        
        input_dir = os.path.join(self.data_base_dir, 'HousesRent')
        output_dir = os.path.join(self.output_base_dir, 'TUFE_Rent')
        
        if not os.path.exists(input_dir):
            print(f"⚠️ Rent data directory not found: {input_dir}")
            print("   Skipping rent analysis...")
            return True
        
        try:
            print(f"\n🏠 Processing rent data...")
            calculator = RentInflationTUFE(tufe_parser=self.tufe)
            results = calculator.run_rent_analysis(input_dir, output_dir)
            self.results['rent'] = results
        except Exception as e:
            print(f"❌ Error processing rent data: {e}")
            traceback.print_exc()
        
        return True
    
    def stage_3_full_aggregation(self) -> bool:
        """Stage 3: Aggregate all categories into composite TUFE inflation"""
        print("\n" + "=" * 80)
        print("STAGE 3: FULL AGGREGATION")
        print("=" * 80)
        
        print(f"\n📈 Calculating composite TUFE inflation...")
        
        try:
            calculator = FullCalculateTUFE(tufe_parser=self.tufe)
            results = calculator.run_full_calculation(
                self.output_base_dir,
                self.output_base_dir,
                output_name='TUFE_Total_Inflation'
            )
            self.results['full_calculation'] = results
        except Exception as e:
            print(f"❌ Error in full aggregation: {e}")
            traceback.print_exc()
            return False
        
        return True
    
    def generate_summary_report(self) -> bool:
        """Generate summary report of entire pipeline"""
        print("\n" + "=" * 80)
        print("SUMMARY REPORT")
        print("=" * 80)
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'project_root': self.project_root,
            'data_directory': self.data_base_dir,
            'output_directory': self.output_base_dir,
            'tufe_file': self.tufe_path,
            'pipeline_stages': {
                'stage_1_category_analysis': 'Complete' if any('category_' in k for k in self.results.keys()) else 'Skipped',
                'stage_2_rent_analysis': 'Complete' if 'rent' in self.results else 'Skipped',
                'stage_3_full_aggregation': 'Complete' if 'full_calculation' in self.results else 'Skipped',
            },
            'output_files': {}
        }
        
        # List generated files
        if os.path.exists(self.output_base_dir):
            for file_path in Path(self.output_base_dir).glob('TUFE_*.csv'):
                summary['output_files'][file_path.name] = str(file_path)
        
        # Save summary
        summary_path = os.path.join(self.output_base_dir, 'TUFE_Pipeline_Summary.json')
        try:
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)
            print(f"\n✓ Pipeline summary saved: {summary_path}")
        except Exception as e:
            print(f"⚠️ Could not save summary: {e}")
        
        # Print summary
        print(f"\n📋 Pipeline Results:")
        print(f"  Stage 1 (Category Analysis): {summary['pipeline_stages']['stage_1_category_analysis']}")
        print(f"  Stage 2 (Rent Analysis): {summary['pipeline_stages']['stage_2_rent_analysis']}")
        print(f"  Stage 3 (Full Aggregation): {summary['pipeline_stages']['stage_3_full_aggregation']}")
        
        print(f"\n📂 Output Files Generated: {len(summary['output_files'])}")
        if summary['output_files']:
            for file_name in sorted(summary['output_files'].keys())[:10]:
                print(f"  - {file_name}")
            if len(summary['output_files']) > 10:
                print(f"  ... and {len(summary['output_files']) - 10} more files")
        
        return True
    
    def run(self, stages: list = None) -> bool:
        """
        Run pipeline stages
        
        Args:
            stages: List of stages to run (None = all)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.setup():
            return False
        
        if stages is None:
            stages = [1, 2, 3]
        
        try:
            if 1 in stages:
                if not self.stage_1_category_analysis():
                    print("⚠️ Stage 1 completed with errors")
            
            if 2 in stages:
                if not self.stage_2_rent_analysis():
                    print("⚠️ Stage 2 completed with errors")
            
            if 3 in stages:
                if not self.stage_3_full_aggregation():
                    print("❌ Stage 3 failed")
                    return False
            
            # Generate summary
            self.generate_summary_report()
            
            self.end_time = datetime.now()
            elapsed = (self.end_time - self.start_time).total_seconds()
            
            print("\n" + "=" * 80)
            print("✅ PIPELINE COMPLETE")
            print("=" * 80)
            print(f"⏰ Finished: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"⏱️  Duration: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
            print(f"📂 Output: {self.output_base_dir}")
            print("=" * 80 + "\n")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Pipeline failed with error: {e}")
            traceback.print_exc()
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='TUFE Inflation Calculation Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tufe.py                    # Run all stages
  python run_tufe.py --stage 1          # Run only stage 1
  python run_tufe.py --stage 1 3        # Run stages 1 and 3 (skip rent)
        """
    )
    
    parser.add_argument('--project-root', 
                       default=os.path.abspath(os.path.join(script_dir, '..', '..')),
                       help='Project root directory')
    parser.add_argument('--stage', type=int, nargs='+', choices=[1, 2, 3],
                       default=None,
                       help='Pipeline stages to run (default: all)')
    
    args = parser.parse_args()
    
    # Run pipeline
    pipeline = TUFEPipeline(args.project_root)
    success = pipeline.run(stages=args.stage)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
