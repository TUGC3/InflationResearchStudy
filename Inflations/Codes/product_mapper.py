"""
Product Mapper - Map product names to TUFE categories
Uses fuzzy matching, keyword matching, and manual overrides for robust product classification
"""

import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import unicodedata


class ProductMapper:
    """Map product names to TUFE categories"""
    
    def __init__(self, tufe_parser):
        self.tufe = tufe_parser
        self.cache = {}
        self.manual_overrides = self._load_manual_overrides()
        self.unmatched_log = []

        # Pre-process TUFE tree for fast lookups
        self._leaf_categories = []
        self._category_index = {}
        self._keyword_index = {}
        self._preprocess_tufe_tree()

    def _preprocess_tufe_tree(self):
        """Flatten TUFE tree into searchable indexes"""
        for code, cat in self.tufe.categories.items():
            if not cat: continue

            self._category_index[code] = {
                'code': code,
                'name_tr': self._normalize_text(cat.get('name_tr', '')),
                'name_en': self._normalize_text(cat.get('name_en', '')),
                'level': cat.get('level', 99)
            }

            # Index keywords for fast O(1) lookup
            for kw in cat.get('keywords', []):
                norm_kw = self._normalize_text(kw)
                if norm_kw not in self._keyword_index:
                    self._keyword_index[norm_kw] = []
                self._keyword_index[norm_kw].append(code)

            # Track leaf nodes (highest level) for fuzzy matching optimization
            if cat.get('level', 0) >= 3 or not cat.get('children'):
                self._leaf_categories.append(code)

    def _load_manual_overrides(self) -> Dict[str, str]:
        """
        Manual product-to-category mappings.
        🔑 KEY FIX: Values are CATEGORY NAMES/KEYWORDS, not hardcoded codes.
        This decouples mapper from dynamic TUFE code generation.
        """
        return {
            # Food
            'pirinç': 'Cereals', 'bulgur': 'Bulgur', 'buğday unu': 'Wheat flour',
            'ekmek': 'Bread', 'bisküvi': 'Biscuits', 'makarna': 'Pasta',
            'et': 'Meat', 'dana': 'Beef', 'kuzu': 'Lamb', 'tavuk': 'Chicken',
            'balık': 'Fish', 'peynir': 'Cheese', 'yoğurt': 'Yoghurt',
            'süt': 'Milk', 'yumurta': 'Eggs', 'yağ': 'Oils and fats',
            'zeytin': 'Table olives', 'domates': 'Tomatoes', 'patates': 'Potatoes',
            'şeker': 'Sugar', 'kahve': 'Coffee', 'çay': 'Tea', 'su': 'Water',
            'bira': 'Beer', 'şarap': 'Wine', 'rakı': 'Raki',

            # Clothing
            'erkek': 'Garments for men or boys', 'kadın': 'Garments for women or girls',
            'çocuk': 'Garments for infants', 'ayakkabı': 'Shoes and other footwear',
            'bot': 'Boots', 'elbise': 'Dress', 'pantolon': 'Trousers',
            'gömlek': 'Shirt', 'tişört': 'T-shirt', 'kazak': 'Sweater',

            # Housing/Rent
            'kiralık': 'Actual rental payments', 'daire': 'Apartment',
            'ev': 'House', 'oda': 'Room',

            # Utilities
            'elektrik': 'Electricity', 'gaz': 'Gas', 'doğalgaz': 'Natural gas',
            'tüpgaz': 'LPG cylinders',

            # Furniture
            'mobilya': 'Household furniture', 'kanepe': 'Sofa', 'masa': 'Table',
            'sandalye': 'Chair', 'yatak': 'Bed', 'halı': 'Carpet',
            'perde': 'Curtains', 'nevresim': 'Duvet cover set', 'yorgan': 'Duvet',

            # Appliances
            'buzdolabı': 'Refrigerator', 'çamaşır makinesi': 'Washing machine',
            'fırın': 'Ovens and cookers', 'klima': 'Air conditioner', 'soba': 'Stove heater',

            # Transport
            'araba': 'Motor cars', 'benzin': 'Petrol', 'motorin': 'Diesel',
            'lpg': 'LPG', 'kargo': 'Courier', 'taksi': 'Taxi',
            'otobüs': 'Bus', 'tren': 'Train',

            # Communication
            'telefon': 'Mobile phone', 'internet': 'Internet', 'bilgisayar': 'Computer',

            # Health
            'ilaç': 'Medicines', 'doktor': 'Doctor consultation', 'diş': 'Dental',

            # Recreation
            'film': 'Cinema', 'spor': 'Sporting equipment', 'kitap': 'Books',
        }

    def _resolve_category(self, category_identifier: str) -> Optional[str]:
        """Safely resolve category name/keyword to actual TUFE code"""
        # 1. Exact code match
        if category_identifier in self.tufe.categories:
            return category_identifier

        # 2. Search by keyword/name
        results = self.tufe.search_by_keyword(category_identifier)
        if results:
            return results[0]

        # 3. Fallback to root code if identifier looks like one
        if re.match(r'^[1-9]\d?(_\d+)*$', category_identifier):
            return category_identifier

        return None

    def map_product(self, product_name: str, store: Optional[str] = None,
                    category_hint: Optional[str] = None) -> Tuple[Optional[str], float]:
        cache_key = (product_name, store, category_hint)
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = self._match_manual_overrides(product_name)
        if result:
            self.cache[cache_key] = (result, 0.95)
            return result, 0.95

        result, score = self._match_keywords(product_name, category_hint)
        if score > 0.75:
            self.cache[cache_key] = (result, score)
            return result, score

        result, score = self._match_fuzzy(product_name, category_hint)
        if score > 0.65:
            self.cache[cache_key] = (result, score)
            return result, score

        if category_hint:
            result = self._get_default_for_hint(category_hint)
            if result:
                self.cache[cache_key] = (result, 0.3)
                return result, 0.3

        self.unmatched_log.append({'product': product_name, 'store': store, 'hint': category_hint})
        self.cache[cache_key] = (None, 0.0)
        return None, 0.0

    def _match_manual_overrides(self, product_name: str) -> Optional[str]:
        name_lower = self._normalize_text(product_name)
        for pattern, category_id in self.manual_overrides.items():
            if pattern in name_lower:
                return self._resolve_category(category_id)
        return None

    def _match_keywords(self, product_name: str, category_hint: Optional[str]) -> Tuple[Optional[str], float]:
        name_lower = self._normalize_text(product_name)
        words = re.split(r'[\s\-\,]+', name_lower)

        best_match = None
        best_score = 0.0

        for word in words:
            if len(word) < 3: continue

            # Direct keyword index lookup
            norm_word = self._normalize_text(word)
            if norm_word in self._keyword_index:
                candidates = self._keyword_index[norm_word]
                # If hint is provided, prioritize candidates in that branch
                if category_hint:
                    hint_codes = self._get_candidates_for_hint(category_hint)
                    prioritized = [c for c in candidates if any(c.startswith(h) for h in hint_codes)]
                    candidates = prioritized if prioritized else candidates

                score = len(word) / len(product_name)
                if score > best_score and candidates:
                    best_score = score
                    best_match = candidates[0]

        return best_match, best_score

    def _match_fuzzy(self, product_name: str, category_hint: Optional[str]) -> Tuple[Optional[str], float]:
        name_lower = self._normalize_text(product_name)

        best_code = None
        best_ratio = 0.0

        # Limit to leaf categories for speed & accuracy
        target_codes = self._leaf_categories
        if category_hint:
            hint_codes = self._get_candidates_for_hint(category_hint)
            target_codes = [c for c in self._leaf_categories if any(c.startswith(h) for h in hint_codes)]

        for code in target_codes:
            cat = self._category_index.get(code)
            if not cat: continue

            # Check Turkish & English names
            ratio_tr = SequenceMatcher(None, name_lower, cat['name_tr']).ratio()
            ratio_en = SequenceMatcher(None, name_lower, cat['name_en']).ratio()
            ratio = max(ratio_tr, ratio_en)

            if ratio > best_ratio:
                best_ratio = ratio
                best_code = code

        return best_code, best_ratio if best_ratio > 0.5 else 0.0

    def _normalize_text(self, text: str) -> str:
        if not text: return ""
        text = text.lower()
        # Remove Turkish diacritics safely
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        # Custom fallback for remaining Turkish chars
        tr_map = {'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u'}
        for k, v in tr_map.items():
            text = text.replace(k, v)
        return re.sub(r'[^\w\s]', '', text).strip()

    def _get_candidates_for_hint(self, category_hint: str) -> List[str]:
        hint_lower = category_hint.lower()
        prefix_map = {
            'food': '1', 'market': '1', 'clothing': '2', 'apparel': '2',
            'housing': '3', 'rent': '3', 'furniture': '4', 'home': '4',
            'transport': '5', 'vehicle': '5', 'communication': '6',
            'health': '7', 'recreation': '8', 'education': '8',
            'restaurant': '9', 'insurance': '10', 'personal': '11'
        }
        prefix = prefix_map.get(hint_lower, '')
        if not prefix: return []
        return [code for code in self.tufe.categories.keys() if code.startswith(prefix)]

    def _get_default_for_hint(self, category_hint: str) -> Optional[str]:
        hint_map = {
            'food': '1', 'market': '1', 'clothing': '2', 'apparel': '2',
            'housing': '3', 'rent': '3', 'furniture': '4', 'home': '4',
            'transport': '5', 'vehicle': '5', 'communication': '6',
            'health': '7', 'recreation': '8', 'education': '8',
            'restaurant': '9', 'insurance': '10', 'personal': '11'
        }
        code = hint_map.get(category_hint.lower())
        return self._resolve_category(code) if code else None

    def get_unmapped_summary(self) -> Dict:
        if not self.unmatched_log:
            return {'total_unmapped': 0, 'by_store': {}, 'by_category_hint': {}}

        summary = {
            'total_unmapped': len(self.unmatched_log),
            'by_store': {},
            'by_category_hint': {},
            'samples': self.unmatched_log[:20]
        }
        for entry in self.unmatched_log:
            store = entry.get('store') or 'unknown'
            hint = entry.get('hint') or 'unknown'
            summary['by_store'][store] = summary['by_store'].get(store, 0) + 1
            summary['by_category_hint'][hint] = summary['by_category_hint'].get(hint, 0) + 1
        return summary