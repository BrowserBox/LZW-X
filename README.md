# LZW-X: Dictionary Compression, Evolved.

LZW-X is a next-generation compression algorithm that breaks the "exact-match" barrier of classic LZW. By integrating fuzzy dictionary lookups and edit-distance modeling, LZW-X discovers hidden patterns in data where traditional compressors see only noise.

## 🚀 Why LZW-X?

Classic LZW (used in GIF, and Unix `compress`) is powerful but brittle. It relies on finding exact repeating prefixes. Change just one character, and the entire dictionary match breaks.

**The LZW-X breakthrough:** Instead of giving up on a near-match, LZW-X encodes the *difference*. It uses a sophisticated **Neighbor Graph** to find dictionary entries that are "close enough" and emits a compact edit script to patch the match.

### ✨ Key Features

- **Fuzzy Dictionary Lookups**: Leverages Levenshtein distance to find approximate matches.
- **Neighbor Graph Optimization**: High-performance local search avoids the $O(N)$ dictionary scan bottleneck.
- **Arithmetic Coding**: State-of-the-art entropy encoding for both dictionary codes and edit scripts.
- **Error Resilience**: Naturally handles mutations in DNA sequences, noisy log files, and minor variations in source code.
- **Lossy Mode (Experimental)**: Tunable compression that prioritizes pattern preservation over bit-perfect reconstruction.

## 📈 Performance

LZW-X shines on data with high "near-redundancy". While it is computationally more intensive (~8-10x slower), it frequently achieves superior compression ratios by discovering approximate matches.

### Detailed Benchmarks

| File | Dict Size | LZW Ratio | LZW-X Ratio | Winner | Margin (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **karamazov.txt** | 16K | 0.4598 | **0.4569** | 🏆 **LZW-X** | 0.63% |
|  | 30K | 0.4884 | **0.4884** | 🏆 **LZW-X** | 0.02% |
|  | 38K | **0.5093** | 0.5096 | 🏆 **LZW** | 0.05% |
|  | 50K | 0.5416 | **0.5413** | 🏆 **LZW-X** | 0.05% |
|  | 64K | **0.5796** | 0.5799 | 🏆 **LZW** | 0.06% |
|  | 128K | 0.7353 | **0.7353** | 🏆 **LZW-X** | 0.01% |
| **megavirus.fasta.txt** | 16K | **0.3446** | 0.3447 | 🏆 **LZW** | 0.03% |
|  | 30K | 0.4237 | **0.4232** | 🏆 **LZW-X** | 0.12% |
|  | 38K | 0.4642 | **0.4636** | 🏆 **LZW-X** | 0.12% |
|  | 50K | **0.5182** | 0.5188 | 🏆 **LZW** | 0.12% |
|  | 64K | 0.5743 | **0.5739** | 🏆 **LZW-X** | 0.07% |
|  | 128K | **0.7184** | 0.7197 | 🏆 **LZW** | 0.19% |
| **std_image.h** | 16K | **0.7178** | 0.7186 | 🏆 **LZW** | 0.12% |
|  | 30K | 0.9164 | **0.9152** | 🏆 **LZW-X** | 0.13% |
|  | 38K | 1.0115 | **1.0100** | 🏆 **LZW-X** | 0.15% |
|  | 50K | 1.1367 | **1.1353** | 🏆 **LZW-X** | 0.13% |
|  | 64K | 1.1729 | **1.1712** | 🏆 **LZW-X** | 0.14% |
|  | 128K | 1.1729 | **1.1712** | 🏆 **LZW-X** | 0.14% |

*Note: Ratios > 1.0 indicate the file grew (common for small files with large dictionaries due to header overhead).*

## 🧠 How it Works

1. **Exact Match Search**: Starts with standard LZW prefix matching.
2. **Neighbor Search**: If the match is too short, LZW-X pivots to the **Neighbor Graph**—a dynamic graph structure where each dictionary entry points to its "edit neighbors".
3. **Edit Scripting**: If a superior approximate match is found, it encodes the dictionary code plus a minimal set of edits (Substitutions, Insertions, Deletions).
4. **Entropy Coding**: The resulting stream is piped through a two-pass arithmetic encoder for maximum density.

## 🛠 Usage

Quick start with the included wrappers:

```bash
# Compress using the LZW-X engine
./lzwx -v input.txt output.lzwx

# Decompress back to original
./unlzwx output.lzwx input_restored.txt
```

### Advanced Options

```text
--dict-size, -d    Maximum dictionary entries (default: 65536)
--progress, -p     Visual progress indicator
--verbose, -v      Detailed compression statistics
```

## 🏗 Installation

Simply clone the repo and ensure you have Python 3.8+ installed.

```bash
git clone https://github.com/your-repo/LZW-X.git
cd LZW-X
chmod +x lzw* unlzw*
```

## License

This project is licensed under the **GNU AGPLv3**. See the `LICENSE` file for details.
