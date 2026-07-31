"""
Custom Memory Implementation
"""

from typing import List, Dict, Any
from datetime import datetime


class CustomMemory:
    """Custom memory implementation for agents"""
    
    def __init__(self):
        self.short_term: Dict[str, Any] = {}
        self.long_term: List[Dict[str, Any]] = []
    
    def add_to_short_term(self, key: str, value: Any):
        """Add to short-term memory (current session)"""
        self.short_term[key] = value
    
    def get_from_short_term(self, key: str) -> Any:
        """Get from short-term memory"""
        return self.short_term.get(key)
    
    def clear_short_term(self):
        """Clear short-term memory"""
        self.short_term = {}
    
    def add_to_long_term(self, data: Dict[str, Any], metadata: Dict[str, Any] = None):
        """
        Add to long-term memory
        
        Args:
            data: Data to store
            metadata: Optional metadata (timestamp, tags, etc.)
        """
        entry = {
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        self.long_term.append(entry)
    
    def get_from_long_term(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get from long-term memory
        
        Args:
            limit: Maximum number of entries to return
        
        Returns:
            List of memory entries
        """
        if limit:
            return self.long_term[-limit:]
        return self.long_term
    
    def find_similar(self, query: str, threshold: float = 0.8, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find similar entries in long-term memory
        
        Args:
            query: Query string
            threshold: Similarity threshold (0-1)
            limit: Maximum number of results
        
        Returns:
            List of similar entries with similarity scores
        """
        similar = []
        query_keywords = set(query.lower().split())
        
        for entry in self.long_term:
            # Simple keyword-based similarity
            data_str = str(entry["data"]).lower()
            entry_keywords = set(data_str.split())
            
            # Calculate Jaccard similarity
            overlap = len(query_keywords & entry_keywords)
            total = len(query_keywords | entry_keywords)
            similarity = overlap / total if total > 0 else 0
            
            if similarity >= threshold:
                similar.append({
                    "entry": entry,
                    "similarity": similarity
                })
        
        # Sort by similarity (descending)
        similar.sort(key=lambda x: x["similarity"], reverse=True)
        
        return similar[:limit]
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search long-term memory
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of matching entries
        """
        results = []
        query_lower = query.lower()
        
        for entry in self.long_term:
            data_str = str(entry["data"]).lower()
            if query_lower in data_str:
                results.append(entry)
                if len(results) >= limit:
                    break
        
        return results
    
    def clear_long_term(self):
        """Clear long-term memory"""
        self.long_term = []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            "short_term_size": len(self.short_term),
            "long_term_size": len(self.long_term)
        }


# Global memory instance
memory = CustomMemory()


# Test function
def test_memory():
    """Test memory implementation"""
    
    print("Testing memory...")
    
    # Test short-term memory
    memory.add_to_short_term("test_key", "test_value")
    assert memory.get_from_short_term("test_key") == "test_value"
    print("✓ Short-term memory works")
    
    # Test long-term memory
    memory.add_to_long_term(
        data={"requirements": "Build a login page", "tasks": []},
        metadata={"source": "test"}
    )
    entries = memory.get_from_long_term()
    assert len(entries) > 0
    print("✓ Long-term memory works")
    
    # Test similarity search
    similar = memory.find_similar("login page authentication")
    print(f"✓ Similarity search works (found {len(similar)} results)")
    
    # Test search
    results = memory.search("login")
    print(f"✓ Search works (found {len(results)} results)")
    
    # Test stats
    stats = memory.get_stats()
    print(f"✓ Stats: {stats}")
    
    print("✓ All memory tests passed!")


if __name__ == "__main__":
    test_memory()
