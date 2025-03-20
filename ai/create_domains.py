import argparse
import json
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv
import threading
import concurrent.futures
from tqdm import tqdm
from google import genai
import os

GEMINI_MODEL_ID = "gemini-2.0-flash-thinking-exp-01-21"
load_dotenv()
client = OpenAI()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_business_domains(full_text):
    prompt = """Identify business domains from these code summaries. Format as JSON.

CODE SUMMARIES:
"""
    prompt += f"\n{full_text}\n"

    prompt += """
RULES:
1. Domains MUST:
   - Represent distinct business capabilities (e.g. "orders", "payments")
   - Be independently meaningful to business stakeholders
   - Contain only lowercase letters and hyphens, and NO OTHER CHARACTERS
   - Be a single word, and have up to 2 words if absolutely unavoidable

2. Create ONE 'common' domain ONLY for:
   - Shared technical utilities (logging, data connectors)
   - Non-business scaffolding reused across domains

3. FORBIDDEN:
   - Technical terms (e.g. "api", "database")
   - Generic groupings (e.g. "utils", "helpers")
   - Functional layers (e.g. "controllers", "services")

4. Output JSON structure (to be followed EXACTLY):
{
  "domains": [
    {
      "name": "lowercase-name", 
      "description": "Specific business capability in 8-12 words"
    }
  ]
}

Now, generate the domains using the exact JSON format provided, and ENSURE that you include a 'common' domain."""

    if len(prompt) > 1048570:
        prompt = prompt[:1048570]
    
    response = client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "system", "content": "You are an expert in software architecture, and you think through each decision very deeply and precisely."},
            {"role": "user", "content": prompt}
        ],
        max_completion_tokens=4000
    )
    
    response_content = response.choices[0].message.content
    try:
        domains_json = json.loads(response_content)
        for domain in domains_json["domains"]:
            domain["name"] = domain["name"].lower().replace(" ", "-").replace("_", "-")
        return json.dumps(domains_json)
    except json.JSONDecodeError:
        return response_content

def count_tokens(text):
    encoding = tiktoken.encoding_for_model("o3-mini")
    return len(encoding.encode(text))

def count_gemini_tokens(input: str):

    return len(input)//4
    
    response = gemini_client.models.count_tokens(
        model=GEMINI_MODEL_ID,
        contents=input,
    )

    return response.total_tokens

def generate_gemini_response(prompt):
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL_ID,
        contents=prompt
    )

    return response.text

def first_part(class_mapping_file):
    print("Starting first part: Accumulating code chunks...")
    with open(class_mapping_file, 'r') as f:
        class_mapping = json.load(f)
    
    buffer = ""
    token_count = 0
    MAX_TOKENS = 800000
    chunks = []

    PROMPT_TEMPLATE =   """Extract all business capabilities, workflows, and domain concepts from this code.

CODE:    
"""

    END_INSTRUCTIONS_TEMPLATE = """

        OUTPUT REQUIREMENTS:
        - List ONLY concrete business operations and domain entities
        - Focus on what the code DOES for the business, not how it works
        - Identify cross-cutting concerns and shared business utilities
        - Ignore technical implementation details"""
    
    for class_name, file_path in class_mapping.items():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                file_content = f.read()
                
            file_tokens = count_gemini_tokens(file_content)
            
            if file_tokens > MAX_TOKENS:
                print(f"Skipping {file_path} as it is too large ({file_tokens} tokens)")
                continue
                
            if token_count + file_tokens > MAX_TOKENS and token_count > 0:
                
                full_content = PROMPT_TEMPLATE + buffer + END_INSTRUCTIONS_TEMPLATE
                
                chunk_tokens = count_gemini_tokens(full_content)
                chunks.append(full_content)
                print(f"Chunk {len(chunks)} created with {chunk_tokens} tokens")
                
                buffer = ""
                token_count = 0
            
            buffer += f"\n\n--- {class_name} ({file_path}) ---\n\n"
            buffer += file_content
            token_count += file_tokens
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    if token_count > 0:
        
        full_content = PROMPT_TEMPLATE + buffer + END_INSTRUCTIONS_TEMPLATE
        
        chunk_tokens = count_gemini_tokens(full_content)
        chunks.append(full_content)
        print(f"Final chunk {len(chunks)} created with {chunk_tokens} tokens")
    
    with open("code_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    print(f"First part completed. {len(chunks)} chunks saved to code_chunks.json")

def second_part():
    print("Starting second part: Processing chunks with AI...")
    
    with open("all_summaries.txt", "w", encoding="utf-8") as f:
        pass
    
    with open("code_chunks.json", "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{total_chunks}")

        summary = generate_gemini_response(chunk)
        
        with open("all_summaries.txt", "a", encoding="utf-8") as f:
            f.write(summary + "\n")
        
        print(f"{i+1}/{total_chunks} summaries done")
    
    print("Second part completed. All summaries saved to all_summaries.txt")

def third_part():
    print("Starting third part: Generating business domains...")

    content = ""
    
    with open("all_summaries.txt", "r", encoding="utf-8") as f:
        content = f.read()
        
    business_domains_json = generate_business_domains(content)
    
    with open("business_domains.json", "w", encoding="utf-8") as f:
        f.write(business_domains_json)
    
    print("Third part completed. Business domains saved to business_domains.json")

def fourth_part(class_mapping_file):
    print("Starting fourth part: Classifying classes into business domains...")
    
    with open(class_mapping_file, 'r') as f:
        class_mapping = json.load(f)
    
    with open("business_domains.json", 'r') as f:
        domains_data = json.load(f)
        domains = domains_data.get("domains", [])
    
    domain_names = [domain["name"] for domain in domains]
    domain_descriptions = {domain["name"]: domain["description"] for domain in domains}
    
    print(f"Found {len(domain_names)} domains: {', '.join(domain_names)}")
    
    domains_text = ""
    for name, description in domain_descriptions.items():
        domains_text += f"- {name}: {description}\n"
    
    class_domain_mapping = {}
    mapping_lock = threading.Lock()
    save_lock = threading.Lock()
    progress_counter = {"processed": 0}
    counter_lock = threading.Lock()
    
    total_classes = len(class_mapping)
    
    def process_class(item):
        class_name, file_path = item
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                file_content = f.read()
            
            if len(file_content) > 1048570:
                file_content = file_content[:1048570]
            
            prompt = f"""Analyze the following C# code and determine the single most appropriate business domain for the specified class based on its primary responsibility.

BUSINESS DOMAINS:
{domains_text}

CLASS CODE ({class_name} at {file_path}):
{file_content}

INSTRUCTIONS:
1. Focus ONLY on the class named '{class_name}' even if the file contains multiple classes
2. Deeply analyze what this specific class does, its responsibilities, and its business purpose
3. Determine which single domain it belongs to (ONLY ONE domain allowed)
4. Respond with ONLY the domain name (lowercase, exactly as listed above) and nothing else
5. Use 'common' ONLY for:
- Classes used across multiple domains with equal importance
- Infrastructure/utility code with no business-specific logic
"""
            
            response = client.chat.completions.create(
                model="o3-mini",
                messages=[
                    {"role": "system", "content": "You are a domain-driven design expert that can accurately classify code into business domains based on its functionality."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            domain = response.choices[0].message.content.strip().lower()
            
            if domain not in domain_names:
                print(f"Warning: AI returned invalid domain '{domain}' for {class_name}. Defaulting to 'unknown'.")
                domain = "common"
            
            with mapping_lock:
                class_domain_mapping[class_name] = domain
            
            with counter_lock:
                progress_counter["processed"] += 1
                current_count = progress_counter["processed"]
                
                if current_count % 10 == 0:
                    with save_lock:
                        with open("class_domain_mapping.json", "w", encoding="utf-8") as f:
                            json.dump(class_domain_mapping, f, ensure_ascii=False, indent=2)
                        print(f"Progress saved ({current_count}/{total_classes})")
            
            return f"Classified {class_name} as '{domain}'"
            
        except Exception as e:
            error_msg = f"Error processing {file_path}: {str(e)}"
            print(error_msg)
            
            with mapping_lock:
                class_domain_mapping[class_name] = "common"
            
            with counter_lock:
                progress_counter["processed"] += 1
                
            return error_msg
    
    print(f"Processing {total_classes} classes with 20 concurrent threads...")
    
    def process_class_with_retry(item, max_retries=5):
        class_name, file_path = item
        retry_count = 0
        backoff_time = 1
        
        while retry_count <= max_retries:
            try:
                return process_class(item)
            except Exception as e:
                error_str = str(e)
                if "rate_limit_exceeded" in error_str and retry_count < max_retries:
                    retry_count += 1
                    import random
                    jitter = random.uniform(0.1, 0.3)
                    wait_time = backoff_time + jitter
                    
                    import re
                    wait_match = re.search(r'try again in (\d+\.?\d*)([ms]+)', error_str)
                    if wait_match:
                        time_value = float(wait_match.group(1))
                        time_unit = wait_match.group(2)
                        if time_unit == 'ms':
                            suggested_wait = time_value / 1000
                        else:
                            suggested_wait = time_value
                        wait_time = max(wait_time, suggested_wait * 1.5)
                    
                    print(f"Rate limit hit for {class_name}, retrying in {wait_time:.2f}s (attempt {retry_count}/{max_retries})")
                    import time
                    time.sleep(wait_time)
                    
                    backoff_time = min(backoff_time * 2, 60)
                else:
                    raise
        
        error_msg = f"Error processing {file_path} after {max_retries} retries: Rate limit exceeded"
        print(error_msg)
        
        with mapping_lock:
            class_domain_mapping[class_name] = "common"
        
        with counter_lock:
            progress_counter["processed"] += 1
            
        return error_msg
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_class = {executor.submit(process_class_with_retry, item): item[0] for item in class_mapping.items()}
        
        for future in tqdm(concurrent.futures.as_completed(future_to_class), total=len(future_to_class)):
            class_name = future_to_class[future]
            try:
                result = future.result()
            except Exception as exc:
                print(f"Processing of {class_name} generated an exception: {exc}")
    
    with open("class_domain_mapping.json", "w", encoding="utf-8") as f:
        json.dump(class_domain_mapping, f, ensure_ascii=False, indent=2)
    
    print("Fourth part completed. Class domain mapping saved to class_domain_mapping.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process class mapping file and summarize code.")
    parser.add_argument("class_mapping_file", help="Path to the class mapping JSON file")
    parser.add_argument("--part", type=int, choices=[1, 2, 3, 4], default=1, 
                        help="Which part to run: 1=accumulate chunks, 2=process with AI, 3=generate domains, 4=classify classes")
    
    args = parser.parse_args()
    
    if args.part == 1:
        first_part(args.class_mapping_file)
    elif args.part == 2:
        second_part()
    elif args.part == 3:
        third_part()
    elif args.part == 4:
        fourth_part(args.class_mapping_file)