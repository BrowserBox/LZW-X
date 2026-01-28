# LZW-X: Dictionary Compression, Evolved.

LZW-X is a next-generation compression algorithm that breaks the "exact-match" barrier of classic LZW. By integrating fuzzy dictionary lookups and edit-distance modeling, LZW-X discovers hidden patterns in data where traditional compressors see only noise.

## 🚀 Why LZW-X?

Classic LZW (used in GIF, ZIP, and Unix `compress`) is powerful but brittle. It relies on finding exact repeating prefixes. Change just one character, and the entire dictionary match breaks.

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

| File | Dict Size | LZW Ratio | LZW-X Ratio | Winner |
| :--- | :--- | :--- | :--- | :--- |
| **karamazov.txt** (Prose) | 16384 | 0.4598 | **0.4569** | 🏆 **LZW-X** |
| | 32768 | 0.4938 | **0.4937** | 🏆 **LZW-X** |
| | 51200 | 0.5416 | **0.5413** | 🏆 **LZW-X** |
| **megavirus.fasta.txt** (DNA) | 38912 | 0.4642 | **0.4636** | 🏆 **LZW-X** |
| | 65536 | 0.5743 | **0.5739** | 🏆 **LZW-X** |
| **std_image.h** (C Code) | 32768 | 0.9391 | **0.9378** | 🏆 **LZW-X** |
| | 38912 | 1.0115 | **1.0100** | 🏆 **LZW-X** |
| | 51200 | 1.1367 | **1.1353** | 🏆 **LZW-X** |
| | 65536 | 1.1729 | **1.1712** | 🏆 **LZW-X** |
| | 131072 | 1.1729 | **1.1712** | 🏆 **LZW-X** |

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
