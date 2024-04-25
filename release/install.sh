#!/bin/bash

# Recommend using bash if not already using it
if [ "$SHELL" != "/bin/bash" ]; then
    echo "You are using: $SHELL; It is recommended to run this script with bash."
    echo "Consider running this script with bash if you encounter issues."
fi

# Ask for user input
echo "Enter your password: "
read -r user_password
echo "Enter your email (e.g., i@luisli.org): "
read -r user_email
echo "Enter your home directory (e.g., /home2/mznv82): "
read -r user_home

# Escape forward slashes in home directory path for safe use in sed
escaped_user_email=$(echo "$user_email" | sed 's/[&/\]/\\&/g')
escaped_user_home=$(echo "$user_home" | sed 's/[&/\]/\\&/g')

# Replace the email in the specified files
sed -i "s/i@luisli.org/$escaped_user_email/g" src/templates/bash/code_tunnel.sh
sed -i "s/i@luisli.org/$escaped_user_email/g" src/templates/bash/sshd.sh
sed -i "s/i@luisli.org/$escaped_user_email/g" src/templates/bash/final_stage.sh

sed -i "s|/home2/mznv82|$escaped_user_home|g" config.json

# Set up the local bin directory and copy executables
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
mkdir -p ~/.local/bin
cp -r bin/* ~/.local/bin
chmod +x hpc_helper
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
cd "$DIR" || exit
python reset_password.py "$user_password"

# Notify the user of completion
echo "Installation and configuration complete."
