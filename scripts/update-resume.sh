#!/bin/bash
# Update resume from YAML using rendercv
# Usage: ./scripts/update-resume.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RESUME_YAML="$PROJECT_DIR/resume.yaml"
OUTPUT_DIR="$PROJECT_DIR/static/resume"

# Check if rendercv is installed
if ! command -v rendercv &> /dev/null; then
    echo "Installing rendercv..."
    pip install rendercv
fi

# Check if resume.yaml exists
if [ ! -f "$RESUME_YAML" ]; then
    echo "Error: resume.yaml not found at $RESUME_YAML"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate resume using rendercv
echo "Generating resume from $RESUME_YAML..."
cd "$PROJECT_DIR"
rendercv render resume.yaml --output-folder-name static/resume

# Rename output files to consistent names
if [ -f "$OUTPUT_DIR/Patrick_Deutsch_CV.pdf" ]; then
    mv "$OUTPUT_DIR/Patrick_Deutsch_CV.pdf" "$OUTPUT_DIR/cv.pdf"
fi
if [ -f "$OUTPUT_DIR/Patrick_Deutsch_CV.html" ]; then
    mv "$OUTPUT_DIR/Patrick_Deutsch_CV.html" "$OUTPUT_DIR/cv.html"
fi

echo "Resume updated successfully!"
echo "  - PDF: $OUTPUT_DIR/cv.pdf"
echo "  - HTML: $OUTPUT_DIR/cv.html"
