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