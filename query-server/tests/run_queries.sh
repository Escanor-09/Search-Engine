#!/bin/bash
HOST="http://127.0.0.1:8000"
BASE="$HOST/search"
OUTFILE="query_results_$(date +%Y-%m-%d).md"

queries=(
  "python"
  "kubernetes"
  "machine learning"
  "engineers"
  "hiring"
  "the a an of"
  "\"machine learning\""
  "\"learning machine\""
  "python AND kubernetes"
  "docker OR linux"
  "python NOT juspay"
  "engineer AND python NOT google"
  "pyhton"
  "kubernets"
  "quantumfluxcapacitor"
  "PYTHON Machine LEARNING"
  ""
  "remote"
  "google AND \"machine learning\""
  "!!!???"
)

descriptions=(
  "Basic single-term match, TF-IDF ranking"
  "Basic single-term match"
  "Multi-term OR (default mode)"
  "Stemming — plural to singular root"
  "Stemming/stopword sanity check"
  "Pure stopword query"
  "Exact phrase match"
  "Reversed phrase — should NOT match"
  "Boolean AND (intersection)"
  "Boolean OR (union)"
  "Boolean NOT (exclusion)"
  "Combined AND + NOT"
  "Spelling correction (edit distance 1)"
  "Spelling correction (edit distance 1-2)"
  "Unknown word, no correction possible"
  "Case insensitivity"
  "Input validation — empty query"
  "location field is not indexed"
  "Boolean AND + phrase combined"
  "Validation — pure punctuation"
)

echo "# Query Test Results — $(date +%Y-%m-%d)" > "$OUTFILE"
echo "" >> "$OUTFILE"

for i in "${!queries[@]}"; do
  q="${queries[$i]}"
  desc="${descriptions[$i]}"
  echo "## Query: \`$q\`" >> "$OUTFILE"
  echo "**Tests:** $desc" >> "$OUTFILE"
  echo '```json' >> "$OUTFILE"
  curl -s -G "$BASE" --data-urlencode "q=$q" | python3 -m json.tool >> "$OUTFILE"
  echo '```' >> "$OUTFILE"
  echo "" >> "$OUTFILE"
done

echo "" >> "$OUTFILE"
echo "# Phase 4 — /health and /suggest" >> "$OUTFILE"
echo "" >> "$OUTFILE"

echo "## GET /health" >> "$OUTFILE"
echo '```json' >> "$OUTFILE"
curl -s "$HOST/health" | python3 -m json.tool >> "$OUTFILE"
echo '```' >> "$OUTFILE"
echo "" >> "$OUTFILE"

suggest_prefixes=("eng" "soft" "data" "zzznotaword" "")
for prefix in "${suggest_prefixes[@]}"; do
  echo "## GET /suggest?prefix=$prefix" >> "$OUTFILE"
  echo '```json' >> "$OUTFILE"
  curl -s -G "$HOST/suggest" --data-urlencode "prefix=$prefix" | python3 -m json.tool >> "$OUTFILE"
  echo '```' >> "$OUTFILE"
  echo "" >> "$OUTFILE"
done

echo "Results written to $OUTFILE"
echo "Note: cache-hit and rate-limit behavior (rows 25-27 in test_queries.md) aren't"
echo "capturable via one-shot curl + JSON diff -- check the server's stdout log lines"
echo "and see test_queries.md's Phase 4 section for how to exercise those manually."


# How to run this?
# chmod +x search-engine/tests/run_queries.sh
# bash search-engine/tests/run_queries.sh