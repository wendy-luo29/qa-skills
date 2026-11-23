
import sys
import json

def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_json.py <file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            # Try to load the JSON to check for validity
            json.load(f)
        print(f"Success: JSON validation successful for: {file_path}")
        sys.exit(0)
    except json.JSONDecodeError as e:
        print(f"❌ JSON validation failed for: {file_path}", file=sys.stderr)
        print(f"Error details: {e}", file=sys.stderr)
        print("Hint: Check for unescaped quotes, trailing commas, or incorrect structure.", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
