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
        """
        Initialize mapper with TUFE parser
        
        Args:
            tufe_parser: TUFEParser instance (from tufe_parser.py)
        """
        self.tufe = tufe_parser
        self.cache = {}  # Cache product -> category mappings
        self.manual_overrides = self._load_manual_overrides()
        self.unmatched_log = []  # Track unmapped products for analysis
        
    def _load_manual_overrides(self) -> Dict[str, str]:
        """
        Load manual product-to-category mappings for edge cases
        
        Returns:
            Dict mapping product name patterns to TUFE category codes
        """
        return {
            # Food products
            'pirinç': '1_1_1_2',  # Rice -> Cereals
            'bulgur': '1_1_1_3',  # Bulgur
            'buğday unu': '1_1_2_1',  # Wheat flour
            'ekmek': '1_1_3_1',  # Bread
            'bisküvi': '1_1_3_3',  # Biscuits
            'makarna': '1_1_4_1',  # Pasta
            'et': '1_2_1',  # Meat (general)
            'dana': '1_2_1_1',  # Beef
            'kuzu': '1_2_1_2',  # Lamb
            'tavuk': '1_2_1_3',  # Chicken
            'balık': '1_3_1',  # Fish
            'peynir': '1_4_3',  # Cheese
            'yoğurt': '1_4_4',  # Yogurt
            'süt': '1_4_1',  # Milk
            'yumurta': '1_4_6',  # Eggs
            'yağ': '1_5_1',  # Oil
            'zeytin': '1_7_5_3',  # Olives
            'meyve': '1_7',  # Fruits (general)
            'sebze': '1_8',  # Vegetables (general)
            'domates': '1_8_2_4',  # Tomatoes
            'patates': '1_8_6_1',  # Potatoes
            'şeker': '1_9_1',  # Sugar
            'kahve': '1_10_2',  # Coffee
            'çay': '1_10_3',  # Tea
            'su': '1_10_4',  # Water
            'bira': '1_11_3',  # Beer
            'şarap': '1_11_2',  # Wine
            'rakı': '1_11_1_1',  # Raki (Turkish spirit)
            
            # Clothing
            'erkek': '2_1',  # Men's clothing
            'kadın': '2_1',  # Women's clothing
            'çocuk': '2_1',  # Children's clothing
            'ayakkabı': '2_2',  # Footwear
            'bot': '2_2',  # Boots
            'elbise': '2_1',  # Dress
            'pantolon': '2_1',  # Trousers
            'gömlek': '2_1',  # Shirt
            'tişört': '2_1',  # T-shirt
            'kazak': '2_1',  # Sweater
            
            # Housing/Rent
            'kiralık': '3_1',  # Rental
            'daire': '3_1',  # Apartment
            'ev': '3_1',  # House
            'oda': '3_1',  # Room
            
            # Utilities
            'elektrik': '3_4_1',  # Electricity
            'gaz': '3_4_2',  # Gas
            'su': '3_3_1',  # Water
            'doğalgaz': '3_4_2_1',  # Natural gas
            'tüpgaz': '3_4_2_2',  # LPG
            
            # Furniture
            'mobilya': '4_1',  # Furniture
            'kanepe': '4_1',  # Sofa
            'masa': '4_1',  # Table
            'sandalye': '4_1',  # Chair
            'yatak': '4_1',  # Bed
            'halı': '4_1',  # Carpet
            'perdeler': '4_2_1',  # Curtains
            'nevresim': '4_2_2',  # Bedding
            'yorgan': '4_2_2',  # Quilt
            
            # Appliances
            'buzdolabı': '4_3_1_1',  # Refrigerator
            'çamaşır makinesi': '4_3_1_2',  # Washing machine
            'fırın': '4_3_1_1',  # Oven
            'oto': '4_3_1_1',  # Oven
            'klima': '4_3_1_3',  # Air conditioner
            'soba': '4_3_1_3',  # Heater
            
            # Transport
            'araba': '5_1_1',  # Car
            'oto': '5_1_1',  # Car
            'benzin': '5_2_2_1',  # Petrol
            'motorin': '5_2_2_1',  # Diesel
            'lpg': '5_2_2_2',  # LPG for vehicles
            'kargo': '5_4_1',  # Courier
            'taksi': '5_3_3',  # Taxi
            'otobüs': '5_3_2_1',  # Bus
            'tren': '5_3_1',  # Train
            
            # Communication
            'telefon': '6_1_1',  # Mobile phone
            'internet': '6_2_2',  # Internet
            'cep': '6_1_1',  # Mobile
            'bilgisayar': '6_1_2_1',  # Computer
            
            # Health
            'ilaç': '7_1_1',  # Medicine
            'doktor': '7_2_1_2',  # Doctor
            'diş': '7_2_1_1',  # Dental
            
            # Recreation
            'film': '8_2_1',  # Cinema/recreation
            'spor': '8_1_2',  # Sports
            'kitap': '8_4_1',  # Books
        }
    
    def map_product(self, product_name: str, store: Optional[str] = None, 
                    category_hint: Optional[str] = None) -> Tuple[Optional[str], float]:
        """
        Map product name to TUFE category
        
        Args:
            product_name: Name of product to map
            store: Store name (for context)
            category_hint: Hint about category (e.g., 'food', 'clothing', 'rent')
            
        Returns:
            (tufe_category_code, confidence_score) or (None, 0.0) if unmapped
        """
        # Check cache first
        cache_key = f"{product_name}_{category_hint}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Step 1: Try manual overrides
        result = self._match_manual_overrides(product_name)
        if result:
            self.cache[cache_key] = (result, 0.95)
            return result, 0.95
        
        # Step 2: Try keyword matching
        result, score = self._match_keywords(product_name, category_hint)
        if score > 0.7:
            self.cache[cache_key] = (result, score)
            return result, score
        
        # Step 3: Try fuzzy string matching
        result, score = self._match_fuzzy(product_name, category_hint)
        if score > 0.6:
            self.cache[cache_key] = (result, score)
            return result, score
        
        # Step 4: Fallback to category hint if provided
        if category_hint:
            result = self._get_default_for_hint(category_hint)
            if result:
                self.cache[cache_key] = (result, 0.3)
                return result, 0.3
        
        # Not mapped
        self.unmatched_log.append({'product': product_name, 'store': store, 'hint': category_hint})
        self.cache[cache_key] = (None, 0.0)
        return None, 0.0
    
    def _match_manual_overrides(self, product_name: str) -> Optional[str]:
        """Match against manual override dictionary"""
        name_lower = self._normalize_text(product_name)
        
        for pattern, category_code in self.manual_overrides.items():
            if pattern in name_lower:
                return category_code
        
        return None
    
    def _match_keywords(self, product_name: str, category_hint: Optional[str]) -> Tuple[Optional[str], float]:
        """Match against TUFE category keywords"""
        name_lower = self._normalize_text(product_name)
        words = re.split(r'[\s\-\,]+', name_lower)
        
        best_match = None
        best_score = 0.0
        
        for word in words:
            if len(word) < 3:
                continue
            
            matching_categories = self.tufe.search_by_keyword(word)
            if matching_categories:
                # Score by word length (longer matches are better)
                score = len(word) / len(product_name)
                if score > best_score:
                    best_score = score
                    best_match = matching_categories[0]
        
        return best_match, best_score if best_score > 0.3 else 0.0
    
    def _match_fuzzy(self, product_name: str, category_hint: Optional[str]) -> Tuple[Optional[str], float]:
        """Fuzzy string matching against TUFE categories"""
        name_lower = self._normalize_text(product_name)
        
        best_code = None
        best_ratio = 0.0
        
        # Get candidate categories based on hint
        if category_hint:
            candidates = self._get_candidates_for_hint(category_hint)
        else:
            candidates = list(self.tufe.categories.keys())
        
        for code in candidates:
            cat = self.tufe.get_category_by_code(code)
            if not cat:
                continue
            
            # Try matching against both Turkish and English names
            ratio_tr = SequenceMatcher(None, name_lower, self._normalize_text(cat['name_tr'])).ratio()
            ratio_en = SequenceMatcher(None, name_lower, self._normalize_text(cat['name_en'])).ratio()
            ratio = max(ratio_tr, ratio_en)
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_code = code
        
        return best_code, best_ratio if best_ratio > 0.3 else 0.0
    
    def _normalize_text(self, text: str) -> str:
        """Normalize Turkish text for matching"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove Turkish diacritics
        turkish_map = {
            'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 
            'ş': 's', 'ü': 'u', 'é': 'e', 'è': 'e'
        }
        for turkish_char, replacement in turkish_map.items():
            text = text.replace(turkish_char, replacement)
        
        # Remove special characters except spaces
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _get_candidates_for_hint(self, category_hint: str) -> List[str]:
        """Get TUFE categories matching category hint"""
        hint_lower = category_hint.lower()
        candidates = []
        
        hint_mapping = {
            'food': ['1'],  # Root categories starting with 1
            'market': ['1'],
            'clothing': ['2'],
            'apparel': ['2'],
            'housing': ['3'],
            'rent': ['3'],
            'furniture': ['4'],
            'home': ['4'],
            'transport': ['5'],
            'vehicle': ['5'],
            'communication': ['6'],
            'health': ['7'],
            'recreation': ['8'],
            'education': ['8'],
            'restaurant': ['8', '9'],
            'insurance': ['10'],
            'personal': ['11'],
        }
        
        prefixes = hint_mapping.get(hint_lower, [])
        for code in self.tufe.categories.keys():
            for prefix in prefixes:
                if code.startswith(prefix):
                    candidates.append(code)
        
        return candidates
    
    def _get_default_for_hint(self, category_hint: str) -> Optional[str]:
        """Get default TUFE category for a hint"""
        hint_mapping = {
            'food': '1_1',  # Food general
            'market': '1_1',
            'clothing': '2_1',  # Clothing general
            'apparel': '2_1',
            'housing': '3_1',  # Rental
            'rent': '3_1',
            'furniture': '4_1',  # Furniture
            'home': '4_1',
            'transport': '5_1',  # Vehicles
            'vehicle': '5_1',
            'communication': '6_1',  # Communication equipment
            'health': '7_1',  # Health
            'recreation': '8_1',  # Recreation
            'education': '8_3',  # Education
            'restaurant': '9_1',  # Restaurants
            'insurance': '10_1',  # Insurance
            'personal': '11_1',  # Personal care
        }
        return hint_mapping.get(category_hint.lower())
    
    def map_batch(self, products: List[Tuple[str, Optional[str], Optional[str]]]) -> List[Tuple[str, str, float]]:
        """
        Map batch of products
        
        Args:
            products: List of (product_name, store, category_hint) tuples
            
        Returns:
            List of (product_name, tufe_code, confidence) tuples
        """
        results = []
        for product_name, store, hint in products:
            code, confidence = self.map_product(product_name, store, hint)
            results.append((product_name, code or 'UNMAPPED', confidence))
        
        return results
    
    def get_unmapped_summary(self) -> Dict:
        """Get summary of unmapped products"""
        if not self.unmatched_log:
            return {'total_unmapped': 0, 'by_store': {}, 'by_category_hint': {}}
        
        summary = {
            'total_unmapped': len(self.unmatched_log),
            'by_store': {},
            'by_category_hint': {},
            'samples': self.unmatched_log[:20]  # First 20 for review
        }
        
        for entry in self.unmatched_log:
            store = entry['store'] or 'unknown'
            hint = entry['category_hint'] or 'unknown'
            
            summary['by_store'][store] = summary['by_store'].get(store, 0) + 1
            summary['by_category_hint'][hint] = summary['by_category_hint'].get(hint, 0) + 1
        
        return summary


def create_mapper(tufe_parser) -> ProductMapper:
    """Factory function to create ProductMapper"""
    return ProductMapper(tufe_parser)


if __name__ == '__main__':
    from tufe_parser import load_tufe
    
    tufe_path = r'c:\Users\onurk\Desktop\Projects\InflationResearchStudy\Inflations\Codes\TUFE'
    print(f"Loading TUFE from {tufe_path}...\n")
    tufe = load_tufe(tufe_path)
    
    mapper = ProductMapper(tufe)
    
    # Test mappings
    test_products = [
        ('Beyaz Peynir 500g', 'Market A', 'food'),
        ('Erkek Tişört', 'Zara', 'clothing'),
        ('Arçelik Buzdolabı', 'Beymen', 'home'),
        ('Suzuki Swift', 'Dealership', 'vehicle'),
        ('Bir ürün adı', 'Unknown Store', None),
    ]
    
    print("Testing product mapping:\n")
    for product_name, store, hint in test_products:
        code, confidence = mapper.map_product(product_name, store, hint)
        if code:
            cat = tufe.get_category_by_code(code)
            print(f"'{product_name}' -> [{code}] {cat['name_en']} (confidence: {confidence:.2f})")
        else:
            print(f"'{product_name}' -> UNMAPPED")
    
    print(f"\n\nUnmapped summary: {mapper.get_unmapped_summary()}")
