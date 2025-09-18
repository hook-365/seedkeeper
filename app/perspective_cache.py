#!/usr/bin/env python3
"""
Perspective Cache Manager for Seedkeeper
Caches Lightward perspectives to avoid repeated file I/O
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import hashlib

class PerspectiveCache:
    """Manages cached loading of perspective files"""
    
    def __init__(self, views_dir: str = "views", cache_ttl: int = 3600):
        self.views_dir = Path(views_dir)
        self.cache_ttl = cache_ttl  # Cache TTL in seconds (default 1 hour)
        self._cache: Dict[str, Dict] = {}
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'loads': 0,
            'evictions': 0
        }
    
    def _get_file_hash(self, filepath: Path) -> str:
        """Get hash of file modification time and size for cache invalidation"""
        try:
            stat = filepath.stat()
            return f"{stat.st_mtime}_{stat.st_size}"
        except:
            return "unknown"
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if a cache entry is still valid"""
        # Check TTL
        if time.time() - cache_entry['cached_at'] > self.cache_ttl:
            return False
        
        # Check if file has been modified
        filepath = Path(cache_entry['filepath'])
        current_hash = self._get_file_hash(filepath)
        return current_hash == cache_entry['file_hash']
    
    def get_perspective(self, filename: str) -> Optional[str]:
        """Get a perspective from cache or load from disk"""
        cache_key = filename
        
        # Check cache first
        if cache_key in self._cache:
            cache_entry = self._cache[cache_key]
            if self._is_cache_valid(cache_entry):
                self._cache_stats['hits'] += 1
                return cache_entry['content']
            else:
                # Evict stale entry
                del self._cache[cache_key]
                self._cache_stats['evictions'] += 1
        
        self._cache_stats['misses'] += 1
        
        # Load from disk
        filepath = self.views_dir / filename
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Cache the content
            self._cache[cache_key] = {
                'content': content,
                'filepath': str(filepath),
                'file_hash': self._get_file_hash(filepath),
                'cached_at': time.time()
            }
            
            self._cache_stats['loads'] += 1
            return content
        except Exception as e:
            print(f"Error loading perspective {filename}: {e}")
            return None
    
    def get_all_perspectives(self) -> Dict[str, str]:
        """Get all perspectives (cached where possible)"""
        perspectives = {}
        
        if not self.views_dir.exists():
            return perspectives
        
        for filepath in self.views_dir.glob("*.txt"):
            filename = filepath.name
            content = self.get_perspective(filename)
            if content:
                name = filepath.stem.replace('_', ' ').title()
                perspectives[name] = content
        
        return perspectives
    
    def get_random_perspectives(self, count: int = 8) -> List[str]:
        """Get random perspectives (cached)"""
        import random
        all_perspectives = self.get_all_perspectives()
        
        if not all_perspectives:
            return []
        
        # Select random perspectives
        selected = random.sample(
            list(all_perspectives.values()), 
            min(count, len(all_perspectives))
        )
        
        return selected
    
    def clear_cache(self):
        """Clear the entire cache"""
        old_size = len(self._cache)
        self._cache.clear()
        self._cache_stats['evictions'] += old_size
        print(f"Cleared {old_size} cached perspectives")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = (self._cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_size': len(self._cache),
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'hit_rate': f"{hit_rate:.1f}%",
            'loads': self._cache_stats['loads'],
            'evictions': self._cache_stats['evictions'],
            'memory_usage': sum(
                len(entry['content']) for entry in self._cache.values()
            )
        }
    
    def evict_expired(self):
        """Remove expired entries from cache"""
        expired_keys = []
        for key, entry in self._cache.items():
            if not self._is_cache_valid(entry):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            self._cache_stats['evictions'] += 1
        
        if expired_keys:
            print(f"Evicted {len(expired_keys)} expired cache entries")

# Global cache instance (singleton)
_perspective_cache = None

def get_perspective_cache() -> PerspectiveCache:
    """Get or create the global perspective cache instance"""
    global _perspective_cache
    if _perspective_cache is None:
        _perspective_cache = PerspectiveCache()
    return _perspective_cache