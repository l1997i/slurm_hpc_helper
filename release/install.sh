#!/bin/bash

# Ask for user input
read -p "Enter your password: " user_password
read -p "Enter your email (e.g., i@luisli.org): " user_email
read -p "Enter your home directory (e.g., /home2/mznv82): " user_home



# Replace the email in the specified files
sed -i "s/i@luisli.org/$user_email/g" src/templates/bash/code_tunnel.sh
sed -i "s/i@luisli.org/$user_email/g" src/templates/bash/sshd.sh
sed -i "s/i@luisli.org/$user_email/g" src/templates/bash/final_stage.sh

# Replace the home directory in the config.json file
sed -i "s|/home2/mznv82|$user_home|g" config.json

# Set up the local bin directory and copy executables
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
mkdir -p ~/.local/bin
cp -r bin/* ~/.local/bin
chmod +x ~/.local/bin/code
chmod +x ~/.local/bin/server
echo "export PATH=\"$DIR:\$PATH\"" >> ~/.bashrc

# Install stage 2 PyTorch environment
mkdir -p .pytorch
cd .pytorch || exit
python3 -m venv .
source bin/activate
pip install torch==1.11.0+cu113 torchvision==0.12.0+cu113 torchaudio==0.11.0 --extra-index-url https://download.pytorch.org/whl/cu113
pip install Werkzeug~=2.0.0

# Run the python script to reset the password
python reset_password.py "$user_password"

# Notify the user of completion
echo "Installation and configuration complete."
