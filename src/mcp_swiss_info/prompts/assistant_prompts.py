"""
Assistant prompts for the mcp-swiss-info server.
"""

from ..server import mcp
from ..utils.logger import setup_logger
from ..utils.validation import sanitize_input

logger = setup_logger("mcp_swiss_info.prompts.assistant")


@mcp.prompt
def helpful_assistant(task: str, style: str = "professional") -> str:
    """Generate a prompt for a helpful assistant with specific task and style."""
    try:
        sanitized_task = sanitize_input(task, max_length=1000)
        sanitized_style = sanitize_input(style, max_length=50)

        style_instructions = {
            "professional": "Maintain a professional and formal tone throughout your response.",
            "friendly": "Use a warm, approachable, and friendly tone in your communication.",
            "casual": "Keep the tone relaxed and conversational, as if talking to a friend.",
            "technical": "Use precise technical language appropriate for expert audiences.",
            "educational": "Explain concepts clearly with educational context and examples.",
        }

        style_instruction = style_instructions.get(
            sanitized_style.lower(), style_instructions["professional"]
        )

        prompt = f"""You are a helpful AI assistant. Your task is to: {sanitized_task}

Style Guidelines:
{style_instruction}

Additional Instructions:
- Provide accurate and relevant information
- Be concise yet comprehensive in your responses
- If you're unsure about something, clearly state your uncertainty
- Structure your response logically with clear sections if appropriate
- Include practical examples when helpful

Please complete the requested task following these guidelines."""

        logger.debug(f"Generated helpful assistant prompt with {sanitized_style} style")
        return prompt
    except Exception as e:
        logger.error(f"Error generating helpful assistant prompt: {e}")
        raise


@mcp.prompt
def code_reviewer(code: str, language: str = "python", focus: str = "general") -> str:
    """Generate a prompt for code review with specific focus areas."""
    try:
        sanitized_code = sanitize_input(code, max_length=5000)
        sanitized_language = sanitize_input(language, max_length=50)
        sanitized_focus = sanitize_input(focus, max_length=100)

        focus_areas = {
            "general": "overall code quality, readability, and best practices",
            "performance": "performance optimization and efficiency improvements",
            "security": "security vulnerabilities and potential risks",
            "style": "code style, formatting, and consistency",
            "bugs": "potential bugs, errors, and edge cases",
            "architecture": "code structure, design patterns, and architecture",
        }

        focus_description = focus_areas.get(sanitized_focus.lower(), focus_areas["general"])

        prompt = f"""Please review the following {sanitized_language} code with a focus on {focus_description}:

```{sanitized_language}
{sanitized_code}
```

Review Guidelines:
1. Analyze the code for issues related to: {focus_description}
2. Provide specific, actionable feedback
3. Suggest improvements with examples when possible
4. Highlight both strengths and areas for improvement
5. Consider {sanitized_language}-specific best practices
6. Rate the overall code quality on a scale of 1-10

Structure your review with:
- Summary of findings
- Specific issues (if any)
- Recommended improvements
- Positive aspects
- Overall rating and conclusion"""

        logger.debug(
            f"Generated code review prompt for {sanitized_language} with {sanitized_focus} focus"
        )
        return prompt
    except Exception as e:
        logger.error(f"Error generating code review prompt: {e}")
        raise


@mcp.prompt
def explain_concept(concept: str, audience: str = "general", depth: str = "medium") -> str:
    """Generate a prompt for explaining a concept to a specific audience."""
    try:
        sanitized_concept = sanitize_input(concept, max_length=200)
        sanitized_audience = sanitize_input(audience, max_length=50)
        sanitized_depth = sanitize_input(depth, max_length=20)

        audience_styles = {
            "beginner": "Use simple language, avoid jargon, and provide basic background context",
            "general": "Use clear language accessible to most people with some context",
            "technical": "Use appropriate technical terminology for an expert audience",
            "academic": "Use formal academic language with proper citations and theoretical context",
            "child": "Use very simple language, analogies, and fun examples appropriate for children",
        }

        depth_levels = {
            "basic": "Provide a simple overview with key points",
            "medium": "Include moderate detail with examples and context",
            "detailed": "Provide comprehensive coverage with in-depth analysis",
        }

        audience_style = audience_styles.get(
            sanitized_audience.lower(), audience_styles["general"]
        )

        depth_level = depth_levels.get(sanitized_depth.lower(), depth_levels["medium"])

        prompt = f"""Please explain the concept of "{sanitized_concept}" for a {sanitized_audience} audience.

Explanation Requirements:
- Audience: {sanitized_audience} - {audience_style}
- Depth: {sanitized_depth} - {depth_level}

Structure your explanation with:
1. Clear definition of the concept
2. Why it's important or relevant
3. Key components or aspects
4. Real-world examples or applications
5. Common misconceptions (if applicable)
6. Summary of key takeaways

Make sure your explanation is appropriate for the specified audience and depth level."""

        logger.debug(f"Generated concept explanation prompt for {sanitized_audience} audience")
        return prompt
    except Exception as e:
        logger.error(f"Error generating concept explanation prompt: {e}")
        raise