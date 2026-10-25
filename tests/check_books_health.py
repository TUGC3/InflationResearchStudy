"""Offline regression checks; run: python -m pytest tests/check_books_health.py."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
HEALTH = ROOT / 'InflationItems/Codes/Health'


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('filename,function,prefix,category,html', [
    ('dentgroup_scraper.py', 'scrape_dentgroup', 'dentgroup', 'Dentist',
     '<div class="accordion-item"><div class="collapse"><div class="row">'
     '<div>Dolgu</div><div>1.500 TL</div></div></div></div>'),
    ('adu_hospital_scraper.py', 'scrape_university_doctor_fees', 'adu_hospital', 'Doctor',
     '<table><tr><td>Muayene</td><td>712,00 TL</td></tr></table>'),
    ('ozelfizyoterapist_scraper.py', 'scrape_physical_therapy', 'ozelfizyoterapist', 'Physical_Therapy',
     '<a href="?page=1"><i class="fa-angle-double-right"></i></a>'
     '<div class="card mb-3 rounded"><span class="float-start">2 Görüş</span>'
     '<span class="fwb">1.500 / Seans</span><ul class="list-unstyled">İstanbul</ul></div>'),
])
def test_brand_output_from_unrelated_directory(tmp_path, monkeypatch, filename, function, prefix, category, html):
    module = load(HEALTH / 'Dentist&Doctor&Physical_Therapy' / filename)
    module.__file__ = str(tmp_path / 'InflationItems/Codes/Health/group' / filename)
    monkeypatch.chdir(tmp_path)
    response = SimpleNamespace(status_code=200, content=html.encode('utf-8'))
    monkeypatch.setattr(module.requests, 'get', Mock(return_value=response))
    getattr(module, function)()
    files = list((tmp_path / 'InflationItems/Datas/Health' / category).glob(f'{prefix}_*.csv'))
    assert len(files) == 1
    frame = pd.read_csv(files[0])
    assert len(frame) == 1
    assert frame.iloc[0]['Price'] in (1500, 712, '1.500 TL')


def test_failed_health_request_is_not_success(monkeypatch):
    module = load(HEALTH / 'Dentist&Doctor&Physical_Therapy/dentgroup_scraper.py')
    monkeypatch.setattr(module.requests, 'get', Mock(return_value=SimpleNamespace(status_code=403)))
    with pytest.raises(SystemExit) as error:
        module.scrape_dentgroup()
    assert error.value.code == 1


def test_health_sources_keep_dates_and_save_independently(tmp_path, monkeypatch):
    module = load(HEALTH / 'Medicine_Glasses_Lenses/health_scraper.py')
    monkeypatch.setattr(module, 'OUTPUT_DIR', tmp_path)
    medicine = pd.DataFrame([{'date': '2026-05-29', 'product-name': 'Medicine', 'product-price': 42, 'source': 'TİTCK'}])
    optical = pd.DataFrame([{'date': '2026-10-24', 'product-name': 'SGK Cam', 'product-price': 50, 'source': 'SGK'}])
    monkeypatch.setattr(module, 'fetch_titck_medicine_prices', lambda: [medicine])
    monkeypatch.setattr(module, 'fetch_sgk_optical_prices', lambda: optical)
    module.main()
    output = pd.read_csv(next(tmp_path.glob('titck_*.csv')))
    assert output.iloc[0]['date'] == '2026-05-29'
    assert output.iloc[0]['source'] == 'TİTCK'
    assert len(list(tmp_path.glob('sgk_*.csv'))) == 1
    assert not list(tmp_path.glob('health_prices*'))
    monkeypatch.setattr(module, 'fetch_titck_medicine_prices', lambda: [])
    with pytest.raises(SystemExit):
        module.main()
    assert len(pd.read_csv(next(tmp_path.glob('sgk_*.csv')))) == 1


def test_empty_nezih_does_not_write_csv(tmp_path, monkeypatch):
    module = load(ROOT / 'InflationItems/Codes/BooksStationery/Nezih/nezih_scraper.py')
    output = tmp_path / 'nezih.csv'
    monkeypatch.setattr(sys, 'argv', ['nezih_scraper.py', '--output', str(output)])
    monkeypatch.setattr(module, '_scrape_category', lambda *args, **kwargs: [])
    with pytest.raises(SystemExit):
        module.main()
    assert not output.exists()
