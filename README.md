# LZW-X: Experimental Fuzzy-Matching Compression

LZW-X is a proof-of-concept compression algorithm that explores breaking the "exact-match" constraint of classic LZW. By integrating fuzzy dictionary lookups (bioinformatics-style alignment) and edit-distance modeling, LZW-X attempts to discover hidden patterns in data where traditional compressors see only noise.

## 🧪 The Hypothesis

Classic LZW (used in GIF and Unix `compress`) relies on finding exact repeating prefixes. If a sequence changes by just one character, the dictionary match breaks.

**The LZW-X approach:** Instead of giving up on a near-match, LZW-X attempts to encode the *difference*. It uses a **Neighbor Graph** to find dictionary entries that are "close enough" and emits a compact edit script to patch the match.

**Note:** This is currently a research prototype. It trades significant CPU cycles (approx 8-10x slower than LZW) for marginal compression ratio gains in specific "noisy" datasets.

### ✨ Key Features

- **Fuzzy Dictionary Lookups**: Leverages Levenshtein distance to find approximate matches.
- **Neighbor Graph Optimization**: Local search strategy to mitigate the cost of dictionary scanning.
- **Arithmetic Coding**: Two-pass entropy encoding for both dictionary codes and edit scripts.
- **Target Use Case**: High-redundancy data with mutations, such as DNA sequences or repetitive logs with timestamps.

## 📈 Performance Benchmarks

Current benchmarks highlight the trade-offs of this approach. While LZW-X can squeeze out more entropy than standard LZW in specific files (like `karamazov.txt`), the gains are currently small (<1%) compared to the computational cost.

| File | Dict Size | LZW Ratio | LZW-X Ratio | Winner | Margin (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **karamazov.txt** | 16K | 0.4598 | **0.4569** | 🏆 **LZW-X** | 0.63% |
|  | 30K | 0.4884 | **0.4884** | 🏆 **LZW-X** | 0.02% |
|  | 38K | **0.5093** | 0.5096 | 🏆 **LZW** | 0.05% |
|  | 50K | 0.5416 | **0.5413** | 🏆 **LZW-X** | 0.05% |
| **megavirus.fasta** | 30K | 0.4237 | **0.4232** | 🏆 **LZW-X** | 0.12% |
| **std_image.h** | 30K | 0.9164 | **0.9152** | 🏆 **LZW-X** | 0.13% |

*Note: Ratios > 1.0 indicate the file grew (header overhead).*

## 🧠 How it Works

1. **Exact Match Search**: Starts with standard LZW prefix matching.
2. **Neighbor Search**: If the match is too short, LZW-X pivots to the **Neighbor Graph**—a dynamic structure linking "edit neighbors".
3. **Edit Scripting**: If a superior approximate match is found, it encodes the dictionary code plus a minimal set of edits (Substitutions, Insertions, Deletions).
4. **Entropy Coding**: The resulting stream is piped through a two-pass arithmetic encoder.

## 🛠 Usage

Requires Python 3.8+.

```bash
git clone https://github.com/BrowserBox/LZW-X.git
cd LZW-X

# Compress
./lzwx -v input.txt output.lzwx

# Decompress
./unlzwx output.lzwx input_restored.txt
```

## Credits & Implementation

*   **Concept:** Adapted from research on sequence alignment applied to compression (circa 2013).
*   **Implementation:** This implementation was realized with the assistance of LLMs (Claude, etc), allowing for rapid prototyping of the arithemtic encoding logic etc.
*   **License:** GNU AGPLv3.

