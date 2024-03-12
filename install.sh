conda create --name slurmgui python=3.9.0 -y && conda activate slurmgui
pip install -r requirements.txt
python reset_password.py 123456

mkdir -p ~/.local/bin
cp bin ~/.local/bin
chmod +x ~/.local/bin/code
chmod +x ~/.local/bin/server
chmod +x ~/.local/bin/submit