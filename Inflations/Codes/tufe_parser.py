"""
TUFE Parser - Parse Turkish Consumer Price Index (TUFE) file
Extracts hierarchical category structure, weights, and keywords for product mapping
"""

import re
from typing import Dict, List, Tuple, Optional


class TUFEParser:
    """Parse TUFE file and build searchable category hierarchy"""
    
    def __init__(self, tufe_file_path: str):
        self.tufe_file = tufe_file_path
        self.categories = {}
        self.category_tree = None
        self.by_english_name = {}
        self.by_turkish_name = {}
        
    def parse(self) -> Dict:
        lines = self._read_tufe_file()
        self.categories, self.category_tree = self._build_hierarchy(lines)
        self._build_lookup_indexes()
        
        return {
            'categories': self.categories,
            'tree': self.category_tree,
            'count': len(self.categories),
            'total_weight': sum(cat['weight'] for cat in self.categories.values() 
                               if cat.get('level') == 0)  # Top-level weights
        }
    
    def _read_tufe_file(self) -> List[str]:
        with open(self.tufe_file, 'r', encoding='utf-8') as f:
            return f.readlines()
    
    def _build_hierarchy(self, lines: List[str]) -> Tuple[Dict, Dict]:
        categories = {}
        tree = {}
        category_counter = {}
        
        # Track parent hierarchy. Format: (indentation_spaces_count, category_code)
        parent_stack = [(-1, 'root')] 
        
        for line_num, line in enumerate(lines):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            
            # Detect leading spaces or tabs
            indent_match = re.match(r'^([ \t]+)?(.+)', line)
            if not indent_match:
                continue
                
            indent_str = indent_match.group(1) or ''
            content = indent_match.group(2)
            
            # Calculate a generic "indent weight" (Tab = 4 spaces, Space = 1)
            current_indent = indent_str.count('\t') * 4 + indent_str.count(' ')
            
            # Split columns by 2 or more spaces, or tabs
            parts = re.split(r' {2,}|\t+', content)
            
            if len(parts) < 2:
                continue
                
            name_tr = parts[0].strip()
            name_en = parts[1].strip()
            
            weight = 0.0
            if len(parts) >= 3:
                try:
                    weight = float(parts[2].strip())
                except ValueError:
                    weight = 0.0
            
            # Traverse up the tree if current indent is less than or equal to the previous one
            while len(parent_stack) > 1 and parent_stack[-1][0] >= current_indent:
                parent_stack.pop()
                
            parent_code = parent_stack[-1][1]
            level = len(parent_stack) - 1
            
            # Generate smart hierarchical code
            if parent_code not in category_counter:
                category_counter[parent_code] = 1
            else:
                category_counter[parent_code] += 1
                
            if parent_code == 'root':
                code = str(category_counter[parent_code])
            else:
                code = f"{parent_code}_{category_counter[parent_code]}"
            
            keywords = self._extract_keywords(name_tr, name_en)
            
            cat_data = {
                'code': code,
                'name_tr': name_tr,
                'name_en': name_en,
                'weight': weight,
                'level': level,
                'keywords': keywords,
                'parent_code': parent_code if parent_code != 'root' else None,
                'children': []
            }
            
            categories[code] = cat_data
            
            if parent_code == 'root':
                tree[code] = cat_data
            else:
                categories[parent_code]['children'].append(code)
                
            parent_stack.append((current_indent, code))
        
        return categories, tree
    
    def _extract_keywords(self, name_tr: str, name_en: str) -> List[str]:
        keywords = []
        for word in re.split(r'[\s\-\,]+', name_tr.lower()):
            if len(word) > 2: keywords.append(word)
        for word in re.split(r'[\s\-\,]+', name_en.lower()):
            if len(word) > 2: keywords.append(word)
        return list(set(keywords))
    
    def _build_lookup_indexes(self):
        for code, cat in self.categories.items():
            self.by_english_name[cat['name_en'].lower()] = code
            self.by_turkish_name[cat['name_tr'].lower()] = code
    
    def get_category_by_code(self, code: str) -> Optional[Dict]:
        return self.categories.get(code)
    
    def search_by_keyword(self, keyword: str, language: str = 'en') -> List[str]:
        keyword_lower = keyword.lower()
        matches = []
        for code, cat in self.categories.items():
            if keyword_lower in cat['keywords']:
                matches.append(code)
        return matches

def load_tufe(tufe_file_path: str) -> TUFEParser:
    parser = TUFEParser(tufe_file_path)
    parser.parse()
    return parser

if __name__ == '__main__':
    import sys
    tufe_path = sys.argv[1] if len(sys.argv) > 1 else r'c:\Users\onurk\Desktop\Projects\InflationResearchStudy\Inflations\Codes\TUFE'
    print(f"Parsing TUFE file: {tufe_path}\n")
    parser = load_tufe(tufe_path)
    print(f"Total categories: {parser.parse()['count']}")
    print(f"Total weight (root level): {parser.parse()['total_weight']:.4f}\n")