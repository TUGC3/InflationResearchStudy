# Inflation Research Study - Scraper Suite

This directory contains the central monitoring and execution suite for the high-frequency inflation research project. The system is designed to coordinate multiple scraping engines while maintaining strict data integrity and throughput standards.

## Project Scope
The suite manages data collection across clothing, construction, and housing sectors. As of the current audit, approximately 14 million records have been aggregated from multiple Turkish e-commerce and real estate platforms.

## Technical Specifications
The system utilizes a balanced concurrency model optimized for each target platform:

- **Nalburadam**: 10 parallel workers with 0.5s mean request latency and 20x retry persistence.
- **Bershka**: 10 parallel workers with 0.4s mean request latency and 20x retry persistence.
- **Houses (Erzurum/Erzincan/Bayburt)**: Serial headless execution with 0.2s mean page transition frequency.
- **Hapeloglu**: 4 parallel workers with 1.5s mean request latency.

All browser-based engines implement automated image and advertisement blocking to minimize DOM overhead and improve processing speed.

## Monitoring and Telemetry
The primary dashboard, `fullscrape.py`, provides real-time telemetry for the collection fleet. It includes:

- **Progress Tracking**: Standardized parsing of categorical and items-based completion metrics.
- **Historical Baseline Analysis**: Automated comparison of current results against a 7-day rolling average to identify data variance.
- **Error Detection**: Real-time logging and status reporting for all sub-processes.

## Usage

Navigate to this directory and run:
```bash
# Standard
python fullscrape.py

# For Python3
python3 fullscrape.py

# If you are like me and use uv
uv run python3 fullscrape.py
```

---
*Maintained by Batu Koray Masak*
