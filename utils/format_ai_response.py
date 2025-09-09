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
    - Handles '###' as bold headings.
    - Handles '-' and numbered lists as HTML bullet points.
    - Wraps paragraphs in <p> tags for proper spacing.
    """
    if not llm_text:
        return ""

    html_parts = []
    in_list = False
    
    # Split the text into lines for processing
    lines = llm_text.strip().split('\n')

    for line in lines:
        line = line.strip()

        # If the line is empty, it's a paragraph break
        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        # Handle headings (###)
        if line.startswith("###"):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            heading_text = line.replace("###", "").strip()
            # Add a line break before the heading for spacing, except for the first element
            if html_parts:
                html_parts.append("<br>")
            html_parts.append(f"<strong>{heading_text}</strong>")
        
        # Handle list items (-) or numbered (1., 2.)
        elif line.startswith("- ") or (line.split('.')[0].isdigit() and line[1:3] == '. '):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            # Remove the list marker ('- ' or '1. ')
            item_text = line.split(' ', 1)[1]
            html_parts.append(f"<li>{item_text}</li>")
        
        # Handle regular paragraphs
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p>{line}</p>")

    # Close any open list at the end
    if in_list:
        html_parts.append("</ul>")

    inner_html =  "".join(html_parts)
    return f"<html><body>{inner_html}</body></html>"