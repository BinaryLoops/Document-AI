import os
import subprocess

def count_lines_of_code(directory='.', exclude_dirs=None):
    """
    Count lines of code in Python files, excluding specified directories.
    
    Args:
        directory (str): Root directory to search
        exclude_dirs (list): Directories to exclude
    
    Returns:
        dict: Detailed line count information
    """
    if exclude_dirs is None:
        exclude_dirs = [
            '.git', 
            '__pycache__', 
            'venv', 
            'env', 
            '.vscode', 
            '.idea'
        ]
    
    # Use cloc for robust counting
    try:
        cmd = [
            'cloc', 
            '--json', 
            f'--exclude-dir={",".join(exclude_dirs)}', 
            '--include-lang=Python', 
            directory
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        import json
        cloc_result = json.loads(result.stdout)
        
        return {
            'total_files': cloc_result['Python']['nFiles'],
            'total_lines': cloc_result['Python']['code'],
            'comment_lines': cloc_result['Python']['comment'],
            'blank_lines': cloc_result['Python']['blank']
        }
    
    except FileNotFoundError:
        # Fallback manual counting if cloc not installed
        total_lines = 0
        files_counted = 0
        
        for root, _, files in os.walk(directory):
            if not any(excluded in root for excluded in exclude_dirs):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r') as f:
                            lines = f.readlines()
                            total_lines += len([l for l in lines if l.strip() and not l.strip().startswith('#')])
                            files_counted += 1
        
        return {
            'total_files': files_counted,
            'total_lines': total_lines
        }

# Directly count lines in the script
def count_code_in_script(script_content):
    """Count non-empty, non-comment lines in a script."""
    lines = script_content.split('\n')
    return len([
        line for line in lines 
        if line.strip() and not line.strip().startswith('#')
    ])

# Example usage
if __name__ == '__main__':
    # Count project lines
    project_stats = count_lines_of_code()
    print("Project Line Count:")
    for key, value in project_stats.items():
        print(f"{key}: {value}")
    
    # Count lines in current script
    with open(__file__, 'r') as f:
        script_lines = count_code_in_script(f.read())
        print(f"\nThis script's lines: {script_lines}")