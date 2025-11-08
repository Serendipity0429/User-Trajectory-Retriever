import sys

def check_misplaced_imports(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    last_import_line = -1
    first_code_line = -1

    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line.startswith('import ') or stripped_line.startswith('from '):
            last_import_line = i
        elif stripped_line and not stripped_line.startswith('#') and not stripped_line.startswith('"""') and not stripped_line.startswith("'''"):
            if first_code_line == -1:
                first_code_line = i

    if first_code_line != -1 and last_import_line > first_code_line:
        print(f"File: {file_path}, last_import: {last_import_line}, first_code: {first_code_line}")

if __name__ == "__main__":
    for file_path in sys.argv[1:]:
        check_misplaced_imports(file_path)