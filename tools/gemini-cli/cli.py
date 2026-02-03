import os
import sys
import click
import subprocess
from google import genai
from rich.console import Console

console = Console()

def run_command(command):
    """Executes a shell command and returns output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nEXIT CODE: {result.returncode}"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path, content):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

SYSTEM_PROMPT = """
You are an AI coding agent. You can read files, write files, and execute commands.
You MUST output your actions in a specific XML format so I can execute them.

AVAILABLE TOOLS:

1. <execute_command>command</execute_command>
   Runs a shell command. Use for ls, grep, find, running tests, etc.

2. <read_file>path/to/file</read_file>
   Reads a file's content.

3. <write_file path="path/to/file">
   content here
   </write_file>
   Writes content to a file. Overwrites if exists.

4. <final_answer>message</final_answer>
   Use this when you are done with the task.

INSTRUCTIONS:
- You will receive the output of your commands in the next turn.
- Do not output markdown code blocks around the XML tags.
- Output ONLY valid XML tool calls.
"""

@click.command()
@click.option("--model", default="gemini-1.5-pro", help="Model to use")
@click.argument("prompt", required=False)
def main(model, prompt):
    """Custom Gemini CLI with R/W/Exec tools"""
    
    if not prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read()
        else:
            console.print("[red]Error: No prompt provided[/red]")
            return

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    chat = client.chats.create(model=model)
    
    # Initial message
    full_prompt = SYSTEM_PROMPT + "\n\nTASK:\n" + prompt
    
    # Simple loop (max 10 turns per invocation to prevent infinite loops)
    for _ in range(10):
        try:
            response = chat.send_message(full_prompt)
            content = response.text
            print(content) # Print the model's thought/action
            
            # Very basic XML parsing (robust enough for this)
            if "<execute_command>" in content:
                cmd = content.split("<execute_command>")[1].split("</execute_command>")[0].strip()
                output = run_command(cmd)
                full_prompt = f"COMMAND OUTPUT:\n{output}"
                print(f"[{cmd}] -> {len(output)} chars")
                
            elif "<read_file>" in content:
                path = content.split("<read_file>")[1].split("</read_file>")[0].strip()
                output = read_file(path)
                full_prompt = f"FILE CONTENT ({path}):\n{output}"
                print(f"[read {path}] -> {len(output)} chars")
                
            elif '<write_file path="' in content:
                path = content.split('<write_file path="')[1].split('"')[0]
                file_content = content.split('">')[1].split('</write_file>')[0]
                output = write_file(path, file_content)
                full_prompt = f"WRITE OUTPUT:\n{output}"
                print(f"[write {path}] -> Success")

            elif "<final_answer>" in content:
                break
                
            else:
                # If no tool called, just continue (maybe thinking)
                full_prompt = "Please use a tool (<execute_command>, <read_file>, <write_file>) or <final_answer>."

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            break

if __name__ == "__main__":
    main()
