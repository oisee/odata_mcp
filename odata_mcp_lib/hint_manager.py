"""
Hint manager for providing service-specific guidance and workarounds.

This module implements a flexible hint system that can provide contextual
guidance for known OData service issues and best practices.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field


@dataclass
class FieldHint:
    """Hint information for a specific field."""
    type: Optional[str] = None
    format: Optional[str] = None
    example: Optional[str] = None
    description: Optional[str] = None
    required: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class EntityHint:
    """Hint information for a specific entity."""
    description: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    navigation_paths: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding empty values."""
        result = {}
        if self.description:
            result['description'] = self.description
        if self.notes:
            result['notes'] = self.notes
        if self.examples:
            result['examples'] = self.examples
        if self.navigation_paths:
            result['navigation_paths'] = self.navigation_paths
        return result


@dataclass
class FunctionHint:
    """Hint information for a specific function."""
    description: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding empty values."""
        result = {}
        if self.description:
            result['description'] = self.description
        if self.parameters:
            result['parameters'] = self.parameters
        if self.examples:
            result['examples'] = self.examples
        return result


@dataclass
class Example:
    """Example usage with description."""
    description: str
    query: str
    note: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {'description': self.description, 'query': self.query}
        if self.note:
            result['note'] = self.note
        return result


@dataclass
class ServiceHint:
    """Complete hint information for a service."""
    pattern: str
    priority: int = 0
    service_type: Optional[str] = None
    known_issues: List[str] = field(default_factory=list)
    workarounds: List[str] = field(default_factory=list)
    field_hints: Dict[str, FieldHint] = field(default_factory=dict)
    entity_hints: Dict[str, EntityHint] = field(default_factory=dict)
    function_hints: Dict[str, FunctionHint] = field(default_factory=dict)
    examples: List[Example] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServiceHint':
        """Create ServiceHint from dictionary."""
        hint = cls(
            pattern=data.get('pattern', ''),
            priority=data.get('priority', 0),
            service_type=data.get('service_type'),
            known_issues=data.get('known_issues', []),
            workarounds=data.get('workarounds', []),
            notes=data.get('notes', [])
        )
        
        # Parse field hints
        for field_name, field_data in data.get('field_hints', {}).items():
            if isinstance(field_data, dict):
                hint.field_hints[field_name] = FieldHint(**field_data)
        
        # Parse entity hints
        for entity_name, entity_data in data.get('entity_hints', {}).items():
            if isinstance(entity_data, dict):
                hint.entity_hints[entity_name] = EntityHint(**entity_data)
        
        # Parse function hints
        for func_name, func_data in data.get('function_hints', {}).items():
            if isinstance(func_data, dict):
                hint.function_hints[func_name] = FunctionHint(**func_data)
        
        # Parse examples
        for example_data in data.get('examples', []):
            if isinstance(example_data, dict):
                hint.examples.append(Example(**example_data))
        
        return hint
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'pattern': self.pattern,
            'priority': self.priority
        }
        
        if self.service_type:
            result['service_type'] = self.service_type
        if self.known_issues:
            result['known_issues'] = self.known_issues
        if self.workarounds:
            result['workarounds'] = self.workarounds
        if self.field_hints:
            result['field_hints'] = {k: v.to_dict() for k, v in self.field_hints.items()}
        if self.entity_hints:
            result['entity_hints'] = {k: v.to_dict() for k, v in self.entity_hints.items()}
        if self.function_hints:
            result['function_hints'] = {k: v.to_dict() for k, v in self.function_hints.items()}
        if self.examples:
            result['examples'] = [e.to_dict() for e in self.examples]
        if self.notes:
            result['notes'] = self.notes
            
        return result


class HintManager:
    """Manages service hints for OData services."""
    
    def __init__(self, verbose: bool = False):
        """Initialize the hint manager."""
        self.verbose = verbose
        self.hints: List[ServiceHint] = []
        self.cli_hint: Optional[ServiceHint] = None
        self.hints_file: Optional[str] = None
    
    def _log_verbose(self, message: str):
        """Log verbose message."""
        if self.verbose:
            print(f"[HintManager] {message}", file=sys.stderr)
    
    def load_from_file(self, hints_file: Optional[str] = None) -> bool:
        """Load hints from a JSON file.
        
        Args:
            hints_file: Path to hints file. If None, searches default locations.
            
        Returns:
            True if hints were loaded successfully, False otherwise.
        """
        # Determine file path
        if hints_file:
            paths_to_try = [Path(hints_file)]
        else:
            # Default search locations
            # 1. Same directory as the main script
            script_dir = Path(sys.argv[0]).parent if sys.argv else Path.cwd()
            # 2. Current working directory
            cwd = Path.cwd()
            
            paths_to_try = [
                script_dir / "hints.json",
                cwd / "hints.json"
            ]
        
        # Try each path
        for path in paths_to_try:
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Parse hints
                    self.hints = []
                    for hint_data in data.get('hints', []):
                        try:
                            hint = ServiceHint.from_dict(hint_data)
                            self.hints.append(hint)
                        except Exception as e:
                            self._log_verbose(f"Failed to parse hint: {e}")
                    
                    self.hints_file = str(path)
                    self._log_verbose(f"Loaded {len(self.hints)} hints from {path}")
                    return True
                    
                except Exception as e:
                    self._log_verbose(f"Failed to load hints from {path}: {e}")
        
        self._log_verbose("No hints file found in default locations")
        return False
    
    def set_cli_hint(self, hint_str: str) -> bool:
        """Set a hint directly from CLI.
        
        Args:
            hint_str: JSON string or plain text hint.
            
        Returns:
            True if hint was set successfully, False otherwise.
        """
        try:
            # Try to parse as JSON
            hint_data = json.loads(hint_str)
            if isinstance(hint_data, dict):
                # Add high priority and wildcard pattern if not specified
                if 'priority' not in hint_data:
                    hint_data['priority'] = 1000
                if 'pattern' not in hint_data:
                    hint_data['pattern'] = '*'
                    
                self.cli_hint = ServiceHint.from_dict(hint_data)
                self._log_verbose("Parsed CLI hint as JSON")
                return True
                
        except json.JSONDecodeError:
            # Fall back to simple text hint
            self.cli_hint = ServiceHint(
                pattern='*',
                priority=1000,
                notes=[hint_str]
            )
            self._log_verbose("Parsed CLI hint as plain text")
            return True
        
        except Exception as e:
            self._log_verbose(f"Failed to parse CLI hint: {e}")
            return False
    
    def matches_pattern(self, pattern: str, url: str) -> bool:
        """Check if a URL matches a pattern with wildcard support.
        
        Args:
            pattern: Pattern with optional wildcards (* and ?)
            url: URL to match against
            
        Returns:
            True if URL matches pattern, False otherwise.
        """
        # Convert wildcard pattern to regex
        # Escape special regex characters except * and ?
        regex_pattern = re.escape(pattern)
        # Replace escaped wildcards with regex equivalents
        regex_pattern = regex_pattern.replace(r'\*', '.*')
        regex_pattern = regex_pattern.replace(r'\?', '.')
        
        # If pattern doesn't start with *, anchor to beginning
        if not pattern.startswith('*'):
            regex_pattern = '^' + regex_pattern
        
        # If pattern doesn't end with *, anchor to end
        if not pattern.endswith('*'):
            regex_pattern = regex_pattern + '$'
        
        try:
            return bool(re.match(regex_pattern, url, re.IGNORECASE))
        except Exception:
            return False
    
    def get_hints(self, service_url: str) -> Optional[Dict[str, Any]]:
        """Get combined hints for a service URL.
        
        Args:
            service_url: The OData service URL
            
        Returns:
            Combined hint dictionary or None if no hints match.
        """
        # Find all matching hints
        matching_hints = []
        
        # Check loaded hints
        for hint in self.hints:
            if self.matches_pattern(hint.pattern, service_url):
                matching_hints.append(hint)
        
        # Add CLI hint if present
        if self.cli_hint:
            matching_hints.append(self.cli_hint)
        
        if not matching_hints:
            return None
        
        # Sort by priority (higher first)
        matching_hints.sort(key=lambda h: h.priority, reverse=True)
        
        # Merge hints from lowest to highest priority
        merged = self._merge_hints(matching_hints)
        
        # Add source information
        result = merged.to_dict()
        sources = []
        if self.cli_hint in matching_hints:
            sources.append("CLI")
        if self.hints_file and any(h in self.hints for h in matching_hints):
            sources.append(f"file: {self.hints_file}")
        
        result['hint_source'] = ', '.join(sources) if sources else 'unknown'
        
        return result
    
    def _merge_hints(self, hints: List[ServiceHint]) -> ServiceHint:
        """Merge multiple hints into one, with higher priority overriding.
        
        Args:
            hints: List of hints sorted by priority (highest first)
            
        Returns:
            Merged ServiceHint
        """
        if not hints:
            return ServiceHint(pattern='*')
        
        # Start with the highest priority hint
        merged = ServiceHint(
            pattern=hints[0].pattern,
            priority=hints[0].priority,
            service_type=hints[0].service_type
        )
        
        # Merge in reverse order (lowest to highest priority)
        for hint in reversed(hints):
            # Merge string fields (higher priority overrides)
            if hint.service_type:
                merged.service_type = hint.service_type
            
            # Merge lists (combine unique values)
            merged.known_issues = self._merge_lists(merged.known_issues, hint.known_issues)
            merged.workarounds = self._merge_lists(merged.workarounds, hint.workarounds)
            merged.notes = self._merge_lists(merged.notes, hint.notes)
            
            # Merge dictionaries (higher priority overrides)
            merged.field_hints.update(hint.field_hints)
            merged.entity_hints.update(hint.entity_hints)
            merged.function_hints.update(hint.function_hints)
            
            # Merge examples (combine all)
            merged.examples.extend(hint.examples)
        
        return merged
    
    def _merge_lists(self, list1: List[str], list2: List[str]) -> List[str]:
        """Merge two lists, preserving unique values and order."""
        seen = set()
        result = []
        for item in list1 + list2:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result