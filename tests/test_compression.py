#!/usr/bin/env python3
"""
Regression tests for LZW-X compression.

Tests round-trip correctness for both LZW and LZWX algorithms
using various file types from the filesystem.
"""

import io
import os
import sys
import tempfile
import hashlib
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from arch import (
    lzw_compress, lzw_decompress,
    lzwx_compress, lzwx_decompress,
    write_compressed, read_compressed,
    arithmetic_encode, arithmetic_decode,
)


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name):
        self.passed += 1
        print(f"  ✓ {name}")

    def fail(self, name, msg):
        self.failed += 1
        self.errors.append((name, msg))
        print(f"  ✗ {name}: {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed")
        if self.errors:
            print("\nFailures:")
            for name, msg in self.errors:
                print(f"  - {name}: {msg}")
        return self.failed == 0


def test_arithmetic_roundtrip(results: TestResult):
    """Test arithmetic coding encoding/decoding."""
    test_cases = [
        [1, 2, 3, 4, 5],
        [1, 1, 1, 1, 2, 2, 3],
        [100, 200, 300, 100, 200, 100],
        list(range(256)),
        [0] * 100,
        [i % 10 for i in range(1000)],
    ]

    for i, symbols in enumerate(test_cases):
        encoded, freq_pairs = arithmetic_encode(symbols)
        decoded = arithmetic_decode(encoded, freq_pairs, len(symbols))
        if decoded == symbols:
            results.ok(f"arithmetic_case_{i}")
        else:
            results.fail(f"arithmetic_case_{i}", f"Mismatch: got {len(decoded)} symbols")


def test_lzw_roundtrip(results: TestResult):
    """Test standard LZW compression/decompression."""
    test_cases = [
        b"hello world",
        b"aaaaaaaaaaa",
        b"abcabcabcabc",
        b"the quick brown fox jumps over the lazy dog",
        bytes(range(256)),
        b"\x00" * 1000,
        b"TOBEORNOTTOBEORTOBEORNOT",
    ]

    for i, data in enumerate(test_cases):
        codes = lzw_compress(data)
        decompressed = lzw_decompress(codes)
        if decompressed == data:
            results.ok(f"lzw_case_{i}")
        else:
            results.fail(f"lzw_case_{i}", f"Mismatch: {len(data)} -> {len(decompressed)}")


def test_lzwx_roundtrip(results: TestResult):
    """Test LZWX compression/decompression."""
    test_cases = [
        b"hello world",
        b"aaaaaaaaaaa",
        b"abcabcabcabc",
        b"the quick brown fox jumps over the lazy dog",
        bytes(range(256)),
        b"\x00" * 1000,
        b"TOBEORNOTTOBEORTOBEORNOT",
        # Cases that should benefit from edit-distance matching
        b"hello world hello werld hello world",  # typo variant
        b"abcdefg abcdefh abcdefg abcdefi",      # single char differences
    ]

    for i, data in enumerate(test_cases):
        codes = lzwx_compress(data)
        decompressed = lzwx_decompress(codes)
        if decompressed == data:
            results.ok(f"lzwx_case_{i}")
        else:
            results.fail(f"lzwx_case_{i}", f"Mismatch: {len(data)} -> {len(decompressed)}")


def test_file_format_roundtrip(results: TestResult):
    """Test full file format (with headers) for both algorithms."""
    test_data = b"The quick brown fox jumps over the lazy dog. " * 100

    for algo in ['lzw', 'lzwx']:
        # Compress
        buf = io.BytesIO()
        write_compressed(buf, algo, test_data)
        compressed = buf.getvalue()

        # Decompress
        buf = io.BytesIO(compressed)
        detected_algo, decompressed = read_compressed(buf)

        if detected_algo == algo and decompressed == test_data:
            results.ok(f"file_format_{algo}")
        else:
            results.fail(f"file_format_{algo}",
                        f"algo: {detected_algo}, size: {len(decompressed)}")


def test_empty_input(results: TestResult):
    """Test handling of empty input."""
    for algo in ['lzw', 'lzwx']:
        buf = io.BytesIO()
        write_compressed(buf, algo, b"")
        compressed = buf.getvalue()

        buf = io.BytesIO(compressed)
        detected_algo, decompressed = read_compressed(buf)

        if decompressed == b"":
            results.ok(f"empty_input_{algo}")
        else:
            results.fail(f"empty_input_{algo}", f"Got {len(decompressed)} bytes")


def test_binary_data(results: TestResult):
    """Test with binary data (all byte values)."""
    # Random-ish binary data
    import random
    random.seed(42)
    test_data = bytes(random.randint(0, 255) for _ in range(10000))

    for algo in ['lzw', 'lzwx']:
        buf = io.BytesIO()
        write_compressed(buf, algo, test_data)
        compressed = buf.getvalue()

        buf = io.BytesIO(compressed)
        _, decompressed = read_compressed(buf)

        if decompressed == test_data:
            results.ok(f"binary_data_{algo}")
        else:
            results.fail(f"binary_data_{algo}",
                        f"Mismatch at some position")


def test_real_files(results: TestResult):
    """Test with real files from the filesystem."""
    # Find some suitable test files
    test_files = []

    # Python source files
    for path in Path('/usr/lib').glob('**/*.py'):
        if path.is_file() and path.stat().st_size < 100000:
            test_files.append(path)
            if len(test_files) >= 2:
                break

    # Try some common locations for text files
    common_files = [
        '/etc/hosts',
        '/etc/passwd',
        '/usr/share/dict/words',
        '/var/log/system.log',
    ]

    for f in common_files:
        p = Path(f)
        if p.exists() and p.is_file():
            try:
                if p.stat().st_size < 1000000:  # < 1MB
                    test_files.append(p)
            except:
                pass

    # Also test with our own source
    test_files.append(Path(__file__).parent.parent / 'arch.py')

    for filepath in test_files:
        if not filepath.exists():
            continue

        try:
            original = filepath.read_bytes()
            if len(original) == 0:
                continue

            for algo in ['lzw', 'lzwx']:
                buf = io.BytesIO()
                write_compressed(buf, algo, original)
                compressed = buf.getvalue()

                buf = io.BytesIO(compressed)
                _, decompressed = read_compressed(buf)

                name = f"real_file_{filepath.name}_{algo}"
                if decompressed == original:
                    ratio = len(compressed) / len(original) * 100
                    results.ok(f"{name} ({ratio:.1f}%)")
                else:
                    results.fail(name, "Content mismatch")

        except Exception as e:
            results.fail(f"real_file_{filepath.name}", str(e))


def test_cli_roundtrip(results: TestResult):
    """Test the CLI tool for round-trip correctness."""
    archive_py = Path(__file__).parent.parent / 'arch.py'

    test_data = b"CLI test data " * 500

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / 'input.bin'
        compressed_file = Path(tmpdir) / 'compressed.lzwx'
        output_file = Path(tmpdir) / 'output.bin'

        input_file.write_bytes(test_data)

        for algo in ['lzw', 'lzwx']:
            # Compress
            result = subprocess.run(
                ['python3', str(archive_py), '--mode=compress', f'--algo={algo}',
                 str(input_file), str(compressed_file)],
                capture_output=True
            )
            if result.returncode != 0:
                results.fail(f"cli_{algo}_compress", result.stderr.decode())
                continue

            # Decompress
            result = subprocess.run(
                ['python3', str(archive_py), '--mode=decompress',
                 str(compressed_file), str(output_file)],
                capture_output=True
            )
            if result.returncode != 0:
                results.fail(f"cli_{algo}_decompress", result.stderr.decode())
                continue

            # Verify
            output_data = output_file.read_bytes()
            if output_data == test_data:
                results.ok(f"cli_roundtrip_{algo}")
            else:
                results.fail(f"cli_roundtrip_{algo}", "Content mismatch")


def test_compression_ratio(results: TestResult):
    """Test that compression actually compresses compressible data."""
    # Highly compressible data
    compressible = b"aaaaaaaaaa" * 1000

    for algo in ['lzw', 'lzwx']:
        buf = io.BytesIO()
        write_compressed(buf, algo, compressible)
        compressed = buf.getvalue()

        ratio = len(compressed) / len(compressible)
        if ratio < 0.5:  # Should compress to at least 50%
            results.ok(f"compression_ratio_{algo} ({ratio*100:.1f}%)")
        else:
            results.fail(f"compression_ratio_{algo}",
                        f"Ratio too high: {ratio*100:.1f}%")


def main():
    print("LZW-X Compression Test Suite")
    print("=" * 60)

    results = TestResult()

    print("\n[Arithmetic Coding]")
    test_arithmetic_roundtrip(results)

    print("\n[LZW Algorithm]")
    test_lzw_roundtrip(results)

    print("\n[LZWX Algorithm]")
    test_lzwx_roundtrip(results)

    print("\n[File Format]")
    test_file_format_roundtrip(results)

    print("\n[Edge Cases]")
    test_empty_input(results)

    print("\n[Binary Data]")
    test_binary_data(results)

    print("\n[Real Files]")
    test_real_files(results)

    print("\n[CLI Tool]")
    test_cli_roundtrip(results)

    print("\n[Compression Ratio]")
    test_compression_ratio(results)

    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
