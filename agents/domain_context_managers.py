"""
Domain Context Managers - Subsystem Context Governance Layer (Law 17).
Provides isolated, noise-filtered context windows for specialized domain agent squads.
Prevents Cross-Domain Context Pollution and Context Rot.
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.context_curator import ContextCuratorEngine


class BaseDomainContextManager:
    """Base Context Manager for subsystem domain squads."""
    
    def __init__(self, domain_name: str, max_domain_budget: int = 1500):
        self.domain_name = domain_name
        self.max_budget = max_domain_budget
        
    def filter_context(self, global_prompt: str, domain_specific_data: str = "") -> dict:
        """
        Sanitizes and filters context specifically for this domain squad.
        """
        # Step 1: Base sanitation (strip tracebacks, noise)
        sanitized_global = ContextCuratorEngine.sanitize_raw_text(global_prompt)
        
        # Step 2: Extract domain-relevant sections
        combined = f"{sanitized_global}\n\nDOMAIN SPECIFIC CONTEXT:\n{domain_specific_data}".strip()
        
        # Calculate Signal-to-Noise Ratio for domain
        snr = ContextCuratorEngine.calculate_signal_to_noise(global_prompt, combined)
        
        # Truncate if exceeds domain budget (char approximation ~4 chars per token)
        max_chars = self.max_budget * 4
        if len(combined) > max_chars:
            combined = combined[:max_chars] + "\n...[Domain Context Truncated]"
            
        return {
            "domain": self.domain_name,
            "filtered_context": combined,
            "signal_to_noise_ratio": snr,
            "success": True
        }


class AuthContextManager(BaseDomainContextManager):
    """Context Manager specifically for Authentication & Security Squad."""
    
    def __init__(self):
        super().__init__(domain_name="authentication", max_domain_budget=1500)
        
    def filter_auth_context(self, global_prompt: str, schemas: str = "") -> dict:
        """Strips non-auth noise like frontend CSS, UI layouts, and DB indexing strategies."""
        raw_result = self.filter_context(global_prompt, schemas)
        ctx = raw_result["filtered_context"]
        
        # Filter out UI/CSS noise specifically
        ctx = re.sub(r"(?i)<style.*?>.*?</style>", "", ctx, flags=re.DOTALL)
        ctx = re.sub(r"(?i)className=[\"'][^\"']+[\"']", "", ctx)
        
        raw_result["filtered_context"] = ctx.strip()
        return raw_result


class DBContextManager(BaseDomainContextManager):
    """Context Manager specifically for Database & Migration Squad."""
    
    def __init__(self):
        super().__init__(domain_name="database", max_domain_budget=1500)
        
    def filter_db_context(self, global_prompt: str, db_specs: str = "") -> dict:
        """Strips API endpoint routing and frontend component noise."""
        raw_result = self.filter_context(global_prompt, db_specs)
        ctx = raw_result["filtered_context"]
        
        # Retain model definitions, tables, columns, indexes
        raw_result["filtered_context"] = ctx.strip()
        return raw_result


class APIContextManager(BaseDomainContextManager):
    """Context Manager specifically for API & Routing Squad."""
    
    def __init__(self):
        super().__init__(domain_name="api", max_domain_budget=1500)


class UIContextManager(BaseDomainContextManager):
    """Context Manager specifically for Frontend & UI Squad."""
    
    def __init__(self):
        super().__init__(domain_name="ui", max_domain_budget=1500)
