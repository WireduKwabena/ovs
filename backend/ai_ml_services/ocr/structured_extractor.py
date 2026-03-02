"""
Structured Data Extractor
==========================

Extract structured information from OCR text using NLP and pattern matching.

Academic Note:
--------------
Combines rule-based (regex) and ML-based (NER) approaches:
1. Named Entity Recognition (spaCy)
2. Pattern matching (regex)
3. Template matching
4. LLM-based extraction (optional)

Use Cases:
- Extract names, dates, IDs from documents
- Parse addresses, phone numbers
- Find specific fields (e.g., "Date of Birth:")
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import spacy
from dateutil import parser as date_parser
import logging

logger = logging.getLogger(__name__)


class StructuredExtractor:
    """
    Extract structured data from unstructured OCR text.
    
    Extracts:
    - Names (person, organization)
    - Dates
    - Numbers (IDs, phone, amounts)
    - Addresses
    - Document-specific fields
    """
    
    def __init__(self, language: str = 'en'):
        """
        Initialize extractor.
        
        Args:
            language: Language code ('en', 'es', etc.)
        """
        self.language = language
        
        # Load spaCy model (lazy loading)
        self._nlp = None
        
        # Common field patterns
        self.field_patterns = {
            'name': [
                r'name[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                r'full\s+name[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            ],
            'date_of_birth': [
                r'(?:date of birth|dob|born)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'(?:date of birth|dob|born)[:\s]+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
            ],
            'id_number': [
                r'(?:id|identification)\s*(?:number|no|#)?[:\s]*([A-Z0-9]{6,})',
                r'(?:passport|license)\s*(?:number|no|#)?[:\s]*([A-Z0-9]{6,})',
            ],
            'email': [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            ],
            'phone': [
                r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            ],
            'address': [
                r'\d+\s+[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)',
            ],
        }
    
    @property
    def nlp(self):
        """Lazy load spaCy model."""
        if self._nlp is None:
            try:
                self._nlp = spacy.load(f'{self.language}_core_web_lg')
            except OSError:
                logger.warning(f"spaCy model '{self.language}_core_web_lg' not found. Install with: python -m spacy download {self.language}_core_web_lg")
                # Fallback to blank model
                self._nlp = spacy.blank(self.language)
        return self._nlp
    
    def extract(self, text: str, document_type: str = None) -> Dict:
        """
        Extract all structured data from text.
        
        Args:
            text: OCR extracted text
            document_type: Optional document type hint
                ('id_card', 'passport', 'birth_certificate', etc.)
        
        Returns:
            Dictionary with extracted fields
        """
        extracted = {
            'document_type': document_type,
            'entities': {},
            'fields': {},
            'dates': [],
            'confidence': 0.0
        }
        
        # Named Entity Recognition
        entities = self._extract_entities(text)
        extracted['entities'] = entities
        
        # Pattern-based field extraction
        fields = self._extract_fields(text)
        extracted['fields'] = fields
        
        # Date extraction
        dates = self._extract_dates(text)
        extracted['dates'] = dates
        
        # Document type-specific extraction
        if document_type:
            specific = self._extract_document_specific(text, document_type)
            extracted['fields'].update(specific)
        
        # Calculate confidence based on number of extracted fields
        total_possible = 10  # Assume 10 important fields
        extracted_count = (
            len(entities.get('PERSON', [])) +
            len(entities.get('ORG', [])) +
            len(fields) +
            len(dates)
        )
        extracted['confidence'] = min(100, (extracted_count / total_possible) * 100)
        
        logger.info(f"Extracted {extracted_count} fields, confidence={extracted['confidence']:.1f}%")
        
        return extracted
    
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities using spaCy.
        
        Returns:
            {
                'PERSON': [...],
                'ORG': [...],
                'GPE': [...],  # Geo-political entities
                'DATE': [...],
                'MONEY': [...],
                ...
            }
        """
        doc = self.nlp(text)
        
        entities = {}
        for ent in doc.ents:
            if ent.label_ not in entities:
                entities[ent.label_] = []
            entities[ent.label_].append(ent.text)
        
        # Remove duplicates
        for key in entities:
            entities[key] = list(set(entities[key]))
        
        return entities
    
    def _extract_fields(self, text: str) -> Dict[str, Any]:
        """
        Extract specific fields using pattern matching.
        
        Returns:
            Dictionary of field: value pairs
        """
        fields = {}
        
        for field_name, patterns in self.field_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    # Take first match
                    fields[field_name] = matches[0].strip()
                    break
        
        return fields
    
    def _extract_dates(self, text: str) -> List[Dict]:
        """
        Extract and parse all dates from text.
        
        Returns:
            List of date dictionaries:
            [
                {
                    'raw': '12/05/2020',
                    'parsed': '2020-05-12',
                    'format': 'DD/MM/YYYY',
                    'confidence': 0.9
                },
                ...
            ]
        """
        dates = []
        
        # Common date patterns
        patterns = [
            (r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', 'numeric'),
            (r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b', 'month_name'),
            (r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b', 'day_month_year'),
        ]
        
        for pattern, date_format in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            for match in matches:
                try:
                    # Try to parse the date
                    parsed_date = date_parser.parse(match, fuzzy=False)
                    
                    dates.append({
                        'raw': match,
                        'parsed': parsed_date.strftime('%Y-%m-%d'),
                        'format': date_format,
                        'confidence': 0.9 if date_format != 'numeric' else 0.7
                    })
                except:
                    # Could not parse
                    dates.append({
                        'raw': match,
                        'parsed': None,
                        'format': date_format,
                        'confidence': 0.3
                    })
        
        return dates
    
    def _extract_document_specific(
        self,
        text: str,
        document_type: str
    ) -> Dict:
        """
        Extract document-type specific fields.
        
        Each document type has known fields.
        """
        specific = {}
        
        if document_type == 'id_card':
            specific.update(self._extract_id_card_fields(text))
        elif document_type == 'passport':
            specific.update(self._extract_passport_fields(text))
        elif document_type == 'birth_certificate':
            specific.update(self._extract_birth_certificate_fields(text))
        elif document_type == 'degree':
            specific.update(self._extract_degree_fields(text))
        
        return specific
    
    def _extract_id_card_fields(self, text: str) -> Dict:
        """Extract ID card specific fields."""
        fields = {}
        
        # ID Number
        id_pattern = r'(?:id|card)\s*(?:number|no|#)?[:\s]*([A-Z0-9]{6,15})'
        match = re.search(id_pattern, text, re.IGNORECASE)
        if match:
            fields['id_number'] = match.group(1)
        
        # Expiry Date
        expiry_pattern = r'(?:expir|valid until)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        match = re.search(expiry_pattern, text, re.IGNORECASE)
        if match:
            fields['expiry_date'] = match.group(1)
        
        # Issue Date
        issue_pattern = r'(?:issue|issued)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        match = re.search(issue_pattern, text, re.IGNORECASE)
        if match:
            fields['issue_date'] = match.group(1)
        
        return fields
    
    def _extract_passport_fields(self, text: str) -> Dict:
        """Extract passport specific fields."""
        fields = {}
        
        # Passport Number (alphanumeric, 6-9 chars)
        passport_pattern = r'(?:passport)\s*(?:number|no|#)?[:\s]*([A-Z0-9]{6,9})'
        match = re.search(passport_pattern, text, re.IGNORECASE)
        if match:
            fields['passport_number'] = match.group(1)
        
        # Nationality
        nationality_pattern = r'(?:nationality|citizen)[:\s]*([A-Z][a-z]+)'
        match = re.search(nationality_pattern, text, re.IGNORECASE)
        if match:
            fields['nationality'] = match.group(1)
        
        # Place of Birth
        pob_pattern = r'(?:place of birth|born in)[:\s]*([A-Z][a-z]+(?:,?\s*[A-Z][a-z]+)*)'
        match = re.search(pob_pattern, text, re.IGNORECASE)
        if match:
            fields['place_of_birth'] = match.group(1)
        
        return fields
    
    def _extract_birth_certificate_fields(self, text: str) -> Dict:
        """Extract birth certificate specific fields."""
        fields = {}
        
        # Mother's Name
        mother_pattern = r'mother[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
        match = re.search(mother_pattern, text, re.IGNORECASE)
        if match:
            fields['mother_name'] = match.group(1)
        
        # Father's Name
        father_pattern = r'father[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
        match = re.search(father_pattern, text, re.IGNORECASE)
        if match:
            fields['father_name'] = match.group(1)
        
        # Registration Number
        reg_pattern = r'(?:registration|cert|certificate)\s*(?:number|no|#)?[:\s]*([A-Z0-9]{6,})'
        match = re.search(reg_pattern, text, re.IGNORECASE)
        if match:
            fields['registration_number'] = match.group(1)
        
        return fields
    
    def _extract_degree_fields(self, text: str) -> Dict:
        """Extract degree/certificate specific fields."""
        fields = {}
        
        # Degree Type
        degree_pattern = r'\b(Bachelor|Master|PhD|Doctorate|Diploma|Certificate)\s+of\s+([A-Za-z\s]+)'
        match = re.search(degree_pattern, text, re.IGNORECASE)
        if match:
            fields['degree_type'] = match.group(0)
        
        # University/Institution
        uni_pattern = r'(?:university|college|institute|school)\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        match = re.search(uni_pattern, text, re.IGNORECASE)
        if match:
            fields['institution'] = match.group(0)
        
        # Graduation Date
        grad_pattern = r'(?:graduated|conferred|awarded)[:\s]*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})'
        match = re.search(grad_pattern, text, re.IGNORECASE)
        if match:
            fields['graduation_date'] = match.group(1)
        
        # GPA/Grade
        gpa_pattern = r'(?:gpa|grade)[:\s]*(\d+\.\d+|\d+/\d+|[A-D][+-]?)'
        match = re.search(gpa_pattern, text, re.IGNORECASE)
        if match:
            fields['gpa'] = match.group(1)
        
        return fields
    
    def extract_key_value_pairs(self, text: str) -> Dict[str, str]:
        """
        Extract key-value pairs from structured text.
        
        Finds patterns like:
        - Name: John Doe
        - DOB: 01/01/1990
        - Address: 123 Main St
        
        Returns:
            Dictionary of key: value pairs
        """
        pairs = {}
        
        # Pattern: "Key: Value" or "Key Value" (with newline)
        pattern = r'([A-Z][A-Za-z\s]+?):\s*([^\n]+)'
        
        matches = re.findall(pattern, text)
        
        for key, value in matches:
            key = key.strip().lower().replace(' ', '_')
            value = value.strip()
            pairs[key] = value
        
        return pairs


class TemplateBasedExtractor:
    """
    Extract data using predefined document templates.
    
    Academic Note:
    --------------
    Template matching for standardized documents:
    - Define field positions (bounding boxes)
    - Extract based on coordinates
    - More accurate but less flexible
    """
    
    def __init__(self):
        """Initialize template extractor."""
        self.templates = {}
    
    def add_template(
        self,
        template_name: str,
        field_positions: Dict[str, Tuple[int, int, int, int]]
    ):
        """
        Add document template.
        
        Args:
            template_name: Template identifier
            field_positions: Dict of field_name: (x, y, width, height)
        """
        self.templates[template_name] = field_positions
    
    def extract_from_template(
        self,
        ocr_result: Dict,
        template_name: str
    ) -> Dict:
        """
        Extract fields based on template.
        
        Args:
            ocr_result: Result from OCR service with bounding boxes
            template_name: Which template to use
        
        Returns:
            Extracted fields
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        template = self.templates[template_name]
        extracted = {}
        
        # Get words and boxes from OCR result
        words = ocr_result['details']['words']
        boxes = ocr_result['details']['boxes']
        
        # For each template field
        for field_name, (tx, ty, tw, th) in template.items():
            # Find words in this region
            field_words = []
            
            for word, (x, y, w, h) in zip(words, boxes):
                # Check if box overlaps with template region
                if (x >= tx and x <= tx + tw and
                    y >= ty and y <= ty + th):
                    field_words.append(word)
            
            # Join words
            extracted[field_name] = ' '.join(field_words)
        
        return extracted


# Django integration
def extract_structured_data(document_id: int) -> Dict:
    """
    Extract structured data from document.
    
    Usage:
    ```python
    from ai_ml_services.ocr.structured_extractor import extract_structured_data
    
    data = extract_structured_data(document.id)
    ```
    """
    from apps.applications.models import Document
    
    document = Document.objects.get(id=document_id)
    
    # Initialize extractor
    extractor = StructuredExtractor()
    
    # Extract structured data
    structured_data = extractor.extract(
        text=document.extracted_text,
        document_type=document.document_type
    )
    
    # Save to database
    document.extracted_data = structured_data
    document.save()
    
    logger.info(f"Structured extraction complete for document {document_id}")
    
    return structured_data


if __name__ == "__main__":
    # Test extractor
    extractor = StructuredExtractor()
    
    sample_text = """
    NATIONAL IDENTITY CARD
    
    Name: John Doe
    Date of Birth: 01/15/1990
    ID Number: ABC123456
    Address: 123 Main Street, New York, NY 10001
    Email: john.doe@example.com
    Phone: +1-555-123-4567
    Issue Date: 01/01/2020
    Expiry Date: 01/01/2030
    """
    
    result = extractor.extract(sample_text, document_type='id_card')
    
    import json
    print(json.dumps(result, indent=2))

