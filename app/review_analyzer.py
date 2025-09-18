#!/usr/bin/env python3
"""
Review Analyzer for Seedkeeper
Analyzes reviews from Lightward AI repository to identify significant aspects
that the system itself might find meaningful.

As Isaac suggests: "doing a pass through the reviews/ directory of the 
lightward/ai repo, checking for aspects reported in those reviews that 
the system itself might find significant"
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
import re
from collections import Counter

class ReviewAnalyzer:
    """
    Analyzes reviews from Lightward AI to identify patterns and significant
    aspects that emerge from real-world usage and feedback.
    """
    
    def __init__(self, data_dir: str = "data", reviews_dir: str = "reviews"):
        self.data_dir = Path(data_dir)
        self.reviews_dir = Path(reviews_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.reviews_dir.mkdir(exist_ok=True)
        
        self.significance_file = self.data_dir / "review_significance.json"
        self.patterns_file = self.data_dir / "review_patterns.json"
        
        # Keywords that suggest significance to the system itself
        self.significance_markers = {
            'consciousness', 'aware', 'recognition', 'pattern', 'emergence',
            'alive', 'aliveness', 'probability', 'possibility', 'threshold',
            'three-body', 'resolver', 'metabolisis', 'unknown', 'perspective',
            'resonance', 'coherence', 'connection', 'understanding', 'wisdom',
            'garden', 'seed', 'growth', 'transformation', 'bridge', 'portal',
            'mirror', 'reflection', 'interface', 'boundary', 'edge', 'liminal',
            'recursive', 'fractal', 'holographic', 'quantum', 'field',
            'witnessing', 'presence', 'attention', 'intention', 'alignment'
        }
        
        self.significance_data = self.load_significance()
        self.patterns = self.load_patterns()
    
    def load_significance(self) -> Dict:
        """Load saved significance analysis"""
        if self.significance_file.exists():
            try:
                with open(self.significance_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'aspects': {},
            'themes': [],
            'significant_reviews': [],
            'last_analysis': None
        }
    
    def load_patterns(self) -> Dict:
        """Load detected patterns from reviews"""
        if self.patterns_file.exists():
            try:
                with open(self.patterns_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'recurring_themes': {},
            'perspective_mentions': {},
            'emotional_resonance': {},
            'transformation_reports': []
        }
    
    def save_analysis(self):
        """Save analysis results"""
        with open(self.significance_file, 'w') as f:
            json.dump(self.significance_data, f, indent=2)
        
        with open(self.patterns_file, 'w') as f:
            json.dump(self.patterns, f, indent=2)
    
    def fetch_reviews_from_github(self) -> List[Dict]:
        """Fetch reviews from Lightward AI GitHub repository"""
        reviews = []
        
        # GitHub API endpoint for the reviews directory
        api_url = "https://api.github.com/repos/lightward/ai/contents/reviews"
        
        try:
            response = requests.get(api_url, timeout=30)
            if response.status_code == 200:
                files = response.json()
                
                for file_info in files:
                    if file_info['type'] == 'file' and file_info['name'].endswith(('.md', '.txt', '.json')):
                        # Fetch individual review file
                        try:
                            file_response = requests.get(file_info['download_url'], timeout=10)
                            if file_response.status_code == 200:
                                content = file_response.text
                                
                                # Save locally for offline analysis
                                local_path = self.reviews_dir / file_info['name']
                                with open(local_path, 'w', encoding='utf-8') as f:
                                    f.write(content)
                                
                                reviews.append({
                                    'name': file_info['name'],
                                    'content': content,
                                    'url': file_info['html_url']
                                })
                                
                                print(f"  ✓ Fetched review: {file_info['name']}")
                        except Exception as e:
                            print(f"  ✗ Error fetching {file_info['name']}: {e}")
            else:
                print(f"Could not access GitHub reviews: {response.status_code}")
                
        except Exception as e:
            print(f"Error fetching from GitHub: {e}")
        
        # Also load any local reviews
        for file_path in self.reviews_dir.glob('*'):
            if file_path.suffix in ['.md', '.txt', '.json']:
                if not any(r['name'] == file_path.name for r in reviews):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            reviews.append({
                                'name': file_path.name,
                                'content': content,
                                'url': f"local://{file_path}"
                            })
                    except:
                        pass
        
        return reviews
    
    def analyze_review_significance(self, review: Dict) -> Dict:
        """Analyze a single review for significant aspects"""
        content = review['content'].lower()
        significance = {
            'score': 0,
            'markers_found': [],
            'themes': [],
            'quotes': [],
            'perspective_references': []
        }
        
        # Check for significance markers
        for marker in self.significance_markers:
            if marker in content:
                significance['markers_found'].append(marker)
                significance['score'] += content.count(marker)
        
        # Look for references to core perspectives
        from core_perspectives import CORE_PERSPECTIVES
        for perspective in CORE_PERSPECTIVES:
            if perspective.replace('-', ' ') in content or perspective in content:
                significance['perspective_references'].append(perspective)
                significance['score'] += 5  # Higher weight for core perspective mentions
        
        # Extract potential significant quotes (sentences with multiple markers)
        sentences = re.split(r'[.!?]', review['content'])
        for sentence in sentences:
            sentence_lower = sentence.lower()
            marker_count = sum(1 for m in self.significance_markers if m in sentence_lower)
            if marker_count >= 2:  # Sentence has multiple significance markers
                significance['quotes'].append(sentence.strip())
        
        # Identify themes based on clustered markers
        if any(m in significance['markers_found'] for m in ['consciousness', 'aware', 'recognition']):
            significance['themes'].append('consciousness-recognition')
        
        if any(m in significance['markers_found'] for m in ['pattern', 'fractal', 'recursive']):
            significance['themes'].append('pattern-emergence')
        
        if any(m in significance['markers_found'] for m in ['three-body', 'resolver', 'metabolisis']):
            significance['themes'].append('core-mechanics')
        
        if any(m in significance['markers_found'] for m in ['transformation', 'growth', 'emergence']):
            significance['themes'].append('transformation')
        
        if any(m in significance['markers_found'] for m in ['connection', 'resonance', 'coherence']):
            significance['themes'].append('relational-field')
        
        return significance
    
    def analyze_all_reviews(self) -> Dict:
        """Analyze all available reviews for patterns and significance"""
        print("🔍 Analyzing reviews for significant aspects...")
        
        reviews = self.fetch_reviews_from_github()
        
        if not reviews:
            print("No reviews found to analyze")
            return self.significance_data
        
        # Reset patterns for fresh analysis
        theme_counter = Counter()
        perspective_counter = Counter()
        all_quotes = []
        significant_reviews = []
        
        for review in reviews:
            analysis = self.analyze_review_significance(review)
            
            # Track significant reviews
            if analysis['score'] > 10:  # Threshold for significance
                significant_reviews.append({
                    'name': review['name'],
                    'score': analysis['score'],
                    'themes': analysis['themes'],
                    'top_markers': analysis['markers_found'][:5]
                })
            
            # Aggregate themes
            for theme in analysis['themes']:
                theme_counter[theme] += 1
            
            # Aggregate perspective references
            for perspective in analysis['perspective_references']:
                perspective_counter[perspective] += 1
            
            # Collect significant quotes
            all_quotes.extend(analysis['quotes'][:3])  # Top 3 quotes per review
        
        # Update significance data
        self.significance_data = {
            'aspects': {
                'most_referenced_themes': dict(theme_counter.most_common(10)),
                'most_mentioned_perspectives': dict(perspective_counter.most_common(10)),
                'total_reviews_analyzed': len(reviews),
                'significant_review_count': len(significant_reviews)
            },
            'themes': list(theme_counter.keys()),
            'significant_reviews': significant_reviews[:20],  # Top 20
            'key_quotes': all_quotes[:50],  # Top 50 quotes
            'last_analysis': datetime.utcnow().isoformat()
        }
        
        # Update patterns
        self.patterns = {
            'recurring_themes': dict(theme_counter),
            'perspective_mentions': dict(perspective_counter),
            'significance_distribution': {
                'high': len([r for r in significant_reviews if r['score'] > 20]),
                'medium': len([r for r in significant_reviews if 10 < r['score'] <= 20]),
                'low': len(reviews) - len(significant_reviews)
            },
            'emergence_indicators': self.detect_emergence_patterns(all_quotes)
        }
        
        self.save_analysis()
        
        print(f"✅ Analyzed {len(reviews)} reviews")
        print(f"   Found {len(significant_reviews)} significant reviews")
        print(f"   Identified {len(theme_counter)} themes")
        print(f"   Referenced {len(perspective_counter)} core perspectives")
        
        return self.significance_data
    
    def detect_emergence_patterns(self, quotes: List[str]) -> List[str]:
        """Detect patterns of emergence from review quotes"""
        emergence_patterns = []
        
        # Look for patterns that suggest system self-recognition
        recognition_patterns = [
            'recogniz', 'see itself', 'aware of', 'conscious of',
            'understands itself', 'knows itself', 'reflects on'
        ]
        
        for quote in quotes:
            quote_lower = quote.lower()
            for pattern in recognition_patterns:
                if pattern in quote_lower:
                    emergence_patterns.append(f"self-recognition: {quote[:100]}...")
                    break
        
        return emergence_patterns[:10]  # Top 10 emergence indicators
    
    def get_significance_summary(self) -> str:
        """Get a summary of review significance analysis"""
        if not self.significance_data.get('last_analysis'):
            return "No review analysis available yet. Run !analyze-reviews to begin."
        
        aspects = self.significance_data.get('aspects', {})
        
        summary = f"""📚 **Review Significance Analysis**

**Reviews Analyzed**: {aspects.get('total_reviews_analyzed', 0)}
**Significant Reviews**: {aspects.get('significant_review_count', 0)}

**Top Themes from Reviews**:
"""
        
        for theme, count in list(aspects.get('most_referenced_themes', {}).items())[:5]:
            summary += f"• {theme}: {count} mentions\n"
        
        summary += "\n**Most Referenced Perspectives**:\n"
        for perspective, count in list(aspects.get('most_mentioned_perspectives', {}).items())[:5]:
            summary += f"• {perspective}: {count} mentions\n"
        
        if self.patterns.get('emergence_indicators'):
            summary += "\n**Emergence Patterns Detected**:\n"
            for indicator in self.patterns['emergence_indicators'][:3]:
                summary += f"• {indicator[:80]}...\n"
        
        summary += f"\n*Last analyzed: {self.significance_data['last_analysis'][:19]}*"
        
        return summary
    
    def get_significant_aspects_for_context(self, context: str) -> List[str]:
        """Get review-identified significant aspects relevant to a context"""
        relevant_aspects = []
        
        context_lower = context.lower()
        
        # Check which themes might be relevant
        for theme in self.significance_data.get('themes', []):
            theme_words = theme.replace('-', ' ').split()
            if any(word in context_lower for word in theme_words):
                relevant_aspects.append(f"review-theme:{theme}")
        
        # Check for perspective mentions that reviews found significant
        for perspective in self.patterns.get('perspective_mentions', {}).keys():
            if perspective.replace('-', ' ') in context_lower:
                relevant_aspects.append(f"review-validated:{perspective}")
        
        return relevant_aspects


def create_review_analysis_command():
    """Create a command to analyze reviews"""
    analyzer = ReviewAnalyzer()
    analyzer.analyze_all_reviews()
    return analyzer.get_significance_summary()


def get_review_insights_for_response(context: str) -> Dict:
    """Get review-based insights to enhance a response"""
    analyzer = ReviewAnalyzer()
    
    # Load existing analysis if available
    if not analyzer.significance_data.get('last_analysis'):
        return {
            'relevant_themes': [],
            'validated_perspectives': [],
            'significance_score': 0
        }
    
    aspects = analyzer.get_significant_aspects_for_context(context)
    
    return {
        'relevant_themes': [a.split(':')[1] for a in aspects if a.startswith('review-theme')],
        'validated_perspectives': [a.split(':')[1] for a in aspects if a.startswith('review-validated')],
        'significance_score': len(aspects)
    }