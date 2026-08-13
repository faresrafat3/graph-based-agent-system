#!/usr/bin/env python3
"""Compare two benchmark JSON reports"""

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]

import argparse
from benchmarks.comparator import compare_reports, format_comparison_markdown

def main():
    parser = argparse.ArgumentParser(description="Compare benchmark reports")
    parser.add_argument("old_report", help="Path to old JSON report")
    parser.add_argument("new_report", help="Path to new JSON report")
    parser.add_argument("--output", help="Optional markdown output file")
    args = parser.parse_args()
    
    comp = compare_reports(args.old_report, args.new_report)
    md = format_comparison_markdown(comp)
    print(md)
    
    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"\n📝 Comparison saved to {args.output}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
