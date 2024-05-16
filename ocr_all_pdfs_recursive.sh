#!/bin/bash

set -euo pipefail

# Function to print usage
usage() {
    echo "Usage: $0"
    echo "This script prompts for an input directory and an output directory, runs ocrmypdf on all PDF files in the input directory and its subdirectories, and logs actions for forensic purposes."
    exit 1
}

# Check if ocrmypdf is installed
if ! command -v ocrmypdf &> /dev/null; then
    echo "ocrmypdf could not be found. Please install it before running this script."
    exit 1
fi

# Check if parallel is installed
if ! command -v parallel &> /dev/null; then
    echo "parallel could not be found. Please install it before running this script."
    exit 1
fi

# Check if md5sum is installed
if ! command -v md5sum &> /dev/null; then
    echo "md5sum could not be found. Please install it before running this script."
    exit 1
fi

# Prompt the user to enter the input directory
read -e -p "Enter the path to the input directory: " INPUT_DIR

# Validate the input directory
if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Input directory does not exist."
    usage
fi

# Prompt the user to enter the output directory
read -e -p "Enter the path to the output directory: " OUTPUT_DIR

# Ensure the output directory exists
mkdir -p "$OUTPUT_DIR"

# Create a log file for actions and errors
LOG_FILE="$OUTPUT_DIR/ocr_processing.log"
touch "$LOG_FILE"

# Function to calculate MD5 hash
calculate_md5() {
    file="$1"
    md5sum "$file" | awk '{ print $1 }'
}

# Function to process a single PDF file with OCR
process_pdf() {
    input_file="$1"
    relative_path="${input_file#$INPUT_DIR/}"
    output_file="$OUTPUT_DIR/$relative_path"
    mkdir -p "$(dirname "$output_file")"

    if [[ ! -f "$input_file" ]]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') Error: File not found: $input_file" >> "$LOG_FILE"
        return 1
    fi

    original_md5=$(calculate_md5 "$input_file")
    echo "$(date '+%Y-%m-%d %H:%M:%S') Processing file: \"$input_file\" (MD5: $original_md5)" >> "$LOG_FILE"

    if ! ocrmypdf -l eng+spa --rotate-pages --deskew --jobs 16 --output-type pdfa "$input_file" "$output_file" 2>> "$LOG_FILE"; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') Error processing file: \"$input_file\"" >> "$LOG_FILE"
        return 1
    fi

    processed_md5=$(calculate_md5 "$output_file")
    echo "$(date '+%Y-%m-%d %H:%M:%S') Processed file: \"$output_file\" (MD5: $processed_md5)" >> "$LOG_FILE"
}

export -f calculate_md5
export -f process_pdf
export INPUT_DIR OUTPUT_DIR LOG_FILE

# Find all PDF files and process them in parallel for OCR
pdf_files=()
while IFS= read -r -d '' file; do
    pdf_files+=("$file")
done < <(find "$INPUT_DIR" -type f -name "*.pdf" -print0)

total_files=${#pdf_files[@]}
echo "Found $total_files PDF files to process for OCR."

parallel --bar --eta -j 2 process_pdf ::: "${pdf_files[@]}"

echo "OCR processing complete for all PDF files in $INPUT_DIR and its subdirectories. Check $LOG_FILE for detailed logs and errors."
