# PDF OCR and Fuzzy Hashing Toolkit

This repository contains scripts designed to perform Optical Character Recognition (OCR) on PDF files and utilize fuzzy hashing to identify similar pages within these documents. These tools are crafted to maintain forensic soundness, ensuring the integrity and traceability of the processed data.

## Features

- **OCR Processing**: Automate the enhancement of scanned PDF files into searchable documents using OCR.
- **Fuzzy Hashing**: Detect similar pages across different PDFs by generating and comparing fuzzy hashes.
- **Forensic Soundness**: Adheres to principles ensuring data integrity, detailed logging, and minimal data alteration.

## Prerequisites

Before running the scripts, ensure the following dependencies are installed:

- **OCRmyPDF**: Provides the OCR functionality.
- **GNU Parallel**: Facilitates the parallel processing of files.
- **Python Libraries**: `pdf2image`, `Pillow`, `ssdeep`, `PyMuPDF` for image processing and fuzzy hashing.

Install OCRmyPDF and GNU Parallel on Ubuntu:

```bash
sudo apt-get install ocrmypdf parallel
```

Install required Python libraries:

```bash
pip install pdf2image Pillow ssdeep PyMuPDF
```

## Usage

### OCR Processing

Process all PDFs within a specified directory, applying OCR and saving the enhanced versions to an output directory:

1. **Set executable permissions** for the script:

```bash
chmod +x ocr_all_pdfs_recursive.sh
```

2. **Run the script**:

```bash
./ocr_all_pdfs_recursive.sh
```

You will be prompted to enter the paths for the input and output directories.

### Fuzzy Hashing

After processing PDFs with OCR, run the fuzzy hashing script to identify similar pages:

1. **Execute the script**:

```bash
python3 fuzzy_hashing.py
```

Input the directory containing the OCR-processed PDFs when prompted.

## Forensic Soundness Features

- **Data Integrity**: Utilizes MD5 checksums to verify the integrity of documents before and after processing.
- **Detailed Logging**: Maintains logs of all processing activities, ensuring a transparent audit trail.
- **Reproducibility**: Ensures that processes are repeatable and verifiable by third parties.

## Contributing

Contributions to this project are welcome! Please fork the repository and submit a pull request with your enhancements.

## License

This project is released under the Unlicense - see the [LICENSE](LICENSE) file for details.
```
