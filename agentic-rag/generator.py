from .response import generate_answer

def agentic_generate(query, context):
    # Step 1: initial answer
    answer = generate_answer(query, context, mode="analysis")

    # Step 2: critique
    critique = generate_answer(query, answer, mode="critique")

    # Step 3: refine if needed
    if any(word in critique.lower() for word in ["missing", "incorrect", "incomplete"]):
        improved = generate_answer(query, answer, mode="refine")
        return improved

    return answer