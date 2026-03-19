import subprocess
import os
import sys

def main():
    # Base directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    codes_dir = os.path.dirname(script_dir)
    
    # Create a logs directory inside Full_Scrape to avoid messy console output
    logs_dir = os.path.join(script_dir, "batus_logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # List of your 4 specific scrapers
    my_scrapers = [
        ("Hapeloglu", os.path.join(codes_dir, "Markets", "Hapeloglu")),
        ("ErzurumErzincanBayburt", os.path.join(codes_dir, "HousesRent", "ErzurumErzincanBayburt")),
        ("Bershka", os.path.join(codes_dir, "ClothingStores", "Bershka")),
        ("Nalburadam", os.path.join(codes_dir, "ConstructionSuppliesMarkets", "Nalburadam"))
    ]
    
    processes = []
    log_file_objects = []
    
    print("🚀 Starting your 4 scrapers simultaneously...\n")
    
    for name, path in my_scrapers:
        if not os.path.exists(path):
            print(f"❌ Directory not found for {name}: {path}")
            continue
            
        log_path = os.path.join(logs_dir, f"{name}.log")
        print(f"🟢 Starting {name}")
        print(f"   📂 Path: {path}")
        print(f"   📝 Log:  {log_path}\n")
        
        # Open log file for output redirection (merges stdout and stderr)
        f = open(log_path, "w", encoding="utf-8")
        log_file_objects.append(f)
        
        # The standardized command you requested previously
        cmd = ["uv", "run", "python", "-m", "scripts.run_scraper"]
        
        # Launch non-blocking subprocess
        p = subprocess.Popen(
            cmd,
            cwd=path,
            stdout=f,
            stderr=subprocess.STDOUT
        )
        processes.append((name, p))
        
    print(f"⏳ All {len(processes)} scrapers are now running in parallel.")
    print("   (You can check the live output inside the 'logs/' folder)\n")
    print("   Waiting for all of them to finish...\n")
    
    # Wait for all processes to finish and report status
    for name, p in processes:
        p.wait()
        if p.returncode == 0:
            print(f"✅ {name} completed successfully.")
        else:
            print(f"❌ {name} exited with error code {p.returncode}. Please check its log file.")
            
    # Cleanup file handles
    for f in log_file_objects:
        f.close()
        
    print("\n🎉 All scrapers have finished executing!")

if __name__ == "__main__":
    main()
