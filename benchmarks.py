#!/usr/bin/env python3
import os
import subprocess
import sys

# The 3 text-based files in the repo as seen in README
FILES = ["karamazov.txt", "megavirus.fasta.txt", "std_image.h"]

# Dict sizes: 16K, 30K, 38K, 50K, 64K, 128K
DICT_SIZES = [
    (16384, "16K"),
    (30720, "30K"),
    (38912, "38K"),
    (51200, "50K"),
    (65536, "64K"),
    (131072, "128K")
]

def get_file_size(path):
    return os.path.getsize(path)

def run_compression(algo, input_file, dict_size):
    output_file = f"{input_file}.{algo}.tmp"
    # Calling the scripts directly as requested (lzw and lzwx)
    # These are in the current directory.
    cmd = [f"./{algo}", f"--dict-size={dict_size}", input_file, output_file]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        size = get_file_size(output_file)
        if os.path.exists(output_file):
            os.remove(output_file)
        return size
    except subprocess.CalledProcessError as e:
        print(f"Error running {algo} on {input_file}: {e.stderr}", file=sys.stderr)
        return None

def benchmark():
    results = []
    for f in FILES:
        if not os.path.exists(f):
            print(f"Warning: {f} not found, skipping.", file=sys.stderr)
            continue
        
        original_size = get_file_size(f)
        for ds_val, ds_label in DICT_SIZES:
            print(f"Benchmarking {f} with dict size {ds_label} ({ds_val})...", file=sys.stderr)
            lzw_size = run_compression("lzw", f, ds_val)
            lzwx_size = run_compression("lzwx", f, ds_val)
            
            if lzw_size is None or lzwx_size is None:
                continue

            lzw_ratio = lzw_size / original_size
            lzwx_ratio = lzwx_size / original_size
            
            if lzwx_size < lzw_size:
                winner = "LZW-X"
                improvement = ((lzw_size - lzwx_size) / lzw_size) * 100
            elif lzw_size < lzwx_size:
                winner = "LZW"
                improvement = ((lzwx_size - lzw_size) / lzwx_size) * 100
            else:
                winner = "Tie"
                improvement = 0.0
            
            results.append({
                "file": f,
                "dict_size_label": ds_label,
                "dict_size_val": ds_val,
                "lzw_ratio": lzw_ratio,
                "lzwx_ratio": lzwx_ratio,
                "winner": winner,
                "improvement": improvement
            })
    return results

def print_markdown(results):
    print("# LZW vs LZW-X Benchmark Results\n")
    print("| File | Dict Size | LZW Ratio | LZW-X Ratio | Winner | Margin (%) |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    current_file = None
    for r in results:
        file_display = f"**{r['file']}**" if r['file'] != current_file else ""
        current_file = r['file']
        
        lzw_r = f"{r['lzw_ratio']:.4f}"
        lzwx_r = f"{r['lzwx_ratio']:.4f}"
        
        if r['winner'] == "LZW-X":
            lzwx_r = f"**{lzwx_r}**"
            winner_str = "🏆 **LZW-X**"
        elif r['winner'] == "LZW":
            lzw_r = f"**{lzw_r}**"
            winner_str = "🏆 **LZW**"
        else:
            winner_str = "Tie"
            
        print(f"| {file_display} | {r['dict_size_label']} | {lzw_r} | {lzwx_r} | {winner_str} | {r['improvement']:.2f}% |")

if __name__ == "__main__":
    # Ensure scripts are executable
    os.chmod("lzw", 0o755)
    os.chmod("lzwx", 0o755)
    
    results = benchmark()
    print_markdown(results)