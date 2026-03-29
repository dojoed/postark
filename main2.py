from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- TOOL: simple calculator ---
def calculator(expression):
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {str(e)}"


# --- AGENT LOOP ---
user_input = input("Ask me anything: ")

# Step 1: Ask model what to do
decision_prompt = f"""
You are an AI agent.

User input: {user_input}

Decide:
- If this is a math problem → respond with: CALCULATE: <expression>
- Otherwise → respond with: ANSWER: <response>
"""

decision = client.responses.create(
    model="gpt-4.1-mini",
    input=decision_prompt
)

decision_text = decision.output[0].content[0].text
print("\nDecision:", decision_text)


# Step 2: Act on decision
if decision_text.startswith("CALCULATE:"):
    expression = decision_text.replace("CALCULATE:", "").strip()
    tool_result = calculator(expression)

    # Step 3: Send result back to model
    final_prompt = f"""
    The user asked: {user_input}
    You calculated: {expression} = {tool_result}

    Respond with a final answer.
    """

    final = client.responses.create(
        model="gpt-4.1-mini",
        input=final_prompt
    )

    print("\nFinal Answer:")
    print(final.output[0].content[0].text)

else:
    print("\nFinal Answer:")
    print(decision_text.replace("ANSWER:", "").strip())