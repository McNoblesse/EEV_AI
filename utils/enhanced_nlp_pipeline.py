import os
import re
import spacy
from typing import Dict, List, Tuple, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import sqlite3
from datetime import datetime
import json
from langchain_core.pydantic_v1 import BaseModel as LangchainBaseModel, Field as LangchainField

from config.access_keys import accessKeys

# Ensure OpenAI API key is set for the environment
os.environ["OPENAI_API_KEY"] = accessKeys.OPENAI_API_KEY

# Download spaCy model if not already installed
spacy.cli.download("en_core_web_sm")

# Load spaCy model for entity extraction
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Warning: spaCy English model not found. Install with: python -m spacy download en_core_web_sm")
    nlp = None

class ExtractedEntity(BaseModel):
    """Represents an extracted entity from user input."""
    text: str = Field(description="The actual text of the entity")
    label: str = Field(description="The entity type (PERSON, ORG, PRODUCT, etc.)")
    confidence: float = Field(description="Confidence score 0-1")
    start_pos: int = Field(description="Start position in text")
    end_pos: int = Field(description="End position in text")

class EnhancedAnalyzedQuery(BaseModel):
    """Enhanced model with comprehensive query analysis."""
    intent: str = Field(description="Primary intent classification")
    intent_confidence: float = Field(description="Confidence score for intent (0-1)")
    sub_intent: str = Field(description="More specific sub-category of intent")
    entities: List[ExtractedEntity] = Field(description="List of extracted entities")
    sentiment: str = Field(description="Sentiment analysis result")
    sentiment_score: float = Field(description="Numerical sentiment score (-1 to 1)")
    complexity_score: int = Field(description="Query complexity (1-10)")
    complexity_factors: List[str] = Field(description="Factors contributing to complexity")
    keywords: List[str] = Field(description="Key terms extracted from query")
    response: str = Field(description="Natural response to the user")
    requires_tools: bool = Field(description="Whether query needs tool assistance")
    user_type: str = Field(description="Inferred user type: technical, business, general")
    escalate: bool = Field(default=False, description="Whether the query should be escalated to a human agent")
    conversation_summary: str = Field(default="", description="Summary of the conversation for context")
    conversation_ended: bool = Field(default=False, description="Whether the conversation has been marked as ended")

class IntentAnalysisResult(LangchainBaseModel):
    """Structured output for intent classification."""
    primary_intent: str = LangchainField(description="The main category of the user's query.")
    confidence_score: float = LangchainField(description="The confidence score for the classification, from 0.0 to 1.0.")
    sub_intent: str = LangchainField(description="A more specific sub-category, or 'none' if not applicable.")
    reasoning: str = LangchainField(description="A brief explanation for the classification choice.")

class EnhancedNLPPipeline:
    """Enhanced NLP pipeline for comprehensive query analysis."""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini-2024-07-18", temperature=0.1)
        self.intent_classifier = self._setup_intent_classifier()
        self.entity_extractor = self._setup_entity_extractor()
        self.complexity_analyzer = self._setup_complexity_analyzer()
        
        # Initialize tracking database
        self._init_analytics_db()
    
    def _init_analytics_db(self):
        """Initialize SQLite database for analytics tracking."""
        conn = sqlite3.connect(accessKeys.SQLITE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                intent TEXT,
                intent_confidence REAL,
                sub_intent TEXT,
                sentiment TEXT,
                sentiment_score REAL,
                complexity_score INTEGER,
                complexity_factors TEXT,
                entities TEXT,
                keywords TEXT,
                       
                user_type TEXT,
                processing_time_ms INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _setup_intent_classifier(self):
        """Setup enhanced intent classification with detailed categories."""
        intent_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are an expert intent classifier for a customer support AI system.
            
            Classify user queries into these detailed categories with high accuracy:
            
            PRIMARY INTENTS:
            1. technical_question - Technical issues, troubleshooting, how-to guides
            2. product_inquiry - Questions about features, capabilities, pricing
            3. account_support - Account management, billing, subscriptions
            4. integration_help - API, SDK, third-party integrations
            5. general_information - Company info, policies, general knowledge
            6. greeting - Hello, hi, introductions
            7. complaint - Issues, problems, negative feedback
            8. compliment - Positive feedback, thanks, appreciation
            9. request_demo - Want to see product demonstration
            10. sales_inquiry - Pricing, purchasing, commercial questions
            
            SUB-INTENTS (for technical_question):
            - api_documentation, troubleshooting, configuration, installation, 
            - performance_issue, bug_report, feature_request
            
            SUB-INTENTS (for product_inquiry):
            - feature_comparison, pricing_info, compatibility, limitations,
            - use_cases, best_practices
            
            Analyze the user's message and return:
            1. Primary intent
            2. Confidence score (0.0 to 1.0)
            3. Sub-intent (if applicable)
            4. Reasoning for your classification
            
            Be very accurate - aim for >95% classification accuracy.
            """),
            ("human", "Classify this user message: {user_input}")
        ])
        
        return intent_prompt | self.llm.with_structured_output(IntentAnalysisResult)
    
    def _setup_entity_extractor(self):
        """Setup entity extraction system."""
        entity_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            Extract and classify entities from user messages. Focus on:
            
            ENTITY TYPES:
            - PRODUCT: Software products, services, tools mentioned
            - PERSON: Names of people, roles, titles
            - ORGANIZATION: Company names, departments
            - TECHNOLOGY: Programming languages, frameworks, APIs
            - ISSUE_TYPE: Specific problems or error types
            - VERSION: Software versions, model numbers
            - DATE_TIME: Time references, deadlines
            - LOCATION: Geographic or system locations
            - METRIC: Performance numbers, quantities
            
            For each entity, provide:
            - The exact text
            - The entity type
            - Confidence score (0.0-1.0)
            - Why this entity is important for support
            """),
            ("human", "Extract entities from: {user_input}")
        ])
        
        return entity_prompt | self.llm
    
    def _setup_complexity_analyzer(self):
        """Setup query complexity analysis."""
        complexity_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            Analyze query complexity on a scale of 1-10:
            
            COMPLEXITY FACTORS:
            1. Technical depth required
            2. Number of concepts involved
            3. Multi-step process requirements
            4. Domain expertise needed
            5. Integration complexity
            6. Troubleshooting depth
            7. Custom solution requirements
            
            SCORING GUIDE:
            1-2: Simple greetings, basic questions
            3-4: Standard product questions, common issues
            5-6: Technical questions requiring some expertise
            7-8: Complex integrations, advanced troubleshooting
            9-10: Expert-level problems, custom solutions
            
            Provide:
            - Complexity score (1-10)
            - List of factors contributing to complexity
            - Estimated resolution time category (quick/medium/complex)
            """),
            ("human", "Analyze complexity of: {user_input}")
        ])
        
        return complexity_prompt | self.llm
    
    def extract_entities_with_spacy(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using spaCy NER."""
        if not nlp:
            return []
        
        doc = nlp(text)
        entities = []
        
        for ent in doc.ents:
            entities.append(ExtractedEntity(
                text=ent.text,
                label=ent.label_,
                confidence=0.8,  # spaCy doesn't provide confidence by default
                start_pos=ent.start_char,
                end_pos=ent.end_char
            ))
        
        return entities
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text."""
        if not nlp:
            # Fallback keyword extraction
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            return list(set(words))[:10]
        
        doc = nlp(text)
        keywords = []
        
        for token in doc:
            if (not token.is_stop and 
                not token.is_punct and 
                len(token.text) > 2 and
                token.pos_ in ['NOUN', 'VERB', 'ADJ', 'PROPN']):
                keywords.append(token.lemma_.lower())
        
        return list(set(keywords))[:10]
    
    def determine_user_type(self, text: str, intent: str) -> str:
        """Determine user type based on language and intent."""
        text_lower = text.lower()
        
        technical_indicators = [
            'api', 'sdk', 'code', 'function', 'error', 'debug', 'integration',
            'endpoint', 'parameter', 'authentication', 'webhook', 'json',
            'xml', 'database', 'query', 'script', 'configuration'
        ]
        
        business_indicators = [
            'pricing', 'plan', 'subscription', 'billing', 'invoice', 'demo',
            'trial', 'enterprise', 'team', 'license', 'contract', 'roi',
            'implementation', 'onboarding', 'training'
        ]
        
        technical_score = sum(1 for word in technical_indicators if word in text_lower)
        business_score = sum(1 for word in business_indicators if word in text_lower)
        
        if technical_score >= 2 or intent in ['technical_question', 'integration_help']:
            return 'technical'
        elif business_score >= 2 or intent in ['sales_inquiry', 'request_demo']:
            return 'business'
        else:
            return 'general'
    
    def analyze_query(self, user_input: str, session_id: str) -> EnhancedAnalyzedQuery:
        """Perform comprehensive query analysis."""
        start_time = datetime.now()
        
        # Intent Classification
        try:
            # The classifier now directly returns a structured object, not text.
            intent_analysis_result: IntentAnalysisResult = self.intent_classifier.invoke({"user_input": user_input})
            intent_analysis = {
                "intent": intent_analysis_result.primary_intent,
                "confidence": intent_analysis_result.confidence_score,
                "sub_intent": intent_analysis_result.sub_intent
            }
        except Exception as e:
            print(f"Intent classification error: {e}")
            intent_analysis = {
                "intent": "general_information",
                "confidence": 0.5,
                "sub_intent": "unknown"
            }
        
        # Entity Extraction
        spacy_entities = self.extract_entities_with_spacy(user_input)
        
        try:
            llm_entity_response = self.entity_extractor.invoke({"user_input": user_input})
            content = llm_entity_response.content
            if isinstance(content, list):
                content = str(content[0]) if content else ""
            llm_entities = self._parse_entity_response(content)
        except Exception as e:
            print(f"Entity extraction error: {e}")
            llm_entities = []
        
        # Combine entities
        all_entities = spacy_entities + llm_entities
        
        # Complexity Analysis
        try:
            complexity_response = self.complexity_analyzer.invoke({"user_input": user_input})
            content = complexity_response.content
            if isinstance(content, list):
                content = str(content[0]) if content else ""
            complexity_analysis = self._parse_complexity_response(content)
        except Exception as e:
            print(f"Complexity analysis error: {e}")
            complexity_analysis = {
                "score": 5,
                "factors": ["Unable to analyze"],
                "estimated_time": "medium"
            }
        
        # Sentiment Analysis (enhanced)
        sentiment_analysis = self._analyze_sentiment(user_input)
        
        # Extract keywords
        keywords = self.extract_keywords(user_input)
        
        # Determine user type
        user_type = self.determine_user_type(user_input, intent_analysis["intent"])
        
        # Determine if tools are needed
        requires_tools = self._requires_tools(intent_analysis["intent"], user_input)
        
        # Create enhanced analysis
        analysis = EnhancedAnalyzedQuery(
            intent=intent_analysis["intent"],
            intent_confidence=intent_analysis["confidence"],
            sub_intent=intent_analysis["sub_intent"],
            entities=all_entities,
            sentiment=sentiment_analysis["sentiment"],
            sentiment_score=sentiment_analysis["score"],
            complexity_score=complexity_analysis["score"],
            complexity_factors=complexity_analysis["factors"],
            keywords=keywords,
            response="",  # Will be filled by the response generator
            requires_tools=requires_tools,
            user_type=user_type
        )
        
        # Log analytics
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        self._log_analytics(session_id, analysis, processing_time)
        
        return analysis
    
    def _parse_intent_response(self, response: str) -> Dict:
        """Parse LLM intent classification response."""
        # Implementation depends on your LLM response format
        # This is a simplified parser
        lines = response.lower().split('\n')
        
        intent = "general_information"
        confidence = 0.8
        sub_intent = "unknown"
        
        for line in lines:
            if 'intent:' in line or 'primary intent:' in line:
                intent = line.split(':')[-1].strip()
            elif 'confidence:' in line:
                try:
                    confidence = float(re.findall(r'0\.\d+|\d+\.\d+|\d+', line)[0])
                    if confidence > 1:
                        confidence = confidence / 100
                except:
                    confidence = 0.8
            elif 'sub-intent:' in line or 'sub intent:' in line:
                sub_intent = line.split(':')[-1].strip()
        
        return {
            "intent": intent,
            "confidence": confidence,
            "sub_intent": sub_intent
        }
    
    def _parse_entity_response(self, response: str) -> List[ExtractedEntity]:
        """Parse LLM entity extraction response."""
        # Simplified entity parser
        entities = []
        lines = response.split('\n')
        
        for line in lines:
            if ':' in line and any(ent_type in line.upper() for ent_type in 
                                 ['PRODUCT', 'PERSON', 'ORG', 'TECH', 'ISSUE']):
                try:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        entity_text = parts[1].strip()
                        entity_type = parts[0].strip().upper()
                        
                        entities.append(ExtractedEntity(
                            text=entity_text,
                            label=entity_type,
                            confidence=0.85,
                            start_pos=0,
                            end_pos=len(entity_text)
                        ))
                except:
                    continue
        
        return entities
    
    def _parse_complexity_response(self, response: str) -> Dict:
        """Parse complexity analysis response."""
        lines = response.lower().split('\n')
        score = 5
        factors = []
        
        for line in lines:
            if 'score:' in line or 'complexity:' in line:
                try:
                    score = int(re.findall(r'\d+', line)[0])
                except:
                    score = 5
            elif 'factor' in line and ':' in line:
                factor = line.split(':')[-1].strip()
                if factor:
                    factors.append(factor)
        
        return {
            "score": min(max(score, 1), 10),
            "factors": factors if factors else ["Standard complexity"],
            "estimated_time": "quick" if score <= 3 else "medium" if score <= 7 else "complex"
        }
    
    def _analyze_sentiment(self, text: str) -> Dict:
        """Enhanced sentiment analysis."""
        positive_words = ['great', 'excellent', 'good', 'amazing', 'perfect', 'love', 'thanks', 'thank you']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'broken', 'error', 'problem', 'issue', 'bug']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = "positive"
            score = min(0.5 + (positive_count * 0.2), 1.0)
        elif negative_count > positive_count:
            sentiment = "negative"
            score = max(-0.5 - (negative_count * 0.2), -1.0)
        else:
            sentiment = "neutral"
            score = 0.0
        
        return {"sentiment": sentiment, "score": score}
    
    def _requires_tools(self, intent: str, text: str) -> bool:
        """Determine if query requires tool assistance."""
        tool_requiring_intents = [
            'technical_question', 'product_inquiry', 'integration_help',
            'account_support'
        ]
        
        tool_keywords = [
            'how to', 'documentation', 'guide', 'tutorial', 'api',
            'feature', 'pricing', 'specification'
        ]
        
        if intent in tool_requiring_intents:
            return True
        
        return any(keyword in text.lower() for keyword in tool_keywords)
    
    def _log_analytics(self, session_id: str, analysis: EnhancedAnalyzedQuery, processing_time: float):
        """Log analytics data to database."""
        try:
            conn = sqlite3.connect(accessKeys.SQLITE_DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO query_analytics 
                (session_id, intent, intent_confidence, sub_intent, sentiment, 
                 sentiment_score, complexity_score, complexity_factors, entities, 
                 keywords, user_type, processing_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                analysis.intent,
                analysis.intent_confidence,
                analysis.sub_intent,
                analysis.sentiment,
                analysis.sentiment_score,
                analysis.complexity_score,
                json.dumps(analysis.complexity_factors),
                json.dumps([e.dict() for e in analysis.entities]),
                json.dumps(analysis.keywords),
                analysis.user_type,
                int(processing_time)
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Analytics logging error: {e}")

# Global instance
enhanced_nlp = EnhancedNLPPipeline()