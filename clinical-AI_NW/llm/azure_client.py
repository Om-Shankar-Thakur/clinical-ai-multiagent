import os
from openai import AzureOpenAI
from dotenv import load_dotenv
load_dotenv()
class AzureLLM:
   def __init__(self):
       self.client = AzureOpenAI(
           api_key=os.getenv("AZURE_OPENAI_API_KEY"),
           api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
           azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
       )
       self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
   def generate(self, system_prompt, user_prompt):
       response = self.client.chat.completions.create(
           model=self.deployment,
           messages=[
               {"role": "system", "content": system_prompt},
               {"role": "user", "content": user_prompt}
           ],
           temperature=0.2
       )
       return response.choices[0].message.content