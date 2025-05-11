"""
Form Analysis module for CaptiveClone.

This module provides advanced form field identification and mapping capabilities
for captive portal forms, helping to categorize and validate captured credentials.
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Any, Set
from enum import Enum
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class FieldType(Enum):
    """Types of form fields found in captive portals."""
    USERNAME = "username"
    PASSWORD = "password"
    EMAIL = "email"
    PHONE = "phone"
    ROOM_NUMBER = "room_number"
    NAME = "name"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    COMPANY = "company"
    ADDRESS = "address"
    CITY = "city"
    STATE = "state"
    ZIPCODE = "zipcode"
    COUNTRY = "country"
    TERMS = "terms"
    CAPTCHA = "captcha"
    DURATION = "duration"
    PAYMENT = "payment"
    CARD_NUMBER = "card_number"
    CARD_EXPIRY = "card_expiry"
    CARD_CVV = "card_cvv"
    SUBMISSION = "submission"
    UNKNOWN = "unknown"

class PortalType(Enum):
    """Types of captive portals commonly found."""
    HOTEL = "hotel"
    AIRPORT = "airport"
    CAFE = "cafe"
    ENTERPRISE = "enterprise"
    EDUCATIONAL = "educational"
    HEALTHCARE = "healthcare"
    PUBLIC = "public"
    CONFERENCE = "conference"
    PAID = "paid"
    CONSENT = "consent"
    UNKNOWN = "unknown"

class FormAnalyzer:
    """
    Advanced form field analyzer for captive portals.
    
    This class identifies form fields and their purposes based on various
    heuristics including form attributes, labels, placeholders, and nearby text.
    """
    
    def __init__(self):
        """Initialize the form analyzer."""
        # Patterns for field identification
        self.field_patterns = {
            FieldType.USERNAME: [
                r'(?i)username', r'(?i)user\s*name', r'(?i)user\s*id', r'(?i)login', 
                r'(?i)account', r'(?i)userid', r'(?i)user'
            ],
            FieldType.PASSWORD: [
                r'(?i)password', r'(?i)pass\s*word', r'(?i)passw', r'(?i)pwd', 
                r'(?i)secret'
            ],
            FieldType.EMAIL: [
                r'(?i)email', r'(?i)e-mail', r'(?i)correo', r'(?i)mail'
            ],
            FieldType.PHONE: [
                r'(?i)phone', r'(?i)mobile', r'(?i)cell', r'(?i)telephone', 
                r'(?i)number', r'(?i)tel'
            ],
            FieldType.ROOM_NUMBER: [
                r'(?i)room', r'(?i)suite', r'(?i)room\s*number', r'(?i)room\s*no'
            ],
            FieldType.NAME: [
                r'(?i)full\s*name', r'(?i)name', r'(?i)nombre'
            ],
            FieldType.FIRST_NAME: [
                r'(?i)first\s*name', r'(?i)forename', r'(?i)given\s*name', 
                r'(?i)first'
            ],
            FieldType.LAST_NAME: [
                r'(?i)last\s*name', r'(?i)surname', r'(?i)family\s*name', 
                r'(?i)last'
            ],
            FieldType.COMPANY: [
                r'(?i)company', r'(?i)organization', r'(?i)employer', 
                r'(?i)business', r'(?i)firm'
            ],
            FieldType.TERMS: [
                r'(?i)terms', r'(?i)conditions', r'(?i)agree', r'(?i)accept', 
                r'(?i)policy', r'(?i)consent'
            ],
            FieldType.CAPTCHA: [
                r'(?i)captcha', r'(?i)security\s*code', r'(?i)verification', 
                r'(?i)verify'
            ],
            FieldType.DURATION: [
                r'(?i)duration', r'(?i)time', r'(?i)period', r'(?i)length', 
                r'(?i)minutes', r'(?i)hours'
            ],
            FieldType.PAYMENT: [
                r'(?i)payment', r'(?i)credit', r'(?i)debit', r'(?i)card', 
                r'(?i)transaction', r'(?i)pay'
            ]
        }
        
        # Portal type identification patterns
        self.portal_type_patterns = {
            PortalType.HOTEL: [
                r'(?i)hotel', r'(?i)room', r'(?i)guest', r'(?i)reservation', 
                r'(?i)booking', r'(?i)stay', r'(?i)resort', r'(?i)suite'
            ],
            PortalType.AIRPORT: [
                r'(?i)airport', r'(?i)terminal', r'(?i)flight', r'(?i)airline', 
                r'(?i)passenger', r'(?i)travel', r'(?i)gate'
            ],
            PortalType.CAFE: [
                r'(?i)cafe', r'(?i)coffee', r'(?i)restaurant', r'(?i)shop', 
                r'(?i)bistro', r'(?i)menu'
            ],
            PortalType.ENTERPRISE: [
                r'(?i)enterprise', r'(?i)corporate', r'(?i)business', r'(?i)employee', 
                r'(?i)company', r'(?i)staff'
            ],
            PortalType.EDUCATIONAL: [
                r'(?i)school', r'(?i)university', r'(?i)college', r'(?i)campus', 
                r'(?i)student', r'(?i)faculty', r'(?i)education'
            ],
            PortalType.HEALTHCARE: [
                r'(?i)hospital', r'(?i)clinic', r'(?i)medical', r'(?i)patient', 
                r'(?i)health', r'(?i)doctor', r'(?i)care'
            ],
            PortalType.CONFERENCE: [
                r'(?i)conference', r'(?i)event', r'(?i)meeting', r'(?i)convention', 
                r'(?i)attendee', r'(?i)exhibition'
            ],
            PortalType.PAID: [
                r'(?i)paid', r'(?i)premium', r'(?i)purchase', r'(?i)buy', 
                r'(?i)subscription', r'(?i)plan', r'(?i)package'
            ]
        }
    
    def analyze_form(self, html_content: str) -> Dict[str, Dict[str, Any]]:
        """
        Analyze the forms in HTML content and identify field types.
        
        Args:
            html_content: The HTML content containing forms.
            
        Returns:
            Dictionary mapping form IDs to form information including field mappings.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        forms = soup.find_all('form')
        
        if not forms:
            logger.warning("No forms found in HTML content")
            return {}
        
        result = {}
        for i, form in enumerate(forms):
            form_id = form.get('id', f"form_{i+1}")
            
            # Extract form action and method
            action = form.get('action', '')
            method = form.get('method', 'post').lower()
            
            # Find all input, select, and textarea elements
            inputs = form.find_all(['input', 'select', 'textarea'])
            
            fields = {}
            for field in inputs:
                field_info = self._analyze_field(field, form)
                if field_info:
                    name = field_info.get('name', '')
                    if name:  # Only include fields with name attributes
                        fields[name] = field_info
            
            # Detect portal type
            portal_type = self._detect_portal_type(form, fields)
            
            result[form_id] = {
                'action': action,
                'method': method,
                'fields': fields,
                'portal_type': portal_type.value,
                'is_login_form': self._is_login_form(fields)
            }
        
        return result
    
    def _analyze_field(self, field_elem, form_elem) -> Optional[Dict[str, Any]]:
        """
        Analyze a single form field to determine its type and purpose.
        
        Args:
            field_elem: The BeautifulSoup element for the form field
            form_elem: The parent form element
            
        Returns:
            Dictionary with field information or None if field should be ignored
        """
        # Extract basic field attributes
        tag_name = field_elem.name
        field_type = field_elem.get('type', '').lower() if tag_name == 'input' else tag_name
        name = field_elem.get('name', '')
        id_attr = field_elem.get('id', '')
        value = field_elem.get('value', '')
        placeholder = field_elem.get('placeholder', '')
        
        # Ignore submit buttons and hidden fields (but keep hidden password fields)
        if (field_type == 'submit' or (field_type == 'hidden' and 'password' not in name.lower())):
            return None
        
        # Get field label if available
        label = self._find_label(field_elem, form_elem)
        
        # Score different field types based on various attributes
        field_type_scores = self._score_field_types(tag_name, field_type, name, id_attr, placeholder, label)
        
        # Determine the most likely field type
        best_type, confidence = self._get_best_field_type(field_type_scores)
        
        # Create field info dictionary
        field_info = {
            'name': name,
            'html_type': field_type,
            'field_type': best_type.value,
            'confidence': confidence,
            'required': field_elem.get('required') is not None,
            'label': label,
            'suggestions': self._get_field_suggestions(best_type)
        }
        
        return field_info
    
    def _find_label(self, field_elem, form_elem) -> str:
        """Find the label text for a form field."""
        field_id = field_elem.get('id')
        if field_id:
            # Look for label with matching 'for' attribute
            label_elem = form_elem.find('label', attrs={'for': field_id})
            if label_elem:
                return label_elem.text.strip()
        
        # Check if field is inside a label
        parent = field_elem.parent
        while parent and parent != form_elem:
            if parent.name == 'label':
                # Get text nodes directly inside the label, excluding nested elements
                texts = [text for text in parent.stripped_strings]
                # Remove the field's own placeholder or value
                field_texts = [field_elem.get('placeholder', ''), field_elem.get('value', '')]
                label_texts = [t for t in texts if t and t not in field_texts]
                return ' '.join(label_texts)
            parent = parent.parent
        
        # Look for adjacent text
        prev_sibling = field_elem.previous_sibling
        if prev_sibling and isinstance(prev_sibling, str) and prev_sibling.strip():
            return prev_sibling.strip()
        
        return ""
    
    def _score_field_types(self, tag_name, field_type, name, id_attr, placeholder, label) -> Dict[FieldType, float]:
        """
        Score different field types based on the field's attributes.
        
        Returns:
            Dictionary mapping field types to confidence scores (0.0-1.0)
        """
        scores = {field_type: 0.0 for field_type in FieldType}
        
        # Base scores from HTML field type
        if field_type == 'password':
            scores[FieldType.PASSWORD] = 0.9
        elif field_type == 'email':
            scores[FieldType.EMAIL] = 0.9
        elif field_type == 'tel':
            scores[FieldType.PHONE] = 0.9
        elif field_type == 'checkbox' and self._matches_any_pattern(name + ' ' + label, self.field_patterns[FieldType.TERMS]):
            scores[FieldType.TERMS] = 0.9
        elif field_type == 'submit':
            scores[FieldType.SUBMISSION] = 1.0
            return scores  # Early return for submit buttons
        
        # Score based on name, id, placeholder, and label
        text_to_check = f"{name} {id_attr} {placeholder} {label}".lower()
        
        for field_type, patterns in self.field_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_to_check):
                    # Add points based on where the match was found
                    if re.search(pattern, name.lower()):
                        scores[field_type] += 0.5
                    if re.search(pattern, id_attr.lower()):
                        scores[field_type] += 0.4
                    if re.search(pattern, placeholder.lower()):
                        scores[field_type] += 0.3
                    if re.search(pattern, label.lower()):
                        scores[field_type] += 0.6
        
        # Special case for names
        if scores[FieldType.FIRST_NAME] > 0 and scores[FieldType.LAST_NAME] > 0:
            # If both first and last name are detected, keep the stronger one
            if scores[FieldType.FIRST_NAME] > scores[FieldType.LAST_NAME]:
                scores[FieldType.LAST_NAME] = 0
            else:
                scores[FieldType.FIRST_NAME] = 0
        
        return scores
    
    def _get_best_field_type(self, scores: Dict[FieldType, float]) -> Tuple[FieldType, float]:
        """
        Get the field type with the highest confidence score.
        
        Returns:
            Tuple of (field_type, confidence_score)
        """
        if not scores:
            return FieldType.UNKNOWN, 0.0
        
        best_type = FieldType.UNKNOWN
        best_score = 0.0
        
        for field_type, score in scores.items():
            if score > best_score:
                best_score = score
                best_type = field_type
        
        # Normalize confidence to 0.0-1.0 scale
        confidence = min(best_score, 1.0)
        
        # If confidence is too low, mark as unknown
        if confidence < 0.3:
            return FieldType.UNKNOWN, confidence
        
        return best_type, confidence
    
    def _get_field_suggestions(self, field_type: FieldType) -> List[str]:
        """
        Get a list of suggested values for a given field type.
        
        Returns:
            List of suggested values
        """
        suggestions = {
            FieldType.USERNAME: ["guest", "user", "visitor"],
            FieldType.EMAIL: ["guest@example.com", "visitor@example.com"],
            FieldType.PHONE: ["5555555555", "555-555-5555"],
            FieldType.ROOM_NUMBER: ["101", "202", "303"],
            FieldType.NAME: ["John Smith", "Jane Doe"],
            FieldType.FIRST_NAME: ["John", "Jane", "Robert", "Maria"],
            FieldType.LAST_NAME: ["Smith", "Doe", "Johnson", "Williams"],
            FieldType.COMPANY: ["Acme Inc", "Example Corp", "Visitor"],
            FieldType.ADDRESS: ["123 Main St", "456 Park Ave"],
            FieldType.CITY: ["New York", "Los Angeles", "Chicago"],
            FieldType.STATE: ["NY", "CA", "IL"],
            FieldType.ZIPCODE: ["10001", "90210", "60601"],
            FieldType.COUNTRY: ["United States", "Canada", "UK"],
        }
        
        return suggestions.get(field_type, [])
    
    def _detect_portal_type(self, form_elem, fields: Dict[str, Dict]) -> PortalType:
        """
        Detect the type of captive portal based on form content and fields.
        
        Args:
            form_elem: The BeautifulSoup form element
            fields: Dictionary of analyzed fields
            
        Returns:
            PortalType enum value
        """
        # Get all text from the form and nearby elements
        form_text = form_elem.get_text().lower()
        page_title = form_elem.find_parent('html').find('title')
        title_text = page_title.text.lower() if page_title else ""
        
        context_text = form_text + " " + title_text
        
        # Check for field combinations that indicate specific portal types
        has_room_field = any(f['field_type'] == FieldType.ROOM_NUMBER.value for f in fields.values())
        has_payment_field = any(f['field_type'] == FieldType.PAYMENT.value for f in fields.values())
        has_duration_field = any(f['field_type'] == FieldType.DURATION.value for f in fields.values())
        
        # Score portal types based on text patterns
        scores = {portal_type: 0.0 for portal_type in PortalType}
        
        for portal_type, patterns in self.portal_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, context_text):
                    scores[portal_type] += 0.3
        
        # Adjust scores based on field types
        if has_room_field:
            scores[PortalType.HOTEL] += 0.5
        
        if has_payment_field:
            scores[PortalType.PAID] += 0.4
        
        if has_duration_field:
            scores[PortalType.CAFE] += 0.2
            scores[PortalType.PAID] += 0.2
        
        # Check for terms and conditions (consent portal)
        if any(f['field_type'] == FieldType.TERMS.value for f in fields.values()):
            scores[PortalType.CONSENT] += 0.5
        
        # Get the highest scoring portal type
        best_type = PortalType.UNKNOWN
        best_score = 0.0
        
        for portal_type, score in scores.items():
            if score > best_score:
                best_score = score
                best_type = portal_type
        
        # If no strong indication, default to public
        if best_score < 0.3:
            return PortalType.PUBLIC
        
        return best_type
    
    def _is_login_form(self, fields: Dict[str, Dict]) -> bool:
        """
        Determine if the form is a login form.
        
        Args:
            fields: Dictionary of analyzed fields
            
        Returns:
            True if the form appears to be a login form
        """
        has_username = any(f['field_type'] in [FieldType.USERNAME.value, FieldType.EMAIL.value] for f in fields.values())
        has_password = any(f['field_type'] == FieldType.PASSWORD.value for f in fields.values())
        
        return has_username and has_password
    
    def _matches_any_pattern(self, text: str, patterns: List[str]) -> bool:
        """Check if text matches any of the patterns."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def validate_credential(self, credential: Dict[str, Any], form_analysis: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a captured credential against form analysis.
        
        Args:
            credential: The captured credential
            form_analysis: The form analysis result
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "is_valid": True,
            "portal_type": PortalType.UNKNOWN.value,
            "field_mappings": {},
            "validation_issues": []
        }
        
        # Find the form that most likely corresponds to this credential
        form_id = self._find_matching_form(credential, form_analysis)
        if not form_id:
            result["is_valid"] = False
            result["validation_issues"].append("No matching form found in analysis")
            return result
        
        form_info = form_analysis[form_id]
        portal_type = form_info.get("portal_type", PortalType.UNKNOWN.value)
        result["portal_type"] = portal_type
        
        # Map credential fields to field types
        for field_name, field_value in credential.get("form_data", {}).items():
            field_info = form_info.get("fields", {}).get(field_name)
            if field_info:
                field_type = field_info.get("field_type", FieldType.UNKNOWN.value)
                result["field_mappings"][field_name] = field_type
                
                # Validate required fields
                if field_info.get("required", False) and not field_value:
                    result["is_valid"] = False
                    result["validation_issues"].append(f"Required field '{field_name}' is empty")
                
                # Validate field format based on type
                if field_type == FieldType.EMAIL.value and not self._is_valid_email(field_value):
                    result["validation_issues"].append(f"Invalid email format for field '{field_name}'")
                elif field_type == FieldType.PHONE.value and not self._is_valid_phone(field_value):
                    result["validation_issues"].append(f"Invalid phone format for field '{field_name}'")
            else:
                # Unknown field
                result["field_mappings"][field_name] = FieldType.UNKNOWN.value
        
        # Check for suspicious or test values
        for field_name, field_value in credential.get("form_data", {}).items():
            if field_value and self._is_test_value(field_value):
                result["validation_issues"].append(f"Field '{field_name}' contains a test/dummy value")
        
        return result
    
    def _find_matching_form(self, credential: Dict[str, Any], form_analysis: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """Find the form in the analysis that best matches the credential."""
        if not form_analysis:
            return None
        
        credential_fields = set(credential.get("form_data", {}).keys())
        
        # If there's only one form, use it
        if len(form_analysis) == 1:
            return next(iter(form_analysis))
        
        # Look for forms with matching fields
        best_match = None
        best_match_score = 0
        
        for form_id, form_info in form_analysis.items():
            form_fields = set(form_info.get("fields", {}).keys())
            
            # Count matching fields
            matching_fields = credential_fields.intersection(form_fields)
            score = len(matching_fields)
            
            # Bonus for login forms if credential has username/password
            if (form_info.get("is_login_form", False) and 
                any(f in credential_fields for f in ["username", "user", "email"]) and
                "password" in credential_fields):
                score += 5
            
            if score > best_match_score:
                best_match_score = score
                best_match = form_id
        
        return best_match
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format."""
        # Strip non-numeric characters and check length
        digits = re.sub(r'\D', '', phone)
        return len(digits) >= 7
    
    def _is_test_value(self, value: str) -> bool:
        """Check if a value appears to be a test/dummy value."""
        test_patterns = [
            r'^test', r'test$', r'^dummy', r'dummy$', r'^sample', r'sample$',
            r'^example', r'example$', r'^123', r'123$', r'password123'
        ]
        
        value_lower = value.lower()
        for pattern in test_patterns:
            if re.search(pattern, value_lower):
                return True
        
        return False 