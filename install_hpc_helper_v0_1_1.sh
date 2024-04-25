#!/bin/bash

# Define the URL of the zip file
ZIP_URL="https://github.com/l1997i/slurm_hpc_helper/releases/download/v0.1.1/hpc_helper_v0_1_1.zip"
ZIP_FILE="hpc_helper_v0_1_1.zip"
DIR_NAME="hpc_helper_v0_1_1"

# Download the zip file
curl -L $ZIP_URL -o $ZIP_FILE

# Unzip the file into the current directory
unzip $ZIP_FILE

# Navigate into the directory
cd $DIR_NAME

# Make the install script executable
chmod +x install.sh

# Run the install script
./install.sh
