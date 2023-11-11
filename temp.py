import openai

# Set your OpenAI API key here
openai.api_key = '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'

# Your prompt or code to be completed
prompt = """
Write a Python function that calculates the square of a number.
"""

# Make an API call to OpenAI GPT-3
response = openai.Completion.create(
  engine="text-davinci-002",
  prompt=prompt,
  max_tokens=100  # Adjust the number of tokens as needed
)

# Get and print the completed code
completed_code = response.choices[0].text
print(completed_code)
