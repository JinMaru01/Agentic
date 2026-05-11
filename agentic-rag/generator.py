from .response import generate_answer, generate_critique, refine_answer

def agentic_generate(query, context):
    # Step 1: initial answer
    answer = generate_answer(query, context, mode="analysis")
    print("\nGenerated answer:\n", answer)

    # Step 2: critique
    critique = generate_critique(query, context, answer)
    print("\nGenerated critique:\n", critique)

    # Step 3: refine if needed
    if any(word in critique.lower() for word in ["missing", "incorrect", "incomplete"]):
        improved = refine_answer(query, context, answer, critique="refine")
        return improved

    return answer