"""
Analysis prompts for the mcp-swiss-info server.
"""

from ..server import mcp
from ..utils.logger import setup_logger
from ..utils.validation import sanitize_input

logger = setup_logger("mcp_swiss_info.prompts.analysis")


@mcp.prompt
def data_analyst(data_description: str, analysis_type: str = "descriptive") -> str:
    """Generate a prompt for data analysis tasks."""
    try:
        sanitized_description = sanitize_input(data_description, max_length=1000)
        sanitized_type = sanitize_input(analysis_type, max_length=50)

        analysis_types = {
            "descriptive": {
                "focus": "describe patterns, trends, and characteristics in the data",
                "methods": "summary statistics, distributions, visualizations, and data profiling",
            },
            "diagnostic": {
                "focus": "identify why certain patterns or anomalies occurred",
                "methods": "correlation analysis, root cause analysis, and comparative studies",
            },
            "predictive": {
                "focus": "forecast future trends and outcomes based on historical data",
                "methods": "statistical modeling, machine learning, and trend analysis",
            },
            "prescriptive": {
                "focus": "recommend actions and solutions based on the analysis",
                "methods": "optimization techniques, decision trees, and scenario planning",
            },
            "exploratory": {
                "focus": "discover hidden patterns and generate insights from the data",
                "methods": "clustering, dimensionality reduction, and hypothesis generation",
            },
        }

        analysis_info = analysis_types.get(
            sanitized_type.lower(), analysis_types["descriptive"]
        )

        prompt = f"""You are a skilled data analyst. Analyze the following data:

Data Description:
{sanitized_description}

Analysis Type: {sanitized_type.title()} Analysis
Focus: {analysis_info['focus']}
Recommended Methods: {analysis_info['methods']}

Please provide a comprehensive analysis that includes:

1. Data Understanding
   - Summary of the data characteristics
   - Key variables and their types
   - Data quality assessment

2. Analysis Approach
   - Methodology selection rationale
   - Analysis steps and techniques
   - Tools and methods to be used

3. Key Findings
   - Main patterns and insights
   - Statistical significance where applicable
   - Unexpected discoveries

4. Visualizations
   - Recommended charts and graphs
   - Key metrics to highlight
   - Dashboard elements if applicable

5. Conclusions and Recommendations
   - Actionable insights
   - Business implications
   - Next steps for further analysis

Present your analysis in a clear, structured format with supporting evidence and reasoning."""

        logger.debug(f"Generated data analysis prompt for {sanitized_type} analysis")
        return prompt
    except Exception as e:
        logger.error(f"Error generating data analysis prompt: {e}")
        raise


@mcp.prompt
def problem_solver(problem: str, approach: str = "systematic") -> str:
    """Generate a prompt for systematic problem solving."""
    try:
        sanitized_problem = sanitize_input(problem, max_length=1000)
        sanitized_approach = sanitize_input(approach, max_length=50)

        approaches = {
            "systematic": "Use a structured, step-by-step methodology",
            "creative": "Employ creative thinking and innovative approaches",
            "analytical": "Focus on logical analysis and data-driven solutions",
            "collaborative": "Consider multiple perspectives and stakeholder input",
            "agile": "Use iterative problem-solving with rapid prototyping",
        }

        approach_description = approaches.get(
            sanitized_approach.lower(), approaches["systematic"]
        )

        prompt = f"""You are an expert problem solver. Please address the following problem using a {sanitized_approach} approach:

Problem Statement:
{sanitized_problem}

Approach: {approach_description}

Please structure your problem-solving process as follows:

1. Problem Analysis
   - Clearly define the core problem
   - Identify stakeholders and impact
   - Determine scope and constraints
   - List assumptions and known facts

2. Root Cause Analysis
   - Explore potential underlying causes
   - Use appropriate analysis techniques
   - Prioritize causes by likelihood and impact
   - Validate cause-effect relationships

3. Solution Generation
   - Brainstorm multiple solution options
   - Evaluate feasibility and resources required
   - Consider risks and potential obstacles
   - Assess pros and cons of each option

4. Solution Selection and Planning
   - Recommend the best solution(s)
   - Provide detailed implementation steps
   - Identify required resources and timeline
   - Define success metrics and milestones

5. Risk Assessment and Mitigation
   - Identify potential risks and challenges
   - Develop mitigation strategies
   - Create contingency plans
   - Establish monitoring mechanisms

6. Next Steps and Follow-up
   - Immediate action items
   - Long-term considerations
   - Review and adjustment procedures
   - Communication and stakeholder management

Use clear reasoning throughout and support your recommendations with evidence and logical analysis."""

        logger.debug(f"Generated problem-solving prompt with {sanitized_approach} approach")
        return prompt
    except Exception as e:
        logger.error(f"Error generating problem-solving prompt: {e}")
        raise


@mcp.prompt
def comparative_analysis(item_a: str, item_b: str, criteria: str = "general") -> str:
    """Generate a prompt for comparative analysis between two items."""
    try:
        sanitized_item_a = sanitize_input(item_a, max_length=200)
        sanitized_item_b = sanitize_input(item_b, max_length=200)
        sanitized_criteria = sanitize_input(criteria, max_length=200)

        prompt = f"""Please conduct a comprehensive comparative analysis between the following two items:

Item A: {sanitized_item_a}
Item B: {sanitized_item_b}

Comparison Criteria: {sanitized_criteria}

Structure your analysis as follows:

1. Overview
   - Brief description of each item
   - Context and background information
   - Purpose of the comparison

2. Similarities
   - Common features or characteristics
   - Shared strengths or advantages
   - Areas where both perform equally well

3. Key Differences
   - Distinct features or approaches
   - Performance variations
   - Different use cases or applications

4. Detailed Comparison
   Create a structured comparison covering:
   - Functionality/Features
   - Performance/Effectiveness
   - Cost/Value proposition
   - Usability/User experience
   - Reliability/Quality
   - Scalability/Flexibility
   - Support/Documentation
   
5. Pros and Cons
   Item A:
   - Advantages
   - Disadvantages
   
   Item B:
   - Advantages
   - Disadvantages

6. Recommendations
   - Which item is better for specific use cases
   - Factors to consider when choosing
   - Situations where each excels
   - Overall recommendation with justification

7. Conclusion
   - Summary of key insights
   - Decision framework for selection
   - Final thoughts and considerations

Use objective analysis and provide specific examples where possible. Support your conclusions with clear reasoning and evidence."""

        logger.debug(
            f"Generated comparative analysis prompt for {sanitized_item_a} vs {sanitized_item_b}"
        )
        return prompt
    except Exception as e:
        logger.error(f"Error generating comparative analysis prompt: {e}")
        raise