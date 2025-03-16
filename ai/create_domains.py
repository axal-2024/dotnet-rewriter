import argparse
import json
import os
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def summarize_with_ai(text):
    prompt = """
Analyze the following code and identify the core business functionalities and important application flows.
Think very deeply and make sure to tie back each functionality or flow to the purpose it was written with.
Make sure that your analysis covers every single aspect and functionality of the given code in as much detail as possible.

CODE TO ANALYZE:    
"""
    
    response = client.chat.completions.create(
        model="o3-mini",
        messages=[
            {"role": "system", "content": "You are an expert software architect with deep understanding of C# applications."},
            {"role": "user", "content": prompt + text}
        ],
        max_completion_tokens=120000
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
    MAX_TOKENS = 100000
    
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
    
    # Summarize any remaining content in the buffer
    if token_count > 0:
        summary = summarize_with_ai(buffer)
        print("\nSUMMARY:\n")
        print(summary)