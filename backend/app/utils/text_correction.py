"""
Text correction utilities for handling spelling mistakes and typos
Uses fuzzy matching to correct common errors without external dependencies
"""

import re
from difflib import get_close_matches
from typing import Dict, Set


class TextCorrector:
    """
    Lightweight spell checker for query correction
    Uses a common word dictionary and fuzzy matching
    """
    
    # Common words in question/pricing queries
    COMMON_WORDS = {
        # Question words
        "what", "where", "when", "why", "how", "who", "which", "whose", "whom",
        # Common verbs
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "can", "could", "should", "would", "will", "shall",
        "may", "might", "must", "tell", "show", "explain", "find", "get", "give",
        # Pricing/business terms
        "price", "cost", "pricing", "costs", "plan", "plans", "account", "accounts",
        "subscription", "subscriptions", "tier", "tiers", "fee", "fees", "charge",
        "pay", "payment", "monthly", "annual", "yearly", "free", "premium", "pro",
        "basic", "standard", "enterprise", "team", "personal", "professional",
        "dollar", "dollars", "euro", "pound", "money", "amount", "rate",
        # Page/content terms
        "page", "site", "website", "document", "article", "content", "text",
        "section", "information", "info", "details", "description",
        # Common adjectives/adverbs
        "this", "that", "these", "those", "the", "a", "an", "my", "your", "their",
        "our", "his", "her", "its", "some", "any", "all", "each", "every",
        "many", "much", "more", "most", "few", "several", "about", "around",
        # Prepositions
        "of", "to", "for", "in", "on", "at", "by", "with", "from", "between",
        "among", "about", "against", "during", "without", "within",
    }
    
    def __init__(self):
        self.word_cache: Dict[str, str] = {}
    
    def correct_word(self, word: str, cutoff: float = 0.75) -> str:
        """
        Correct a single word using fuzzy matching
        
        Args:
            word: The word to correct
            cutoff: Similarity threshold (0-1), higher = stricter
        
        Returns:
            Corrected word or original if no match found
        """
        word_lower = word.lower()
        
        # Already correct
        if word_lower in self.COMMON_WORDS:
            return word
        
        # Check cache
        if word_lower in self.word_cache:
            return self.word_cache[word_lower]
        
        # Find close matches
        matches = get_close_matches(
            word_lower, 
            self.COMMON_WORDS, 
            n=1, 
            cutoff=cutoff
        )
        
        if matches:
            corrected = matches[0]
            # Preserve original capitalization pattern
            if word[0].isupper():
                corrected = corrected.capitalize()
            self.word_cache[word_lower] = corrected
            return corrected
        
        return word
    
    def correct_text(self, text: str, cutoff: float = 0.75) -> tuple[str, bool]:
        """
        Correct spelling errors in text while preserving structure
        
        Args:
            text: The text to correct
            cutoff: Similarity threshold for fuzzy matching
        
        Returns:
            Tuple of (corrected_text, was_corrected)
        """
        # Split into words while preserving punctuation and spacing
        words = re.findall(r'\b\w+\b|[^\w\s]', text)
        
        corrected_words = []
        was_corrected = False
        
        for word in words:
            if re.match(r'\w+', word):  # Only correct actual words
                corrected = self.correct_word(word, cutoff)
                if corrected != word:
                    was_corrected = True
                corrected_words.append(corrected)
            else:
                corrected_words.append(word)
        
        # Reconstruct text with proper spacing
        result = []
        for i, word in enumerate(corrected_words):
            if re.match(r'[^\w\s]', word):  # Punctuation
                result.append(word)
            elif i == 0:
                result.append(word)
            else:
                result.append(' ' + word)
        
        return ''.join(result), was_corrected


# Global instance for reuse
_corrector = None

def get_corrector() -> TextCorrector:
    """Get or create global TextCorrector instance"""
    global _corrector
    if _corrector is None:
        _corrector = TextCorrector()
    return _corrector


def correct_query(query: str, cutoff: float = 0.75) -> tuple[str, bool]:
    """
    Correct spelling errors in a user query
    
    Args:
        query: User's query text
        cutoff: Similarity threshold (0.75 = 75% similarity required)
    
    Returns:
        Tuple of (corrected_query, was_corrected)
    
    Example:
        >>> correct_query("what is the prise of pro accont")
        ("what is the price of pro account", True)
    """
    return get_corrector().correct_text(query, cutoff)
