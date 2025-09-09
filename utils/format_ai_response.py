import re

def clean_ai_response(response_text):
    """
    Clean up the AI-generated response by:
    1. Removing code block markers like ```html and ```
    2. Removing references to FAQ
    3. Preserving formatting like line breaks
    """
    # Remove code block markers
    response_text = response_text.replace("```html", "").replace("```", "")

    # Remove references to FAQ
    response_text = response_text.replace("Based on our FAQ, ", "")
    response_text = response_text.replace("According to our FAQ, ", "")
    response_text = response_text.replace("From our FAQ, ", "")
    response_text = response_text.replace("Our FAQ indicates that ", "")

    # Clean up any trailing/leading whitespace
    response_text = response_text.strip()

    # Convert markdown-style asterisks to plain text bullets
    lines = response_text.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('*'):
            # Replace markdown bullets with plain text bullets
            lines[i] = '• ' + line.strip()[1:].strip()
        elif '**' in line:
            # Replace bold markdown with plain text
            lines[i] = line.replace('**', '')

    # Rejoin the lines
    response_text = '\n'.join(lines)

    return response_text

def format_llm_output_for_email(llm_text: str) -> str:
    """
    Converts raw LLM text with simple markdown into a structured HTML email body.
    - Handles '###' and '**word**' as bold headings.
    - Handles '-' and numbered lists as HTML bullet points.
    - Wraps paragraphs in <p> tags for proper spacing.
    - Wraps the entire output in a valid HTML document structure.
    """
    if not llm_text:
        return ""

    html_parts = []
    in_list = False
    
    lines = llm_text.strip().split('\n')

    for line in lines:
        line = line.strip()

        # ✅ NEW: Use regex to replace **word** with <strong>word</strong>
        line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)

        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        if line.startswith("###"):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            heading_text = line.replace("###", "").strip()
            if html_parts:
                html_parts.append("<br>")
            # The heading text might already be bolded by the regex, so we just add it.
            html_parts.append(f"<strong>{heading_text.replace('<strong>', '').replace('</strong>', '')}</strong>")
        
        elif line.startswith("- ") or (line.split('.')[0].isdigit() and line[1:3] == '. '):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item_text = line.split(' ', 1)[1]
            html_parts.append(f"<li>{item_text}</li>")
        
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p>{line}</p>")

    if in_list:
        html_parts.append("</ul>")

    inner_html = "".join(html_parts)
    return f"<html><body>{inner_html}</body></html>"