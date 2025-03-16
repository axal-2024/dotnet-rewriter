import argparse
import json
import os
import tiktoken
import openai

def summarize_with_ai(text):
    return text[0:100] + "..."

def count_tokens(text):
    encoding = tiktoken.encoding_for_model("o3-mini")
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
    MAX_TOKENS = 150000
    
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
            pass
    
    # Summarize any remaining content in the buffer
    if token_count > 0:
        summary = summarize_with_ai(buffer)
        print("\nSUMMARY:\n")
        print(summary)