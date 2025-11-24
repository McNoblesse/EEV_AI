"""
Tier 2: Moderate Complexity (Complexity 31-60)
- Product inquiries
- How-to questions
- FAQ with context needed
- Potential escalation to human
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import logging
from datetime import datetime

from security.authentication import get_client_context, build_namespace
from model.schema import RequestPayload, PayloadResponse
from config.database import get_db
from model.database_models import Conversation, ConversationAnalytics
from utils.complexity_analyzer import complexity_analyzer
from utils.tools import retriever_tool, send_mail_to_human_agent_sync

router = APIRouter(prefix="/model", tags=["Tier 2 Model"])
logger = logging.getLogger(__name__)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


@router.post("/tier_2_model", response_model=PayloadResponse)
async def tier_2_handler(
    data: RequestPayload,
    client: dict = Depends(get_client_context),
    db: Session = Depends(get_db)
):
    """Tier 2: Moderate complexity with client-specific knowledge retrieval"""
    
    client_id = client["client_id"]
    
    # ✅ EXTRACT CATEGORY FROM REQUEST
    category = getattr(data, 'category', None)
    
    # ✅ BUILD NAMESPACE
    namespace = build_namespace(client_id, category)
    
    logger.info(f"Tier 2 query from client: {client['client_name']} ({client_id}), category: {category}, namespace: {namespace}")
    
    start_time = datetime.now()
    
    try:
        # Complexity analysis
        complexity_result = await complexity_analyzer.analyze_with_llm(data.user_query)
        
        # Route to Tier 1 if too simple (score < 31)
        if complexity_result.score < 31:
            logger.info(f"Query too simple for Tier 2, routing to Tier 1: score={complexity_result.score}")
            return PayloadResponse(
                session_id=data.session_id,
                response="Your query is being handled by our quick response system...",
                intent="general_question",
                intent_confidence=0.8,
                sub_intent="simple_query",
                sentiment="neutral",
                sentiment_score=0.0,
                complexity_score=complexity_result.score,
                complexity_factors=complexity_result.factors,
                entities=[],
                keywords=[],
                user_type="general",
                escalate=True,  # Route to Tier 1
                conversation_summary=None,
                conversation_ended=False,
                reasoning_steps=[f"Routed to Tier 1: {complexity_result.reasoning}"],
                retrieved_context=[],
                tools_used=[],
                processing_time_ms=0
            )
        
        # Route to Tier 3 if very complex
        if complexity_result.score > 70:
            logger.info(f"Routing to Tier 3: score={complexity_result.score}")
            return PayloadResponse(
                session_id=data.session_id,
                response="Your query requires our advanced AI system. Connecting you now...",
                intent="escalation_request",
                intent_confidence=0.9,
                sub_intent="tier3_routing",
                sentiment="neutral",
                sentiment_score=0.0,
                complexity_score=complexity_result.score,
                complexity_factors=complexity_result.factors,
                entities=[],
                keywords=[],
                user_type="business",
                escalate=True,
                conversation_summary=None,
                conversation_ended=False,
                reasoning_steps=[f"Routed to Tier 3: {complexity_result.reasoning}"],
                retrieved_context=[],
                tools_used=[],
                processing_time_ms=0
            )
        
        # Handle Tier 2 queries (31-70)
        logger.info(f"Processing Tier 2 query: score={complexity_result.score}")
        
        # ✅ RETRIEVE WITH CATEGORY
        kb_results = retriever_tool.invoke({
            "query": data.user_query,
            "client_id": client_id,
            "category": category  # ✅ PASS CATEGORY
        })
        
        # Log what we got
        logger.info(f"📚 Retrieved context length: {len(kb_results)} chars")
        
        # Generate response
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are eeV Assistant for {client['client_name']}.

Provide helpful, accurate responses using ONLY the knowledge base context provided.

IMPORTANT: 
- You can ONLY answer based on the knowledge base for {client['client_name']}
- If information is not in the provided context, clearly state: "I don't have that information in our knowledge base"
- Always cite the source document when providing information
"""),
            ("human", "Query: {query}\n\nKnowledge Base Context:\n{context}\n\nProvide response:")
        ])
        
        chain = prompt | llm
        response = await chain.ainvoke({
            "query": data.user_query,
            "context": kb_results[:3000] if kb_results else f"No documentation found in {client['client_name']}'s knowledge base."
        })
        
        ai_response = response.content
        
        # Check if escalation needed
        escalate_triggers = ['not sure', 'need specialist', 'escalate', 'complex issue']
        should_escalate = any(trigger in ai_response.lower() for trigger in escalate_triggers) or complexity_result.score >= 60
        
        if should_escalate and complexity_result.score >= 70:
            try:
                send_mail_to_human_agent_sync.invoke({
                    "issue_description": f"Tier 2 Escalation\n\nQuery: {data.user_query}\n\nComplexity: {complexity_result.score}\n\nSession: {data.session_id}",
                    "session_id": data.session_id
                })
                ai_response += "\n\n✅ I've notified our specialist team. They'll follow up shortly."
            except Exception as e:
                logger.error(f"Escalation email failed: {e}")
        
        # Calculate processing time
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Save to database - MAIN CONVERSATION TABLE
        conversation = Conversation(
            client_id=client_id,  # ✅ NEW
            session_id=data.session_id,
            user_query=data.user_query,
            bot_response=ai_response,
            intent="product_inquiry",
            intent_confidence=0.75,
            sub_intent="moderate_complexity",
            sentiment="neutral",
            sentiment_score=0.0,
            complexity_score=complexity_result.score,  # This is now safe (31-70)
            channel=getattr(data, 'channel', 'chat'),
            requires_escalation=should_escalate,
            user_type="business",
            conversation_summary=None,
            conversation_ended=False,
            entities=[],
            keywords=complexity_result.factors,
            complexity_factors=complexity_result.factors,
            reasoning_steps=[complexity_result.reasoning],
            tool_calls_used=["retriever_tool"],
            retrieval_context=[kb_results[:500]] if kb_results else [],
            processing_time_ms=processing_time,
            tokens_used=0,
            model_used="gpt-4o-mini"
        )
        
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        # OPTIONALLY: Also save to analytics table
        try:
            analytics = ConversationAnalytics(
                conversation_id=conversation.id,
                entities=[],
                keywords=complexity_result.factors,
                complexity_factors=complexity_result.factors,
                reasoning_steps=[complexity_result.reasoning],
                tool_calls_used=["retriever_tool"],
                retrieval_context=[kb_results[:500]] if kb_results else [],
                processing_time_ms=processing_time,
                tokens_used=0,
                model_used="gpt-4o-mini"
            )
            db.add(analytics)
            db.commit()
        except Exception as e:
            logger.warning(f"Analytics table save failed (non-critical): {e}")
        
        return PayloadResponse(
            session_id=data.session_id,
            response=ai_response,
            intent="product_inquiry",
            intent_confidence=0.75,
            sub_intent=f"category_{category}" if category else "general",  # ✅ INCLUDE CATEGORY
            sentiment="neutral",
            sentiment_score=0.0,
            complexity_score=complexity_result.score,
            complexity_factors=complexity_result.factors,
            entities=[],
            keywords=complexity_result.factors,
            user_type="business",
            escalate=should_escalate,
            conversation_summary=None,
            conversation_ended=False,
            reasoning_steps=[complexity_result.reasoning, f"Searched namespace: {namespace}"],  # ✅ ADD
            retrieved_context=[kb_results[:500]] if kb_results else [],
            tools_used=["retriever_tool"],
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Tier 2 error for client {client_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")