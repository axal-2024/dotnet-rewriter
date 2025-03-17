import argparse
import json
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def summarize_with_ai(text):
    prompt = """Analyze the following code and list out every single possible business functionality or application flow in as much detail as possible.

CODE TO ANALYZE:    
"""
    end_instructions = """

IMPORTANT INSTRUCTIONS:
Ensure that the output is a bulleted list of the functionalities and flows described in extreme detail, and nothing else. No titles or additional text."""
    
    response = client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "system", "content": "You are an expert software architect with a deep understanding of C# applications."},
            {"role": "user", "content": prompt + text + end_instructions}
        ],
        max_completion_tokens=5000
    )
    
    return response.choices[0].message.content

def generate_business_domains(summaries):
    prompt = """Based on all the functionalities and application flows below, identify business domains according to Domain-Driven Design principles.

SUMMARIES OF FUNCTIONALITIES:
"""
    
    for i, summary in enumerate(summaries):
        prompt += f"\n--- SUMMARY {i+1} ---\n{summary}\n"
    
    prompt += """
INSTRUCTIONS:
1. Identify specific business domains that should be independent of each other according to Domain-Driven Design principles.
2. Create a single 'common' domain for functionality that is shared across domains.
3. Do NOT create any other utility, application, or common domains - only specific domains and a single common domain.
4. For each domain, provide a detailed description of what functionality it includes.
5. Format your response as a valid JSON object with the following structure:
   {
     "domains": [
       {
         "name": "DomainName",
         "description": "Detailed description of domain responsibilities and functionality"
       },
       ...
     ]
   }
6. Ensure one domain has the name "Common" containing all shared functionality.
"""
    
    response = client.chat.completions.create(
        model="o3-mini-high",
        messages=[
            {"role": "system", "content": "You are an expert in Domain-Driven Design who can identify bounded contexts and business domains from application functionality descriptions."},
            {"role": "user", "content": prompt}
        ],
        max_completion_tokens=4000
    )
    
    return response.choices[0].message.content

def count_tokens(text):
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(text))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process class mapping file and summarize code.")
    parser.add_argument("class_mapping_file", help="Path to the class mapping JSON file")
    
    args = parser.parse_args()
    
    class_mapping_file = args.class_mapping_file
    
    with open(class_mapping_file, 'r') as f:
        class_mapping = json.load(f)
    
    buffer = ""
    token_count = 0
    MAX_TOKENS = 190000
    summaries = []
    summary_count = 0
    
    for class_name, file_path in class_mapping.items():
        try:
            with open(file_path, 'r') as f:
                file_content = f.read()
                
            file_tokens = count_tokens(file_content)
            
            if token_count + file_tokens > MAX_TOKENS and token_count > 0:
                summary = summarize_with_ai(buffer)
                summaries.append(summary)
                summary_count += 1
                print(f"no. of summaries done = {summary_count}")
                
                buffer = ""
                token_count = 0
            
            buffer += f"\n\n--- {class_name} ({file_path}) ---\n\n"
            buffer += file_content
            token_count += file_tokens
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    if token_count > 0:
        summary = summarize_with_ai(buffer)
        summaries.append(summary)
        summary_count += 1
        print(f"no. of summaries done = {summary_count}")
    
    # Save all summaries to a text file
    if summaries:
        with open("all_summaries.txt", "w", encoding="utf-8") as f:
            for s in summaries:
                f.write(s + "\n")
    
    # Generate business domains from all summaries and save to a text file
    if summaries:
        business_domains_json = generate_business_domains(summaries)
        with open("business_domains.txt", "w", encoding="utf-8") as f:
            f.write(business_domains_json)