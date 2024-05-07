import sys

def format_arguments(args):
    formatted_text = ", ".join([f"{{$arg:row.$arg}}" for arg in args[1:]])  # Skip the first argument which is the script name
    return f"{{ {formatted_text} }}"

if __name__ == "__main__":
    # Ensure that there is at least one command line argument besides the script name
    if len(sys.argv) > 1:
        output = format_arguments(sys.argv)
        print(output)
    else:
        print("No command line arguments provided.")
