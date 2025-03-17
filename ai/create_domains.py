import argparse
import json
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

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
         "name": "domain_name",
         "description": "Detailed description of domain responsibilities and functionality"
       },
       ...
     ]
   }
6. Ensure one domain has the exact name "common" (lowercase) containing all shared functionality.
7. Use only lowercase single words for domain names (e.g., "user", "payment", "inventory"). If absolutely required, it can have a maximum of 2 words separated by an underscore.
8. Be extremely specific about what functionality belongs in each domain.
"""
    
    # Truncate content if it exceeds max length
    if len(prompt) > 1048570:
        prompt = prompt[:1048570]
    
    response = client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "system", "content": "You are an expert in Domain-Driven Design who can identify bounded contexts and business domains from application functionality descriptions."},
            {"role": "user", "content": prompt}
        ],
        max_completion_tokens=4000
    )
    
    return response.choices[0].message.content

def count_tokens(text):
    encoding = tiktoken.encoding_for_model("o3-mini")
    return len(encoding.encode(text))

def first_part(class_mapping_file):
    print("Starting first part: Accumulating code chunks...")
    with open(class_mapping_file, 'r') as f:
        class_mapping = json.load(f)
    
    buffer = ""
    token_count = 0
    MAX_TOKENS = 180000  # Reduced from 190000 to avoid overflows
    chunks = []
    
    for class_name, file_path in class_mapping.items():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                file_content = f.read()
                
            file_tokens = count_tokens(file_content)
            
            # Skip files that are too large
            if file_tokens > MAX_TOKENS:
                print(f"Skipping {file_path} as it is too large ({file_tokens} tokens)")
                continue
                
            # If adding this file would exceed the limit, create a new chunk
            if token_count + file_tokens > MAX_TOKENS and token_count > 0:
                # Create prompt for this chunk
                prompt = """Analyze the following code and list out every single possible business functionality or application flow in as much detail as possible.

CODE TO ANALYZE:    
"""
                end_instructions = """

IMPORTANT INSTRUCTIONS:
Ensure that the output is a bulleted list of the functionalities and flows described in extreme detail, and nothing else. No titles or additional text."""
                
                full_content = prompt + buffer + end_instructions
                # Truncate content if it exceeds max length
                if len(full_content) > 1048570:
                    # Calculate how much to keep to stay under the limit
                    keep_length = 1048570 - len(prompt) - len(end_instructions)
                    truncated_text = buffer[:keep_length]
                    full_content = prompt + truncated_text + end_instructions
                
                # Count tokens in the entire chunk for accurate reporting
                chunk_tokens = count_tokens(full_content)
                chunks.append(full_content)
                print(f"Chunk {len(chunks)} created with {chunk_tokens} tokens")
                
                buffer = ""
                token_count = 0
            
            # Normal case - add file to the current buffer
            buffer += f"\n\n--- {class_name} ({file_path}) ---\n\n"
            buffer += file_content
            token_count += file_tokens
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    if token_count > 0:
        # Create prompt for the final chunk
        prompt = """Analyze the following code and list out every single possible business functionality or application flow in as much detail as possible.

CODE TO ANALYZE:    
"""
        end_instructions = """

IMPORTANT INSTRUCTIONS:
Ensure that the output is a bulleted list of the functionalities and flows described in extreme detail, and nothing else. No titles or additional text."""
        
        full_content = prompt + buffer + end_instructions
        # Truncate content if it exceeds max length
        if len(full_content) > 1048570:
            # Calculate how much to keep to stay under the limit
            keep_length = 1048570 - len(prompt) - len(end_instructions)
            truncated_text = buffer[:keep_length]
            full_content = prompt + truncated_text + end_instructions
        
        chunk_tokens = count_tokens(full_content)
        chunks.append(full_content)
        print(f"Final chunk {len(chunks)} created with {chunk_tokens} tokens")
    
    # Save all chunks to a JSON file
    with open("code_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    print(f"First part completed. {len(chunks)} chunks saved to code_chunks.json")

def second_part():
    print("Starting second part: Processing chunks with AI...")
    
    # Clear the summaries file at the start
    with open("all_summaries.txt", "w", encoding="utf-8") as f:
        pass
    
    # Load chunks from JSON file
    with open("code_chunks.json", "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{total_chunks}")
        
        response = client.chat.completions.create(
            model="o3-mini",
            messages=[
                {"role": "system", "content": "You are an expert software architect with a deep understanding of C# applications."},
                {"role": "user", "content": chunk}
            ],
            max_completion_tokens=5000
        )
        
        summary = response.choices[0].message.content
        
        # Save the summary immediately
        with open("all_summaries.txt", "a", encoding="utf-8") as f:
            f.write(summary + "\n")
        
        print(f"{i+1}/{total_chunks} summaries done")
    
    print("Second part completed. All summaries saved to all_summaries.txt")

def third_part():
    print("Starting third part: Generating business domains...")
    
    # Read all summaries from the file
    with open("all_summaries.txt", "r", encoding="utf-8") as f:
        content = f.read()
        summaries = content.split("\n\n")
        # Filter out empty summaries
        summaries = [s for s in summaries if s.strip()]
    
    print(f"Found {len(summaries)} summaries to process")
    
    # Generate business domains from all summaries
    business_domains_json = generate_business_domains(summaries)
    
    # Save the business domains to a file
    with open("business_domains.json", "w", encoding="utf-8") as f:
        f.write(business_domains_json)
    
    print("Third part completed. Business domains saved to business_domains.json")

def fourth_part(class_mapping_file):
    print("Starting fourth part: Classifying classes into business domains...")
    
    # Load class mapping
    with open(class_mapping_file, 'r') as f:
        class_mapping = json.load(f)
    
    # Load business domains
    with open("business_domains.json", 'r') as f:
        domains_data = json.load(f)
        domains = domains_data.get("domains", [])
    
    domain_names = [domain["name"] for domain in domains]
    domain_descriptions = {domain["name"]: domain["description"] for domain in domains}
    
    print(f"Found {len(domain_names)} domains: {', '.join(domain_names)}")
    
    # Prepare domain descriptions for the prompt
    domains_text = ""
    for name, description in domain_descriptions.items():
        domains_text += f"- {name}: {description}\n"
    
    # Create mapping between classes and domains
    class_domain_mapping = {}
    total_classes = len(class_mapping)
    
    for i, (class_name, file_path) in enumerate(class_mapping.items()):
        print(f"Processing class {i+1}/{total_classes}: {class_name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                file_content = f.read()
            
            # Truncate content if it's too large
            if len(file_content) > 900000:
                file_content = file_content[:900000] + "\n[Content truncated due to length]"
            
            prompt = f"""Analyze the following class code and classify it into exactly ONE of the business domains defined below.

BUSINESS DOMAINS:
{domains_text}

CLASS CODE ({class_name} at {file_path}):
{file_content}

INSTRUCTIONS:
1. Deeply analyze what this class does, its responsibilities, and its business purpose
2. Determine which single domain it belongs to (only one domain allowed)
3. Respond with ONLY the domain name (lowercase, exactly as listed above) and nothing else
"""
            
            response = client.chat.completions.create(
                model="o3-mini",
                messages=[
                    {"role": "system", "content": "You are a domain-driven design expert that can accurately classify code into business domains based on its functionality."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100  # Short response needed
            )
            
            domain = response.choices[0].message.content.strip().lower()
            
            # Validate that the response is one of our domains
            if domain not in domain_names:
                print(f"Warning: AI returned invalid domain '{domain}' for {class_name}. Defaulting to 'common'.")
                domain = "common"
            
            # Add to mapping
            class_domain_mapping[file_path] = domain
            print(f"Classified {class_name} as '{domain}'")
            
            # Save progress periodically
            if (i + 1) % 10 == 0:
                with open("class_domain_mapping.json", "w", encoding="utf-8") as f:
                    json.dump(class_domain_mapping, f, ensure_ascii=False, indent=2)
                print(f"Progress saved ({i+1}/{total_classes})")
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            # Add to mapping as error
            class_domain_mapping[file_path] = "error"
    
    # Save final mapping
    with open("class_domain_mapping.json", "w", encoding="utf-8") as f:
        json.dump(class_domain_mapping, f, ensure_ascii=False, indent=2)
    
    print("Fourth part completed. Class domain mapping saved to class_domain_mapping.json")

if __name__ == "__main__":
    # Sample commands:
    # python create_domains.py class_mapping.json --part 1  # Accumulate code chunks
    # python create_domains.py class_mapping.json --part 2  # Process chunks with AI
    # python create_domains.py class_mapping.json --part 3  # Generate business domains
    
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