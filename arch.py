#!/usr/bin/env python3
"""
LZW-X: Edit-Distance Generalized LZW Compression

Usage:
    arch.py --mode=compress|decompress --algo=lzw|lzwx [options] <input> <output>

Algorithms:
    lzw   - Standard LZW compression
    lzwx  - LZW with edit-distance matching (LZW-X / LZW*)
"""

import argparse
import struct
import sys
import time
from dataclasses import dataclass
from typing import BinaryIO, Callable


# ==============================================================================
# Progress Indicator
# ==============================================================================

class Progress:
    """Simple progress indicator for terminal output."""

    def __init__(self, total: int, desc: str = "", enabled: bool = True, width: int = 40):
        self.total = total
        self.desc = desc
        self.enabled = enabled and sys.stderr.isatty()
        self.width = width
        self.current = 0
        self.start_time = time.time()
        self._last_update = 0

    def update(self, n: int = 1):
        """Update progress by n units."""
        self.current += n
        now = time.time()
        # Throttle updates to avoid excessive I/O
        if self.enabled and (now - self._last_update > 0.05 or self.current >= self.total):
            self._last_update = now
            self._draw()

    def set(self, pos: int):
        """Set absolute position."""
        self.current = pos
        self.update(0)

    def _draw(self):
        """Draw the progress bar."""
        pct = self.current / self.total if self.total > 0 else 1.0
        filled = int(self.width * pct)
        bar = "█" * filled + "░" * (self.width - filled)

        elapsed = time.time() - self.start_time
        if pct > 0 and pct < 1:
            eta = elapsed / pct - elapsed
            time_str = f"ETA {eta:.0f}s"
        else:
            time_str = f"{elapsed:.1f}s"

        line = f"\r{self.desc} [{bar}] {pct*100:5.1f}% {time_str}  "
        sys.stderr.write(line)
        sys.stderr.flush()

    def finish(self):
        """Complete the progress bar."""
        if self.enabled:
            self.current = self.total
            self._draw()
            sys.stderr.write("\n")
            sys.stderr.flush()


# ==============================================================================
# Arithmetic Coding
# ==============================================================================

class BitWriter:
    def __init__(self):
        self.buffer = []
        self.current_byte = 0
        self.bit_count = 0

    def write_bit(self, bit):
        self.current_byte = (self.current_byte << 1) | bit
        self.bit_count += 1
        if self.bit_count == 8:
            self.buffer.append(self.current_byte)
            self.current_byte = 0
            self.bit_count = 0

    def get_bytes(self):
        if self.bit_count > 0:
            self.buffer.append(self.current_byte << (8 - self.bit_count))
        return bytes(self.buffer)


class BitReader:
    def __init__(self, data):
        self.data = data
        self.idx = 0
        self.current_byte = 0
        self.bits_left = 0

    def read_bit(self):
        if self.bits_left == 0:
            if self.idx >= len(self.data):
                return 0  # End of stream padding
            self.current_byte = self.data[self.idx]
            self.idx += 1
            self.bits_left = 8
        
        bit = (self.current_byte >> (self.bits_left - 1)) & 1
        self.bits_left -= 1
        return bit


def arithmetic_encode(symbols: list[int]) -> tuple[bytes, dict[int, int]]:
    """Encode symbols using Arithmetic coding. Returns (encoded_bytes, freq_table)."""
    if not symbols:
        return b'', {}

    # Build frequency table
    freq_table = {}
    for s in symbols:
        freq_table[s] = freq_table.get(s, 0) + 1

    # Build cumulative probability ranges
    # We sort symbols to ensure encoder and decoder agree on order
    sorted_syms = sorted(freq_table.keys())
    cum_freq = {}
    total = 0
    for sym in sorted_syms:
        low = total
        total += freq_table[sym]
        cum_freq[sym] = (low, total)
    
    # Constants for 32-bit precision
    MAX_VAL = 0xFFFFFFFF
    ONE_QUARTER = (MAX_VAL + 1) // 4
    HALF = ONE_QUARTER * 2
    THREE_QUARTERS = ONE_QUARTER * 3

    low = 0
    high = MAX_VAL
    pending_bits = 0
    writer = BitWriter()

    for sym in symbols:
        range_val = high - low + 1
        sym_low, sym_high = cum_freq[sym]
        
        # Refine range
        high = low + (range_val * sym_high) // total - 1
        low = low + (range_val * sym_low) // total
        
        # Renormalize
        while True:
            if high < HALF:
                writer.write_bit(0)
                for _ in range(pending_bits):
                    writer.write_bit(1)
                pending_bits = 0
                low = low * 2
                high = high * 2 + 1
            elif low >= HALF:
                writer.write_bit(1)
                for _ in range(pending_bits):
                    writer.write_bit(0)
                pending_bits = 0
                low = (low - HALF) * 2
                high = (high - HALF) * 2 + 1
            elif low >= ONE_QUARTER and high < THREE_QUARTERS:
                pending_bits += 1
                low = (low - ONE_QUARTER) * 2
                high = (high - ONE_QUARTER) * 2 + 1
            else:
                break
                
    # Flush pending bits
    pending_bits += 1
    if low < ONE_QUARTER:
        writer.write_bit(0)
        for _ in range(pending_bits):
            writer.write_bit(1)
    else:
        writer.write_bit(1)
        for _ in range(pending_bits):
            writer.write_bit(0)

    return writer.get_bytes(), freq_table


def arithmetic_decode(data: bytes, freq_table: dict[int, int], num_symbols: int) -> list[int]:
    """Decode Arithmetic-encoded bytes back to symbols."""
    if not freq_table or num_symbols == 0:
        return []

    # Reconstruct cumulative frequencies
    sorted_syms = sorted(freq_table.keys())
    cum_freq_map = {} # sym -> (low, high)
    idx_to_sym = []   # fast lookup for binary search
    cum_freq_list = [] # [cumulative_count_at_idx]
    
    total = 0
    for sym in sorted_syms:
        idx_to_sym.append(sym)
        cum_freq_list.append(total)
        low = total
        total += freq_table[sym]
        cum_freq_map[sym] = (low, total)
    cum_freq_list.append(total) # Total at the end

    # Constants
    MAX_VAL = 0xFFFFFFFF
    ONE_QUARTER = (MAX_VAL + 1) // 4
    HALF = ONE_QUARTER * 2
    THREE_QUARTERS = ONE_QUARTER * 3

    low = 0
    high = MAX_VAL
    value = 0
    
    reader = BitReader(data)
    
    # Initialize value buffer
    for _ in range(32):
        value = (value << 1) | reader.read_bit()

    decoded = []
    
    for _ in range(num_symbols):
        range_val = high - low + 1
        
        # Find symbol where: cum_freq[s] <= ((value - low + 1) * total - 1) / range < cum_freq[s+1]
        
        # Let's use the property:
        # count = floor( ( (value - low + 1) * total - 1 ) / range )
        count = ((value - low + 1) * total - 1) // range_val
        
        import bisect
        # bisect_right returns index where count could be inserted while maintaining order.
        # cum_freq_list is [0, freq1, freq1+freq2, ...]
        # We want index i such that cum_freq_list[i] <= count
        # bisect_right gives first element > count. So index-1 is what we want.
        
        idx = bisect.bisect_right(cum_freq_list, count) - 1
        # Clamp just in case of precision edge cases
        idx = min(max(idx, 0), len(idx_to_sym) - 1)
        
        sym = idx_to_sym[idx]
        decoded.append(sym)
        
        sym_low, sym_high = cum_freq_map[sym]
        
        # Narrow range
        high = low + (range_val * sym_high) // total - 1
        low = low + (range_val * sym_low) // total
        
        # Renormalize
        while True:
            if high < HALF:
                # Do nothing, just shift
                pass
            elif low >= HALF:
                value -= HALF
                low -= HALF
                high -= HALF
            elif low >= ONE_QUARTER and high < THREE_QUARTERS:
                value -= ONE_QUARTER
                low -= ONE_QUARTER
                high -= ONE_QUARTER
            else:
                break
            
            low = low * 2
            high = high * 2 + 1
            value = (value << 1) | reader.read_bit()

    return decoded


# ==============================================================================
# Edit Distance & Alignment (for LZWX)
# ==============================================================================

# Edit operation types
OP_MATCH = 0
OP_SUB = 1      # substitute
OP_INS = 2      # insert
OP_DEL = 3      # delete
OP_TRANS = 4    # transpose

MAX_EDIT_DIST = 2  # Maximum edit distance for approximate matching


def edit_distance_with_alignment(s: bytes, t: bytes, max_dist: int) -> tuple[int, list[tuple]]:
    """
    Compute edit distance between s and t (full s against prefix of t).
    Returns (distance, edit_script) or (inf, []) if distance > max_dist.

    Edit script transforms s into t[0:matched_len].
    """
    n, m = len(s), len(t)
    if n == 0:
        return (m, [(OP_INS, 0, t[i]) for i in range(m)]) if m <= max_dist else (float('inf'), [])

    # DP table
    # We only need to compute values where |i - j| <= max_dist (plus a bit of margin)
    # Banded DP: O(N * max_dist)
    INF = float('inf')
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    
    # Initialize bounds for band
    # i goes from 0 to n
    # j goes from max(0, i - max_dist) to min(m, i + max_dist + k)
    # We need a slightly wider band for insertions
    
    # Base cases for band
    for i in range(1, min(n + 1, max_dist + 1)):
        dp[i][0] = i
    for j in range(1, min(m + 1, max_dist + 1)):
        dp[0][j] = j
        
    for i in range(1, n + 1):
        # Determine band range for j
        # We need to cover the diagonal i=j, plus/minus max_dist
        # Since we want to find a match for ALL of s, we expect j to be close to i.
        start_j = max(1, i - max_dist)
        end_j = min(m + 1, i + max_dist + 1)
        
        for j in range(start_j, end_j):
            if s[i-1] == t[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                cost = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
                dp[i][j] = cost
                
            # Transposition check (within band)
            # Damerau-Levenshtein
            if i > 1 and j > 1 and s[i-1] == t[j-2] and s[i-2] == t[j-1]:
                 # Only if valid cost
                 dp[i][j] = min(dp[i][j], dp[i-2][j-2] + 1)

    # Find best j
    best_j = -1
    best_dist = INF
    
    # We only need to check j where dp[n][j] is valid
    # The band at row n is [n - max_dist, n + max_dist]
    start_search = max(1, n - max_dist)
    end_search = min(m + 1, n + max_dist + 1)
    
    for j in range(start_search, end_search):
        if dp[n][j] <= max_dist:
            if best_j == -1 or dp[n][j] < best_dist or (dp[n][j] == best_dist and j > best_j):
                best_j = j
                best_dist = dp[n][j]

    if best_j == -1:
        return (INF, [])

    # Backtrace to get edit script
    edits = []
    i, j = n, best_j
    while i > 0 or j > 0:
        if i > 0 and j > 0 and s[i-1] == t[j-1]:
            i -= 1
            j -= 1
        elif i > 1 and j > 1 and s[i-1] == t[j-2] and s[i-2] == t[j-1] and dp[i][j] == dp[i-2][j-2] + 1:
            edits.append((OP_TRANS, i-2, 0)) # 0 is dummy char
            i -= 2
            j -= 2
        elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
            edits.append((OP_SUB, i-1, t[j-1]))
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j-1] + 1:
            edits.append((OP_INS, i, t[j-1]))
            j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + 1:
            edits.append((OP_DEL, i-1, 0))
            i -= 1
        else:
            break

    edits.reverse()
    return (best_dist, edits, best_j)


def apply_edits(s: bytes, edits: list[tuple]) -> bytes:
    """Apply edit script to transform s."""
    result = list(s)
    offset = 0
    for op in edits:
        if op[0] == OP_SUB:
            pos = op[1] + offset
            if 0 <= pos < len(result):
                result[pos] = op[2]
        elif op[0] == OP_INS:
            pos = op[1] + offset
            if 0 <= pos <= len(result):
                result.insert(pos, op[2])
                offset += 1
        elif op[0] == OP_DEL:
            pos = op[1] + offset
            if 0 <= pos < len(result):
                del result[pos]
                offset -= 1
        elif op[0] == OP_TRANS:
            pos = op[1] + offset
            if 0 <= pos < len(result) - 1:
                result[pos], result[pos+1] = result[pos+1], result[pos]
                # No offset change
    return bytes(result)


# ==============================================================================
# LZW Compression (Standard)
# ==============================================================================

def lzw_compress(data: bytes, max_dict_size: int = 65536, progress: Progress | None = None) -> list[int]:
    """Standard LZW compression."""
    if not data:
        return []

    # Initialize dictionary with single bytes
    dict_size = 256
    dictionary = {bytes([i]): i for i in range(256)}

    codes = []
    current = bytes([data[0]])

    for i, byte in enumerate(data[1:]):
        candidate = current + bytes([byte])
        if candidate in dictionary:
            current = candidate
        else:
            codes.append(dictionary[current])
            if dict_size < max_dict_size:
                dictionary[candidate] = dict_size
                dict_size += 1
            current = bytes([byte])

        if progress and i % 10000 == 0:
            progress.set(i + 1)

    if current:
        codes.append(dictionary[current])

    if progress:
        progress.finish()

    return codes


def lzw_decompress(codes: list[int], max_dict_size: int = 65536, progress: Progress | None = None) -> bytes:
    """Standard LZW decompression."""
    if not codes:
        return b''

    # Initialize dictionary with single bytes
    dict_size = 256
    dictionary = {i: bytes([i]) for i in range(256)}

    result = bytearray()
    current = dictionary[codes[0]]
    result.extend(current)

    for i, code in enumerate(codes[1:]):
        if code in dictionary:
            entry = dictionary[code]
        elif code == dict_size:
            entry = current + bytes([current[0]])
        else:
            raise ValueError(f"Invalid LZW code: {code}")

        result.extend(entry)
        
        if dict_size < max_dict_size:
            dictionary[dict_size] = current + bytes([entry[0]])
            dict_size += 1
            
        current = entry

        if progress and i % 10000 == 0:
            progress.set(i + 1)

    if progress:
        progress.finish()

    return bytes(result)


# ==============================================================================
# LZWX Compression (Edit-Distance Generalized)
# ==============================================================================

def encode_edits(edits: list[tuple]) -> list[int]:
    """Encode edit script as a list of integers for serialization."""
    if not edits:
        return [0]  # No edits marker

    encoded = [len(edits)]
    for op, pos, char in edits:
        encoded.extend([op, pos, char])
    return encoded


def decode_edits(encoded: list[int], idx: int) -> tuple[list[tuple], int]:
    """Decode edit script from integer list. Returns (edits, new_idx)."""
    count = encoded[idx]
    idx += 1
    edits = []
    for _ in range(count):
        op = encoded[idx]
        pos = encoded[idx + 1]
        char = encoded[idx + 2]
        edits.append((op, pos, char))
        idx += 3
    return edits, idx


def lzwx_compress(data: bytes, max_dist: int = MAX_EDIT_DIST, max_dict_size: int = 65536, 
                  use_transposition: bool = False, use_substitution: bool = False,
                  progress: Progress | None = None) -> list[int]:
    """LZWX compression with edit-distance matching."""
    if not data:
        return []

    # Initialize dictionary with single bytes
    dict_size = 256
    dictionary = {bytes([i]): i for i in range(256)}
    reverse_dict = {i: bytes([i]) for i in range(256)}
    
    # NEIGHBOR GRAPH
    # neighbors[code] = set of neighbor_codes (dist 1)
    neighbors = [set() for _ in range(max_dict_size)] # Pre-allocate
    
    output = []
    pos = 0
    prev = b''
    data_len = len(data)
    prev_code = -1 

    # Parameters
    MAX_NEIGHBORS_SEARCH = 20 # Limit how many neighbors we check

    while pos < data_len:
        if progress:
            progress.set(pos)
        
        # 1. Exact Match (Standard LZW)
        best_code = data[pos]
        best_len = 1
        best_edits = []
        best_gain = 1
        
        # LZW Longest Match
        current = bytes([data[pos]])
        exact_code = dictionary.get(current)
        
        # Optimized inner loop for exact match
        i = pos + 1
        while i < data_len:
            byte = data[i]
            candidate = current + bytes([byte])
            if candidate in dictionary:
                current = candidate
                exact_code = dictionary[current]
                i += 1
            else:
                break
        
        exact_len = len(current)
        
        if exact_len > best_len:
            best_code = exact_code
            best_len = exact_len
            best_edits = []
            best_gain = exact_len

        # 2. Approximate Match via Graph
        if max_dist > 0 and exact_code is not None:
            # Check neighbors of exact_code
            candidates = list(neighbors[exact_code])
            
            checked = 0
            for cand_code in candidates:
                if checked >= MAX_NEIGHBORS_SEARCH:
                    break
                
                entry = reverse_dict[cand_code]
                
                # Filter crazy lengths
                if abs(len(entry) - exact_len) > max_dist:
                    continue
                
                checked += 1
                
                # Check alignment
                window_len = len(entry) + max_dist
                window = data[pos : min(pos + window_len, data_len)]
                
                result = edit_distance_with_alignment(entry, window, max_dist)
                
                if result[0] != float('inf'):
                    dist, edits, matched_len = result
                    edit_cost = 1 + len(edits) * 3
                    gain = matched_len - edit_cost
                    
                    if gain > best_gain:
                        best_code = cand_code
                        best_len = matched_len
                        best_edits = edits
                        best_gain = gain

        # Output
        output.append(best_code)
        output.extend(encode_edits(best_edits))

        # Reconstruct actual for dictionary update
        if best_edits:
            actual = apply_edits(reverse_dict[best_code], best_edits)
        else:
            if best_len == exact_len:
                actual = current
            else:
                if best_code in reverse_dict:
                    actual = reverse_dict[best_code]
                else:
                    actual = bytes([best_code])
                if len(actual) < best_len:
                    actual = data[pos:pos+best_len]

        # Dictionary Update (Graph Maintenance)
        if prev and pos + best_len < data_len:
            new_char = actual[0:1] # bytes
            new_entry = prev + new_char
            
            if new_entry not in dictionary:
                if dict_size < max_dict_size: # Bounds check
                    new_code = dict_size
                    dictionary[new_entry] = new_code
                    reverse_dict[new_code] = new_entry
                    
                    # LINKING THE GRAPH
                    # 1. Link to Prev (Deletion of last char)
                    if prev_code != -1:
                        neighbors[new_code].add(prev_code)
                        neighbors[prev_code].add(new_code)
                        
                        # 2. Propagate neighbors from Prev (Deletions/Extensions)
                        p_neighbors = neighbors[prev_code]
                        for n_code in p_neighbors:
                            # If P has neighbor N, check if N + c exists.
                            n_entry = reverse_dict[n_code]
                            target_entry = n_entry + new_char
                            
                            target_code = dictionary.get(target_entry)
                            if target_code is not None:
                                # Found parallel edge!
                                neighbors[new_code].add(target_code)
                                neighbors[target_code].add(new_code)

                        # 3. Transposition Linking (Optional)
                        if use_transposition:
                            # New = Prev + c. Prev = PrevPrev + d. So New = ...dc
                            # Transposition = ...cd = PrevPrev + c + d
                            # Check if 'PrevPrev' exists (len(Prev) > 1)
                            if len(prev) > 0:
                                # d = prev[-1]
                                d_char = prev[-1:]
                                # PrevPrev = prev[:-1]
                                prev_prev_str = prev[:-1]
                                
                                # Construct Transposed Candidate
                                # T = PrevPrev + c + d
                                transposed_entry = prev_prev_str + new_char + d_char
                                
                                t_code = dictionary.get(transposed_entry)
                                if t_code is not None:
                                    # Link New and Transposed
                                    neighbors[new_code].add(t_code)
                                    neighbors[t_code].add(new_code)

                        # 4. Substitution Linking (Optional)
                        if use_substitution:
                             # If we have Prev (parent), check all siblings of Prev.
                             # Siblings are neighbors of Prev that have same length as Prev.
                             # Actually simpler: if 'New' = 'Prev' + 'c', check if 'Prev' + 'x' exists.
                             # 'Prev' + 'x' is a substitution neighbor of 'New' (dist 1: 'c' <-> 'x')
                             # This is implicit in the graph structure? 
                             # No. 'Prev'+'c' and 'Prev'+'x' are distance 1 apart (substitute c <-> x).
                             # We need to link them.
                             
                             # Iterate over all possible bytes x != c? Too slow (255 checks).
                             # Optimization: Iterate over existing extensions of Prev?
                             # We don't store "children of Prev".
                             # But 'Prev' + 'x' would have linked to 'Prev' when it was created (step 1).
                             # So 'Prev'+'x' is in neighbors[prev_code]!
                             
                             for neighbor_code in neighbors[prev_code]:
                                 neighbor_entry = reverse_dict[neighbor_code]
                                 # We are looking for siblings: len(neighbor) == len(New) == len(Prev) + 1
                                 if len(neighbor_entry) == len(new_entry):
                                     # Verify it's a substitution (same prefix 'Prev')
                                     # Since neighbor is connected to Prev, and len is same, 
                                     # and neighbor != Prev (len diff), it MUST be an extension of Prev?
                                     # Not necessarily. Could be a deletion from Prev+y+z? No dist 1.
                                     # It could be 'Prev' + 'x'.
                                     
                                     # Check if neighbor starts with Prev (optimization)
                                     # Actually we know:
                                     # New = Prev + c
                                     # Neighbor linked to Prev.
                                     # If Neighbor = Prev + x, then dist(New, Neighbor) = 1 (Sub c<->x)
                                     
                                     if neighbor_entry.startswith(prev):
                                          neighbors[new_code].add(neighbor_code)
                                          neighbors[neighbor_code].add(new_code)
                                
                    dict_size += 1

        prev = actual
        # Track prev_code for next iteration
        if not best_edits:
            prev_code = best_code
        else:
            prev_code = dictionary.get(actual, -1)
            
        pos += best_len

    if progress:
        progress.finish()

    return output


def lzwx_decompress(encoded: list[int], max_dict_size: int = 65536, progress: Progress | None = None) -> bytes:
    """LZWX decompression."""
    if not encoded:
        return b''

    # Initialize dictionary with single bytes
    dict_size = 256
    dictionary = {i: bytes([i]) for i in range(256)}
    # Also track entries to match compressor's "if new_entry not in dictionary" check
    entries_set = {bytes([i]) for i in range(256)}

    result = bytearray()
    idx = 0
    prev = b''
    encoded_len = len(encoded)

    while idx < encoded_len:
        if progress:
            progress.set(idx)

        code = encoded[idx]
        idx += 1

        edits, idx = decode_edits(encoded, idx)

        # Get base string
        if code in dictionary:
            entry = dictionary[code]
        elif code == dict_size:
            # Special case: code not yet in dictionary (LZW codeword-not-yet-defined case)
            entry = prev + bytes([prev[0]])
        else:
            raise ValueError(f"Invalid LZWX code: {code}")

        # Apply edits
        if edits:
            actual = apply_edits(entry, edits)
        else:
            actual = entry

        result.extend(actual)

        # Grow dictionary (match compressor logic exactly)
        if prev and idx < encoded_len:
            new_entry = prev + bytes([actual[0]])
            if new_entry not in entries_set:
                if dict_size < max_dict_size:
                    dictionary[dict_size] = new_entry
                    entries_set.add(new_entry)
                    dict_size += 1

        prev = actual

    if progress:
        progress.finish()

    return bytes(result)


# ==============================================================================
# File Format
# ==============================================================================

MAGIC_LZW = b'LZW\x00'
MAGIC_LZWX = b'LZWX'
VERSION = 3  # Bump version for new format with dict_size in header


def separate_lzwx_streams(mixed: list[int]) -> tuple[list[int], list[int]]:
    """Split interleaved LZWX stream into [Codes] and [Edits]."""
    codes_stream = []
    edits_stream = []
    i = 0
    n = len(mixed)
    while i < n:
        # Code
        codes_stream.append(mixed[i])
        i += 1
        
        # Count
        if i >= n: break
        count = mixed[i]
        edits_stream.append(count)
        i += 1
        
        # Edit Tuples
        for _ in range(count):
            edits_stream.append(mixed[i]); i+=1 # Op
            edits_stream.append(mixed[i]); i+=1 # Pos
            edits_stream.append(mixed[i]); i+=1 # Char
            
    return codes_stream, edits_stream


def restore_lzwx_streams(codes_stream: list[int], edits_stream: list[int]) -> list[int]:
    """Merge [Codes] and [Edits] back into interleaved stream."""
    mixed = []
    e_idx = 0
    e_len = len(edits_stream)
    
    for code in codes_stream:
        mixed.append(code)
        
        if e_idx < e_len:
            count = edits_stream[e_idx]
            mixed.append(count)
            e_idx += 1
            
            for _ in range(count):
                mixed.append(edits_stream[e_idx]); e_idx+=1
                mixed.append(edits_stream[e_idx]); e_idx+=1
                mixed.append(edits_stream[e_idx]); e_idx+=1
                
    return mixed


def write_compressed(f: BinaryIO, algo: str, data: bytes, max_dict_size: int = 65536, 
                     use_transposition: bool = False, use_substitution: bool = False,
                     show_progress: bool = False):
    """Write compressed data to file with header."""
    # Compress
    progress = Progress(len(data), desc=f"Compressing ({algo.upper()})", enabled=show_progress) if show_progress else None

    if algo == 'lzw':
        codes = lzw_compress(data, max_dict_size=max_dict_size, progress=progress)
        magic = MAGIC_LZW
    else:
        # Returns interleaved stream
        mixed_codes = lzwx_compress(data, max_dict_size=max_dict_size, 
                              use_transposition=use_transposition, use_substitution=use_substitution,
                              progress=progress)
        magic = MAGIC_LZWX

    # Write header
    f.write(magic)
    f.write(struct.pack('<B', VERSION))
    f.write(struct.pack('<I', max_dict_size))     # Store dictionary size
    f.write(struct.pack('<Q', len(data)))         # Original size
    
    # Helper to write a stream
    def write_stream(symbols):
        encoded, freq_table = arithmetic_encode(symbols)
        f.write(struct.pack('<Q', len(symbols)))      # Number of symbols
        f.write(struct.pack('<I', len(freq_table)))
        for sym, freq in freq_table.items():
            f.write(struct.pack('<I', sym))
            f.write(struct.pack('<I', freq))
        f.write(struct.pack('<Q', len(encoded)))
        f.write(encoded)

    if algo == 'lzw':
        f.write(struct.pack('<Q', len(codes)))        # Total symbols (legacy field, redundant with stream)
        f.write(struct.pack('<B', 1))                 # Stream Count = 1
        write_stream(codes)
    else:
        # Dual Stream (Codes + Edits)
        codes_stream, edits_stream = separate_lzwx_streams(mixed_codes)
        
        f.write(struct.pack('<Q', len(mixed_codes)))  # Total mixed symbols (legacy field)
        f.write(struct.pack('<B', 2))                 # Stream Count = 2
        write_stream(codes_stream)
        write_stream(edits_stream)


def read_compressed(f: BinaryIO, show_progress: bool = False) -> tuple[str, bytes]:
    """Read and decompress file. Returns (algo, decompressed_data)."""
    magic = f.read(4)
    if magic == MAGIC_LZW:
        algo = 'lzw'
    elif magic == MAGIC_LZWX:
        algo = 'lzwx'
    else:
        raise ValueError(f"Invalid file magic: {magic}")

    version = struct.unpack('<B', f.read(1))[0]
    if version != VERSION:
        # Basic backward compatibility for old format
        if version == 2:
            max_dict_size = 65536 # Default for old version
            f.seek(-1, 1) # Rewind by 1 byte to re-read the version byte as part of the next field in old format
        else:
            raise ValueError(f"Unsupported version: {version}")
    else:
        max_dict_size = struct.unpack('<I', f.read(4))[0]

    original_size = struct.unpack('<Q', f.read(8))[0]
    _ = struct.unpack('<Q', f.read(8))[0] # Total symbols (ignore)
    stream_count = struct.unpack('<B', f.read(1))[0]

    # Helper to read a stream
    def read_stream():
        num_symbols = struct.unpack('<Q', f.read(8))[0]
        freq_count = struct.unpack('<I', f.read(4))[0]
        freq_table = {}
        for _ in range(freq_count):
            sym = struct.unpack('<I', f.read(4))[0]
            freq = struct.unpack('<I', f.read(4))[0]
            freq_table[sym] = freq
        
        encoded_size = struct.unpack('<Q', f.read(8))[0]
        encoded = f.read(encoded_size)
        
        return arithmetic_decode(encoded, freq_table, num_symbols)

    if algo == 'lzw':
        if stream_count != 1: raise ValueError("LZW must have 1 stream")
        codes = read_stream()
    else:
        if stream_count != 2: raise ValueError("LZW-X must have 2 streams")
        codes_stream = read_stream()
        edits_stream = read_stream()
        codes = restore_lzwx_streams(codes_stream, edits_stream)

    # LZW/LZWX decode
    progress = Progress(len(codes), desc=f"Decompressing ({algo.upper()})", enabled=show_progress) if show_progress else None

    if algo == 'lzw':
        data = lzw_decompress(codes, max_dict_size=max_dict_size, progress=progress)
    else:
        data = lzwx_decompress(codes, max_dict_size=max_dict_size, progress=progress)

    return algo, data



# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='LZW-X Compression Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--mode', '-m', required=True, choices=['compress', 'decompress'],
                        help='Operation mode')
    parser.add_argument('--algo', '-a', choices=['lzw', 'lzwx'], default='lzwx',
                        help='Algorithm (default: lzwx)')
    parser.add_argument('input', help='Input file (use - for stdin)')
    parser.add_argument('output', help='Output file (use - for stdout)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print compression statistics')
    parser.add_argument('--progress', '-p', action='store_true',
                        help='Show progress bar')
    parser.add_argument('--dict-size', '-d', type=int, default=65536,
                        help='Maximum dictionary size (default: 65536)')
    parser.add_argument('--use-transposition', action='store_true',
                        help='Enable transposition (Damerau-Levenshtein) edges in graph')
    parser.add_argument('--use-substitution', action='store_true',
                        help='Enable substitution edges in graph (default: disabled)')

    args = parser.parse_args()

    # Open input
    if args.input == '-':
        in_data = sys.stdin.buffer.read()
    else:
        with open(args.input, 'rb') as f:
            in_data = f.read()

    if args.mode == 'compress':
        # Compress
        import io
        buf = io.BytesIO()
        write_compressed(buf, args.algo, in_data, max_dict_size=args.dict_size, 
                         use_transposition=args.use_transposition,
                         use_substitution=args.use_substitution,
                         show_progress=args.progress)
        out_data = buf.getvalue()

        if args.verbose:
            ratio = len(out_data) / len(in_data) * 100 if in_data else 0
            print(f"Algorithm: {args.algo.upper()}", file=sys.stderr)
            print(f"Original:  {len(in_data)} bytes", file=sys.stderr)
            print(f"Compressed: {len(out_data)} bytes", file=sys.stderr)
            print(f"Ratio: {ratio:.2f}%", file=sys.stderr)
    else:
        # Decompress
        import io
        buf = io.BytesIO(in_data)
        algo, out_data = read_compressed(buf, show_progress=args.progress)

        if args.verbose:
            print(f"Algorithm: {algo.upper()}", file=sys.stderr)
            print(f"Compressed: {len(in_data)} bytes", file=sys.stderr)
            print(f"Decompressed: {len(out_data)} bytes", file=sys.stderr)

    # Write output
    if args.output == '-':
        sys.stdout.buffer.write(out_data)
    else:
        with open(args.output, 'wb') as f:
            f.write(out_data)


if __name__ == '__main__':
    main()
