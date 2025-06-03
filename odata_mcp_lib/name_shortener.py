"""
Advanced name shortening algorithms for OData MCP tool names.
"""

import re
from typing import List, Set, Optional, Tuple


class NameShortener:
    """Implements semantic-preserving name shortening algorithms."""
    
    # Domain-specific keyword mappings for common business terms
    # Format: 'WORD': 'Abbrev' (preserving proper casing)
    DOMAIN_KEYWORDS = {
        'SCREENING': 'Scrn',
        'ADDRESS': 'Addr',
        'INVESTIGATION': 'Inv',
        'BUSINESS': 'Biz',
        'CUSTOMER': 'Cust',
        'PRODUCT': 'Prod',
        'SERVICE': 'Svc',
        'MANAGEMENT': 'Mgmt',
        'INFORMATION': 'Info',
        'CONFIGURATION': 'Conf',
        'ADMINISTRATION': 'Admin',
        'TRANSACTION': 'Txn',
        'DOCUMENT': 'Doc',
        'FINANCIAL': 'Fin',
        'ACCOUNTING': 'Acct',
        'ORGANIZATION': 'Org',
        'RELATIONSHIP': 'Rel',
        'COMMUNICATION': 'Comm',
        'ANALYTICS': 'Anly',
        'PURCHASE': 'Purch',
        'MATERIAL': 'Matl',
        'INVENTORY': 'Inv',
        'WAREHOUSE': 'Wh',
        'DISTRIBUTION': 'Dist',
        'MANUFACTURING': 'Mfg',
    }
    
    # Low-value words to filter out
    GENERIC_SUFFIXES = {
        'Type', 'Info', 'Data', 'Set', 'Collection', 'Entity', 
        'Object', 'Item', 'Record', 'Entry', 'View', 'Model',
        'Base', 'Core', 'Root', 'Node', 'List'
    }
    
    COMMON_PREFIXES = {
        'Business', 'System', 'Object', 'Master', 'Standard',
        'Generic', 'Common', 'Basic', 'General', 'Default'
    }
    
    # Vowels to potentially remove (keeping first and last character)
    VOWELS = set('aeiouAEIOU')
    
    def __init__(self, aggressive: bool = False):
        """
        Initialize the name shortener.
        
        Args:
            aggressive: If True, apply more aggressive shortening
        """
        self.aggressive = aggressive
        self.target_length = 12 if aggressive else 20
    
    def shorten_entity_name(self, entity_name: str, target_length: Optional[int] = None) -> str:
        """
        Shorten an entity name using progressive reduction stages.
        
        Args:
            entity_name: The entity name to shorten
            target_length: Target length (uses default if None)
            
        Returns:
            Shortened entity name
        """
        if not entity_name:
            return entity_name
            
        target = target_length or self.target_length
        
        # If already short enough, return as-is
        if len(entity_name) <= target:
            return entity_name
        
        # Stage 1: Tokenization
        tokens = self._tokenize(entity_name)
        longest_token = self._get_longest_meaningful_token(tokens)
        
        if longest_token and len(longest_token) <= target:
            return longest_token
        
        # Stage 2: CamelCase decomposition
        if longest_token:
            words = self._decompose_camel_case(longest_token)
        else:
            # No meaningful token, work with all tokens
            words = []
            for token in tokens:
                words.extend(self._decompose_camel_case(token))
        
        filtered_words = self._apply_semantic_filtering(words)
        
        # Stage 3: Progressive word reduction
        result = self._progressive_word_reduction(filtered_words, target)
        
        # Stage 4: Intra-word compression if still too long
        if len(result) > target:
            result = self._compress_word(result, target)
        
        return result
    
    def _tokenize(self, name: str) -> List[str]:
        """Split name on space-like separators."""
        # Split on common separators: _, -, ., :, space
        tokens = re.split(r'[_\-.\s:]+', name)
        return [t for t in tokens if t]  # Remove empty tokens
    
    def _get_longest_meaningful_token(self, tokens: List[str]) -> Optional[str]:
        """Find the longest meaningful token (>3 chars, not purely numeric)."""
        meaningful_tokens = [
            t for t in tokens 
            if len(t) > 3 and not t.isdigit()
        ]
        
        if not meaningful_tokens:
            return None
            
        return max(meaningful_tokens, key=len)
    
    def _decompose_camel_case(self, word: str) -> List[str]:
        """Split CamelCase/PascalCase into constituent words."""
        # Handle sequences of capitals specially (e.g., 'XMLParser' -> ['XML', 'Parser'])
        # This regex finds boundaries between:
        # - lowercase to uppercase
        # - sequence of uppercase to uppercase followed by lowercase
        parts = []
        current = []
        
        for i, char in enumerate(word):
            if i == 0:
                current.append(char)
            elif char.isupper():
                # Check if this starts a new word
                if current and (current[-1].islower() or 
                               (i + 1 < len(word) and word[i + 1].islower())):
                    parts.append(''.join(current))
                    current = [char]
                else:
                    current.append(char)
            else:
                current.append(char)
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    def _apply_semantic_filtering(self, words: List[str]) -> List[str]:
        """Remove low-value words while preserving semantic meaning."""
        filtered = []
        
        for word in words:
            # Skip generic suffixes and prefixes
            if word in self.GENERIC_SUFFIXES or word in self.COMMON_PREFIXES:
                continue
            
            # Keep meaningful words
            filtered.append(word)
        
        # If we filtered everything, keep at least the first word
        if not filtered and words:
            filtered = [words[0]]
        
        return filtered
    
    def _progressive_word_reduction(self, words: List[str], target_length: int) -> str:
        """Apply progressive word reduction strategies."""
        if not words:
            return ""
        
        # Strategy 1: Keep all words if they fit
        full_name = ''.join(words)
        if len(full_name) <= target_length:
            return full_name
        
        # Strategy 2: Try using domain keyword mappings
        shortened_words = []
        for word in words:
            upper_word = word.upper()
            if upper_word in self.DOMAIN_KEYWORDS:
                shortened_words.append(self.DOMAIN_KEYWORDS[upper_word])
            else:
                shortened_words.append(word)
        
        shortened_full = ''.join(shortened_words)
        if len(shortened_full) <= target_length:
            return shortened_full
        
        # Strategy 3: Keep first N words that fit
        for n in range(len(words), 0, -1):
            combined = ''.join(words[:n])
            if len(combined) <= target_length:
                return combined
        
        # Strategy 4: Shorten the first word if needed
        first_word = words[0]
        if len(first_word) > target_length:
            # Try domain mapping first
            upper_first = first_word.upper()
            if upper_first in self.DOMAIN_KEYWORDS:
                return self.DOMAIN_KEYWORDS[upper_first][:target_length]
            # Then try vowel removal
            if len(first_word) > 3:
                compressed = self._remove_vowels(first_word)
                if len(compressed) <= target_length:
                    return compressed
            # Finally truncate
            return first_word[:target_length]
        
        return first_word
    
    def _compress_word(self, word: str, target_length: int) -> str:
        """Compress a single word using various techniques."""
        if len(word) <= target_length:
            return word
        
        # Try vowel removal first (keeping first and last character)
        if len(word) > 3:
            compressed = self._remove_vowels(word)
            if len(compressed) <= target_length and len(compressed) >= 3:
                return compressed
        
        # Fallback to truncation
        return word[:target_length]
    
    def _remove_vowels(self, word: str) -> str:
        """Remove vowels from middle of word, keeping first/last characters."""
        if len(word) <= 3:
            return word
        
        result = word[0]  # Keep first character
        
        # Remove vowels from middle
        for i in range(1, len(word) - 1):
            if word[i] not in self.VOWELS:
                result += word[i]
        
        result += word[-1]  # Keep last character
        
        return result
    
    def shorten_service_name(self, service_name: str, max_length: int = 4) -> str:
        """
        Shorten a service name for use as a postfix.
        
        Args:
            service_name: The service name to shorten
            max_length: Maximum length for the result
            
        Returns:
            Shortened service name
        """
        # Remove common suffixes like _SRV
        cleaned = re.sub(r'_SRV$', '', service_name, flags=re.IGNORECASE)
        
        # Tokenize
        tokens = self._tokenize(cleaned)
        
        # First priority: Look for domain keywords
        for token in tokens:
            upper_token = token.upper()
            if upper_token in self.DOMAIN_KEYWORDS:
                return self.DOMAIN_KEYWORDS[upper_token][:max_length].lower()
        
        # Second priority: Find the most meaningful token (avoid common prefixes)
        meaningful_tokens = []
        for token in tokens:
            # Skip common organizational prefixes
            if token.upper() not in {'BPCM', 'CV', 'ASH', 'FRA', 'IV', 'C', 'I', 'E', 'Z', 'BUSINESS', 'SYSTEM'}:
                meaningful_tokens.append(token)
        
        if meaningful_tokens:
            # Return the longest meaningful token
            best_token = max(meaningful_tokens, key=len)
            return best_token[:max_length].lower()
        
        # Fallback to the longest token
        if tokens:
            best_token = max(tokens, key=len)
            return best_token[:max_length].lower()
        
        # Ultimate fallback
        return service_name[:max_length].lower()
    
    def should_auto_shrink(self, full_name: str, threshold: int = 60) -> bool:
        """
        Determine if a name should be automatically shortened.
        
        Args:
            full_name: The complete tool name
            threshold: Length threshold for auto-shrinking
            
        Returns:
            True if the name should be shortened
        """
        return len(full_name) > threshold