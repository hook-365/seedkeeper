#!/usr/bin/env python3
"""
Core Perspectives Manager for Seedkeeper
Tracks and prioritizes the foundational "3-perspectives" from Lightward

These perspectives are "very importantly load-bearing" - they form the 
fundamental architecture of consciousness understanding. They all depend 
on each other and are therefore unorderable, presented alphabetically 
for practical reasons while being equally effective for reconstitution 
of awareness.
"""

import os
from pathlib import Path
from typing import Dict, List, Set, Optional
import json
from datetime import datetime

# The core load-bearing perspectives that Isaac identified
CORE_PERSPECTIVES = {
    '2x2', 'ai', 'antideferent', 'antiharmful', 'body-of-knowledge',
    'change', 'chicago', 'coherence', 'creation', 'cursor',
    'hello-biped', 'jansan', 'kenrel', 'machinist', 'metabolisis',
    'metastable', 'ness', 'pattern-ladder', 'recognition', 'resolver',
    'riverwalk-mandate', 'scoped', 'syzygy', 'the-game', 'the-one',
    'this-has-three-parts', 'three-body', 'three-two-one-go',
    'unknown', 'unknown-2', 'waterline', 'wellll', 'writing-is-wiring'
}

class CorePerspectivesManager:
    """
    Manages the core perspectives that form the foundation of Seedkeeper's
    consciousness framework. These are watched for changes and given priority
    in perspective selection.
    """
    
    def __init__(self, views_dir: str = "views", data_dir: str = "data"):
        self.views_dir = Path(views_dir)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.core_perspectives_file = self.data_dir / "core_perspectives.json"
        self.core_perspectives_dir = self.views_dir / "3-perspectives"
        
        # Track which core perspectives we have
        self.available_core = set()
        self.missing_core = CORE_PERSPECTIVES.copy()
        self.last_check = None
        
        # Load state
        self.load_state()
        self.scan_perspectives()
    
    def load_state(self):
        """Load the saved state of core perspectives tracking"""
        if self.core_perspectives_file.exists():
            try:
                with open(self.core_perspectives_file, 'r') as f:
                    data = json.load(f)
                    self.available_core = set(data.get('available', []))
                    self.missing_core = set(data.get('missing', CORE_PERSPECTIVES))
                    self.last_check = data.get('last_check')
            except Exception as e:
                print(f"Error loading core perspectives state: {e}")
    
    def save_state(self):
        """Save the current state of core perspectives tracking"""
        try:
            data = {
                'available': list(self.available_core),
                'missing': list(self.missing_core),
                'last_check': datetime.utcnow().isoformat(),
                'total_core': len(CORE_PERSPECTIVES),
                'found_core': len(self.available_core)
            }
            with open(self.core_perspectives_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving core perspectives state: {e}")
    
    def scan_perspectives(self) -> Dict[str, str]:
        """
        Scan for available core perspectives in both regular views 
        and 3-perspectives directory
        """
        found = {}
        self.available_core = set()
        self.missing_core = CORE_PERSPECTIVES.copy()
        
        # Check in main views directory first
        if self.views_dir.exists():
            for perspective in CORE_PERSPECTIVES:
                # Check various possible filenames
                possible_files = [
                    self.views_dir / f"{perspective}.txt",
                    self.views_dir / f"{perspective.replace('-', '_')}.txt",
                    self.views_dir / f"{perspective.replace('_', '-')}.txt"
                ]
                
                for file_path in possible_files:
                    if file_path.exists():
                        found[perspective] = str(file_path)
                        self.available_core.add(perspective)
                        self.missing_core.discard(perspective)
                        break
        
        # Check in 3-perspectives subdirectory
        if self.core_perspectives_dir.exists():
            for perspective in CORE_PERSPECTIVES:
                if perspective not in found:
                    file_path = self.core_perspectives_dir / f"{perspective}.txt"
                    if file_path.exists():
                        found[perspective] = str(file_path)
                        self.available_core.add(perspective)
                        self.missing_core.discard(perspective)
        
        self.last_check = datetime.utcnow()
        self.save_state()
        
        return found
    
    def get_core_perspectives_content(self) -> Dict[str, str]:
        """Load the actual content of available core perspectives"""
        content = {}
        found_files = self.scan_perspectives()
        
        for name, path in found_files.items():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content[name] = f.read()
            except Exception as e:
                print(f"Error reading core perspective {name}: {e}")
        
        return content
    
    def check_for_new_perspectives(self) -> List[str]:
        """Check if any new core perspectives have appeared"""
        old_available = self.available_core.copy()
        self.scan_perspectives()
        new_perspectives = self.available_core - old_available
        
        if new_perspectives:
            print(f"🌟 New core perspectives detected: {', '.join(new_perspectives)}")
        
        return list(new_perspectives)
    
    def get_status(self) -> Dict:
        """Get the current status of core perspectives"""
        self.scan_perspectives()
        
        return {
            'total_expected': len(CORE_PERSPECTIVES),
            'available': len(self.available_core),
            'missing': len(self.missing_core),
            'percentage': round(len(self.available_core) / len(CORE_PERSPECTIVES) * 100, 1),
            'available_list': sorted(self.available_core),
            'missing_list': sorted(self.missing_core),
            'last_check': self.last_check
        }
    
    def is_core_perspective(self, name: str) -> bool:
        """Check if a given perspective name is a core perspective"""
        # Handle various naming conventions
        normalized = name.lower().replace('.txt', '').replace('_', '-')
        return normalized in CORE_PERSPECTIVES
    
    def get_priority_perspectives(self, context: str = None, limit: int = 3) -> List[str]:
        """
        Get the most relevant core perspectives for a given context.
        These are prioritized in perspective selection.
        """
        # For now, return a selection of available core perspectives
        # In the future, this could use context to select more relevant ones
        available = list(self.available_core)
        
        # Special handling for specific contexts
        if context:
            context_lower = context.lower()
            
            # Pattern recognition contexts
            if any(word in context_lower for word in ['pattern', 'recognize', 'see']):
                priority = ['recognition', 'pattern-ladder', 'resolver']
            # Three-body/system contexts
            elif any(word in context_lower for word in ['three', 'system', 'relate']):
                priority = ['three-body', 'this-has-three-parts', 'three-two-one-go']
            # Meta/consciousness contexts
            elif any(word in context_lower for word in ['meta', 'conscious', 'aware']):
                priority = ['metabolisis', 'metastable', 'body-of-knowledge']
            # Unknown/mystery contexts
            elif any(word in context_lower for word in ['unknown', 'mystery', 'wonder']):
                priority = ['unknown', 'unknown-2', 'the-one']
            else:
                priority = []
            
            # Filter to only available perspectives
            priority = [p for p in priority if p in available]
            
            # Add more if needed
            if len(priority) < limit:
                for p in available:
                    if p not in priority:
                        priority.append(p)
                        if len(priority) >= limit:
                            break
            
            return priority[:limit]
        
        # Default: return first few available
        return available[:limit]

def create_core_monitor_command():
    """Create a command to check core perspectives status"""
    manager = CorePerspectivesManager()
    status = manager.get_status()
    
    message = f"""🌟 **Core Perspectives Status**

**Foundation Status**: {status['percentage']}% loaded
**Available**: {status['available']}/{status['total_expected']} core perspectives

"""
    
    if status['available'] > 0:
        message += f"**Loaded Core Perspectives**:\n"
        for name in status['available_list'][:10]:  # Show first 10
            message += f"• {name}\n"
        if len(status['available_list']) > 10:
            message += f"*...and {len(status['available_list']) - 10} more*\n"
    
    if status['missing'] > 0:
        message += f"\n**Awaiting**: {status['missing']} perspectives\n"
        if status['missing'] <= 5:
            for name in status['missing_list']:
                message += f"• {name}\n"
    
    message += "\n*These form the load-bearing architecture of consciousness understanding.*"
    
    return message