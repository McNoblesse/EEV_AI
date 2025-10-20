from jinja2 import Template
from psycopg_pool import ConnectionPool

from app.eev_configurations.config import settings

def LoadConversations(session_id, limit=None):
    template_str = """Chat History (last {{limit}} messages)
{% for i in messages -%}
{% if i['role'] == 'user' -%}
[{{ i['created_at'].strftime("%Y-%m-%d %H:%M:%S") }}] USER: {{ i['content'] }}
{% elif i['role'] == 'ai' -%}
[{{ i['created_at'].strftime("%Y-%m-%d %H:%M:%S") }}] AI: {{ i['content'] }}
{% endif -%}
{% endfor -%}
"""
    template = Template(template_str)
    
    with ConnectionPool(conninfo=settings.MEMORY_DB).connection() as conn:
        with conn.cursor() as cur:
            if limit is None:
                cur.execute("""
                    SELECT user_query, bot_response, created_at
                    FROM conversations
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    """,
                    (session_id,)
                )
            else:
                cur.execute("""
                    SELECT user_query, bot_response, created_at
                    FROM conversations
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (session_id, limit)
                )
            session_messages = cur.fetchall()

    if not session_messages:
        return "Chat History (last 10 messages)\nNo recent Chat"
    else:
        convert_to_template_format = [
                                      d
                                      for user_query, bot_response, created_at in session_messages
                                      for d in (
                                                {"role": "user", "content": user_query, "created_at": created_at},
                                                {"role": "ai", "content": bot_response, "created_at": created_at},
                                            )
                                     ]
        return template.render(messages=convert_to_template_format,
                               limit=int(limit/2) if limit is not None else "Full conversation")