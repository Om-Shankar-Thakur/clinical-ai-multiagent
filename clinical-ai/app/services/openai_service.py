import os
from openai import AzureOpenAI
from dotenv import load_dotenv
load_dotenv()
class OpenAIService:
   def __init__(self):
       self.client = AzureOpenAI(
           api_key=os.getenv("AZURE_OPENAI_KEY"),
           api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
           azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
       )
       self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

   def generate(self, prompt: str) -> str:
       response = self.client.chat.completions.create(
           model=self.deployment,
           messages=[
               {"role": "system", "content": "You are a strict clinical reasoning engine. Always return valid JSON. Never hallucinate."},
               {"role": "user", "content": prompt}
           ],
           temperature=0.2,
           max_tokens=500,
           response_format={"type": "json_object"}
       )
       return response.choices[0].message.content.strip()