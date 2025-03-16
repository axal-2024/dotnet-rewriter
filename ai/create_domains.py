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
    
    for class_name, file_path in class_mapping.items():
        try:
            with open(file_path, 'r') as f:
                file_content = f.read()
                
            file_tokens = count_tokens(file_content)
            
            if token_count + file_tokens > MAX_TOKENS and token_count > 0:
                summary = summarize_with_ai(buffer)
                print("\nSUMMARY:\n")
                print(summary)
                print("\n" + "="*80 + "\n")
                
                buffer = ""
                token_count = 0
            
            buffer += f"\n\n--- {class_name} ({file_path}) ---\n\n"
            buffer += file_content
            token_count += file_tokens
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    if token_count > 0:
        summary = summarize_with_ai(buffer)
        print("\nSUMMARY:\n")
        print(summary)