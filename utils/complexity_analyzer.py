"""
Dedicated Query Complexity Analysis Module
Provides fast rule-based + LLM hybrid scoring
"""

from typing import Dict, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
import re

class ComplexityScore(BaseModel):
    score: int  # 0-100
    tier: str  # 'tier1', 'tier2', 'tier3'
    reasoning: str
    factors: list[str]


class ComplexityAnalyzer:
    """Fast complexity scoring for query routing"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Rule-based patterns
        self.simple_patterns = [
            r'\b(hi|hello|hey|good morning)\b',
            r'\b(thanks|thank you|bye)\b',
            r'\b(what is|who is|define)\b'
        ]
        
        self.complex_patterns = [
            r'\b(integrate|configure|troubleshoot|debug)\b',
            r'\b(migration|deployment|architecture)\b',
            r'\b(multiple|several|various)\b.*\b(issues|problems)\b'
        ]
    
    def analyze_fast(self, query: str) -> ComplexityScore:
        """
        Fast rule-based complexity scoring (< 10ms)
        Use for tier routing before full analysis
        """
        query_lower = query.lower()
        factors = []
        score = 30  # Base score
        
        # Length factor
        word_count = len(query.split())
        if word_count < 5:
            score -= 10
            factors.append("short_query")
        elif word_count > 20:
            score += 15
            factors.append("long_query")
        
        # Simple patterns (reduce score)
        for pattern in self.simple_patterns:
            if re.search(pattern, query_lower):
                score -= 15
                factors.append("greeting_or_simple")
                break
        
        # Complex patterns (increase score)
        for pattern in self.complex_patterns:
            if re.search(pattern, query_lower):
                score += 20
                factors.append("technical_keywords")
                break
        
        # Technical indicators
        if any(word in query_lower for word in ['api', 'sdk', 'endpoint', 'webhook', 'integration']):
            score += 15
            factors.append("technical_terms")
        
        # Question complexity
        question_words = ['how', 'why', 'explain', 'difference between']
        if any(word in query_lower for word in question_words):
            score += 10
            factors.append("complex_question")
        
        # Clamp score
        score = max(0, min(100, score))
        
        # Determine tier
        if score < 30:
            tier = 'tier1'
        elif score < 60:
            tier = 'tier2'
        else:
            tier = 'tier3'
        
        return ComplexityScore(
            score=score,
            tier=tier,
            reasoning=f"Rule-based analysis: {', '.join(factors)}",
            factors=factors
        )
    
    async def analyze_with_llm(self, query: str) -> ComplexityScore:
        """
        LLM-based complexity analysis (slower, more accurate)
        Use for tier 2/3 refinement
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Analyze query complexity on a scale of 0-100:

0-30: Simple (greetings, basic FAQs, yes/no questions)
31-60: Moderate (product inquiries, how-to questions)
61-100: Complex (technical issues, multi-step problems, escalation needed)

Consider:
- Technical terminology
- Number of sub-questions
- Domain knowledge required
- Multi-step resolution needed"""),
            ("human", "Query: {query}\n\nProvide: score (0-100), tier (tier1/tier2/tier3), reasoning")
        ])
        
        chain = prompt | self.llm.with_structured_output(ComplexityScore)
        result = await chain.ainvoke({"query": query})
        
        return result
    
    def should_escalate(self, score: int) -> Tuple[bool, str]:
        """Determine if query should escalate to higher tier"""
        if score >= 80:
            return True, "tier3"
        elif score >= 60:
            return True, "tier2"
        return False, "tier1"


# Singleton instance
complexity_analyzer = ComplexityAnalyzer()